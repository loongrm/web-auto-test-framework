import asyncio
import uuid
import os
import json
from typing import Dict
from fastapi import APIRouter, BackgroundTasks
from backend.models.schemas import RunRequest, RunResponse, TaskStatus
from backend.services.email_service import email_service
from backend.services.allure_parser import AllureParser
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()

_tasks: Dict[str, dict] = {}


@router.post("/run", response_model=RunResponse)
async def run_tests(req: RunRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())[:8]
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


@router.post("/notify/test")
async def test_email_notification():
    """验证邮件配置是否正确（调用此接口发一封测试邮件）"""
    to = [os.getenv("ALERT_EMAIL", "")]
    to = [addr for addr in to if addr]
    if not to:
        return {"success": False, "message": "ALERT_EMAIL 未配置"}
    success = email_service.send_test(to=to)
    return {
        "success": success,
        "message": "测试邮件已发送，请查收" if success else "发送失败，请检查 SMTP 配置",
    }


@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        return TaskStatus(task_id=task_id, status="not_found")
    return TaskStatus(task_id=task_id, **task)


@router.get("/tasks")
async def list_tasks():
    return {"tasks": list(_tasks.items())}


async def _execute(task_id: str, req: RunRequest, run_id: int):
    test_path = f"tests/{req.module}" if req.module != "all" else "tests/"
    cmd = [
        "python", "-m", "pytest", test_path,
        "-v",
        "--alluredir=reports/allure-results",
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

    stats  = _parse_pytest_output(stdout_str)
    status = "success" if proc.returncode == 0 else "failed"

    await DBClient.finish_run(run_id=run_id, status=status, **stats)

    _tasks[task_id] = {
        "status":     status,
        "returncode": proc.returncode,
        "stdout":     stdout_str[-5000:],
        "stderr":     stderr_str[-2000:],
        "run_id":     run_id,
        **stats,
    }
    log.info(f"[{task_id}] 执行完成 | status={status} | {stats}")

    # 发送邮件通知
    await _send_result_email(run_id, req, status, stats)


async def _send_result_email(run_id: int, req: RunRequest, status: str, stats: dict):
    """异步发送测试结果邮件"""
    to_list = [addr.strip() for addr in os.getenv("ALERT_EMAIL", "").split(",") if addr.strip()]
    if not to_list:
        log.warning("ALERT_EMAIL 未配置，跳过邮件通知")
        return

    # 获取失败用例
    failed_cases = []
    try:
        parser  = AllureParser()
        failed_cases = parser.parse_failed_cases()
        # 存入数据库
        if failed_cases:
            await DBClient.save_cases(run_id, failed_cases)
    except Exception as e:
        log.warning(f"解析失败用例时出错: {e}")

    # 获取AI摘要（可用时）
    ai_summary_text = ""
    try:
        from ai.case_generator import AICaseGenerator
        generator = AICaseGenerator()
        if generator.available and failed_cases:
            # 只在有失败用例且AI可用时生成摘要
            from backend.routers.reports import _generate_ai_summary_text
            ai_summary_text = await _generate_ai_summary_text(run_id, failed_cases, stats)
    except Exception as e:
        log.warning(f"获取AI摘要失败: {e}")

    dashboard_url = os.getenv("PLATFORM_URL", "http://localhost:5173")
    allure_url    = os.getenv("ALLURE_URL", "http://localhost:5050")

    try:
        email_service.send_test_result(
            to=to_list,
            run_id=run_id,
            module=req.module,
            env=req.env,
            status=status,
            total=stats.get("total", 0),
            passed=stats.get("passed", 0),
            failed=stats.get("failed", 0),
            skipped=stats.get("skipped", 0),
            duration=0.0,
            trigger=req.trigger,
            dashboard_url=f"{dashboard_url}/reports/{run_id}",
            allure_url=allure_url,
            failed_cases=failed_cases[:15],
            ai_summary=ai_summary_text,
        )
    except Exception as e:
        log.error(f"发送结果邮件失败: {e}")


def _parse_pytest_output(output: str) -> dict:
    import re
    result = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    passed  = re.search(r"(\d+) passed",  output)
    failed  = re.search(r"(\d+) failed",  output)
    skipped = re.search(r"(\d+) skipped", output)
    if passed:  result["passed"]  = int(passed.group(1))
    if failed:  result["failed"]  = int(failed.group(1))
    if skipped: result["skipped"] = int(skipped.group(1))
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    return result