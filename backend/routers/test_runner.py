import asyncio
import uuid
import os
from typing import Dict
from fastapi import APIRouter, BackgroundTasks
from backend.models.schemas import RunRequest, RunResponse, TaskStatus
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()

# 内存任务状态（生产环境建议换 Redis）
_tasks: Dict[str, dict] = {}


@router.post("/run", response_model=RunResponse)
async def run_tests(req: RunRequest, background_tasks: BackgroundTasks):
    """触发测试执行"""
    task_id = str(uuid.uuid4())[:8]

    # 在 DB 中创建运行记录
    run = await DBClient.create_run(
        name=f"{req.module}-{task_id}",
        module=req.module,
        env=req.env,
        trigger=req.trigger,
    )

    _tasks[task_id] = {"status": "running", "run_id": run.id}
    background_tasks.add_task(_execute, task_id, req, run.id)

    log.info(f"任务已提交 | task_id={task_id} | run_id={run.id}")
    return RunResponse(
        task_id=task_id,
        run_id=run.id,
        status="accepted",
        message=f"任务 {task_id} 已提交，模块: {req.module}，环境: {req.env}",
    )


@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    """查询任务状态"""
    task = _tasks.get(task_id)
    if not task:
        return TaskStatus(task_id=task_id, status="not_found")
    return TaskStatus(task_id=task_id, **task)


@router.get("/tasks")
async def list_tasks():
    """列出所有任务"""
    return {"tasks": list(_tasks.items())}


async def _execute(task_id: str, req: RunRequest, run_id: int):
    """后台异步执行 pytest"""
    # 构建测试路径
    test_path = f"tests/{req.module}" if req.module != "all" else "tests/"

    cmd = [
        "python", "-m", "pytest", test_path,
        "-v",
        f"--alluredir=reports/allure-results",
        "--tb=short",
        "--junit-xml=reports/junit.xml",
    ]

    if req.markers:
        cmd += ["-m", req.markers]

    env = {**os.environ, "TEST_ENV": req.env}

    log.info(f"[{task_id}] 执行: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()

    stdout_str = stdout.decode("utf-8", errors="replace")
    stderr_str = stderr.decode("utf-8", errors="replace")

    # 解析 pytest 输出中的统计数字
    stats = _parse_pytest_output(stdout_str)
    status = "success" if proc.returncode == 0 else "failed"

    # 更新 DB
    await DBClient.finish_run(
        run_id=run_id,
        status=status,
        **stats,
    )

    _tasks[task_id] = {
        "status": status,
        "returncode": proc.returncode,
        "stdout": stdout_str[-5000:],
        "stderr": stderr_str[-2000:],
        "run_id": run_id,
        **stats,
    }
    log.info(f"[{task_id}] 执行完成 | status={status} | {stats}")


def _parse_pytest_output(output: str) -> dict:
    """从 pytest 输出中提取统计数字"""
    import re
    result = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    # 例: "3 passed, 1 failed, 1 skipped"
    match = re.search(
        r"(\d+) passed|(\d+) failed|(\d+) skipped|(\d+) error",
        output,
    )
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    skipped = re.search(r"(\d+) skipped", output)
    if passed:
        result["passed"] = int(passed.group(1))
    if failed:
        result["failed"] = int(failed.group(1))
    if skipped:
        result["skipped"] = int(skipped.group(1))
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    return result