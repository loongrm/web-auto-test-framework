import asyncio
import uuid
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, BackgroundTasks
from backend.models.schemas import RunRequest, RunResponse, TaskStatus
from backend.services.email_service import email_service
from backend.services.allure_parser import AllureParser
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()

_tasks: Dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=3)

# 保存主事件循环引用（在FastAPI启动时设置）
_main_loop: Optional[asyncio.AbstractEventLoop] = None

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def set_main_loop(loop: asyncio.AbstractEventLoop):
    """由 main.py 在应用启动时调用"""
    global _main_loop
    _main_loop = loop
    log.info(f"主事件循环已注册: {loop}")


def _run_async_in_main_loop(coro) -> None:
    """
    从线程池同步环境中，把协程调度到 FastAPI 主事件循环执行。
    使用 run_coroutine_threadsafe，共享同一个 SQLAlchemy 连接池，
    彻底解决 'attached to a different loop' 问题。
    """
    if _main_loop is None:
        log.error("主事件循环未注册，数据库操作跳过")
        return
    try:
        future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
        future.result(timeout=30)  # 最多等30秒
    except Exception as e:
        log.error(f"主循环执行协程失败: {e}", exc_info=True)


# 路由接口

@router.post("/run", response_model=RunResponse)
async def run_tests(req: RunRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())[:8]

    run = await DBClient.create_run(
        name=f"{req.module}-{task_id}",
        module=req.module,
        env=req.env,
        trigger=req.trigger,
    )

    _tasks[task_id] = {
        "status":     "running",
        "run_id":     run.id,
        "stdout":     "",
        "stderr":     "",
        "passed":     0,
        "failed":     0,
        "total":      0,
        "returncode": None,
    }

    background_tasks.add_task(_execute_async, task_id, req, run.id)

    log.info(f"任务已提交 | task_id={task_id} | run_id={run.id}")
    return RunResponse(
        task_id=task_id,
        run_id=run.id,
        status="accepted",
        message=f"任务 {task_id} 已提交，模块: {req.module}，环境: {req.env}",
    )


@router.post("/notify/test")
async def test_email_notification():
    to_list = [a.strip() for a in os.getenv("ALERT_EMAIL", "").split(",") if a.strip()]
    if not to_list:
        return {"success": False, "message": "ALERT_EMAIL 未配置"}
    success = email_service.send_test(to=to_list)
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
    return {
        "project_root":      str(PROJECT_ROOT),
        "python_executable": sys.executable,
        "main_loop":         str(_main_loop),
        "tasks": {
            k: {
                "status":     v.get("status"),
                "run_id":     v.get("run_id"),
                "returncode": v.get("returncode"),
                "passed":     v.get("passed"),
                "failed":     v.get("failed"),
                "total":      v.get("total"),
            }
            for k, v in _tasks.items()
        },
    }


@router.get("/debug/env")
async def debug_env():
    tests_dir = PROJECT_ROOT / "tests"
    return {
        "project_root":        str(PROJECT_ROOT),
        "project_root_exists": PROJECT_ROOT.exists(),
        "tests_dir_exists":    tests_dir.exists(),
        "python_executable":   sys.executable,
        "PYTHONPATH":          os.environ.get("PYTHONPATH", "未设置"),
        "TEST_ENV":            os.environ.get("TEST_ENV", "未设置"),
        "cwd":                 os.getcwd(),
        "main_loop_set":       _main_loop is not None,
    }


# 异步包装

async def _execute_async(task_id: str, req: RunRequest, run_id: int):
    """把同步执行函数放到线程池，不阻塞 FastAPI 主线程"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _executor,
            _execute_sync,
            task_id, req, run_id
        )
    except Exception as e:
        log.error(f"[{task_id}] _execute_async 异常: {e}", exc_info=True)
        _tasks[task_id].update({
            "status": "failed",
            "stderr": f"任务调度异常: {str(e)}",
        })
        await DBClient.finish_run(run_id, "failed", 0, 0, 0, 0)


# 同步执行核心（线程池内运行

def _execute_sync(task_id: str, req: RunRequest, run_id: int):
    log.info(f"[{task_id}] 开始执行（线程池）")

    # 1. 确定测试路径
    test_path = str(
        PROJECT_ROOT / "tests" if req.module == "all"
        else PROJECT_ROOT / "tests" / req.module
    )

    if not Path(test_path).exists():
        msg = f"测试目录不存在: {test_path}"
        log.error(f"[{task_id}] {msg}")
        _tasks[task_id].update({"status": "failed", "stderr": msg})
        _db_finish_run(run_id, "failed", 0, 0, 0, 0)
        return

    # 2. 确保目录存在
    allure_dir = PROJECT_ROOT / "reports" / "allure-results"
    junit_file = PROJECT_ROOT / "reports" / "junit.xml"
    allure_dir.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)
    (PROJECT_ROOT / "screenshots").mkdir(exist_ok=True)

    # 3. 构建命令
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        f"--alluredir={allure_dir}",
        "--clean-alluredir",
        "--tb=short",
        f"--junit-xml={junit_file}",
        "--no-header",
    ]
    if req.markers:
        cmd += ["-m", req.markers]

    # 4. 环境变量
    env = {
        **os.environ,
        "TEST_ENV":   req.env,
        "PYTHONPATH": str(PROJECT_ROOT),
    }

    log.info(f"[{task_id}] 命令: {' '.join(cmd)}")
    log.info(f"[{task_id}] 工作目录: {PROJECT_ROOT}")

    # 5. 执行
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            env=env,
            timeout=600,
        )
        stdout_str = result.stdout or ""
        stderr_str = result.stderr or ""
        returncode  = result.returncode

    except subprocess.TimeoutExpired:
        log.error(f"[{task_id}] 执行超时（600s）")
        _tasks[task_id].update({
            "status": "failed", "stderr": "执行超时", "returncode": -1
        })
        _db_finish_run(run_id, "failed", 0, 0, 0, 0)
        return

    except Exception as e:
        log.error(f"[{task_id}] subprocess 异常: {e}", exc_info=True)
        _tasks[task_id].update({
            "status": "failed", "stderr": str(e)
        })
        _db_finish_run(run_id, "failed", 0, 0, 0, 0)
        return

    # 6. 打印关键日志
    log.info(f"[{task_id}] 退出码: {returncode}")
    if stderr_str.strip():
        log.warning(f"[{task_id}] stderr:\n{stderr_str[-2000:]}")
    if stdout_str.strip():
        last = "\n".join(stdout_str.splitlines()[-25:])
        log.info(f"[{task_id}] stdout 末尾:\n{last}")

    # 7. 解析统计
    stats  = _parse_pytest_output(stdout_str)
    status = "success" if returncode == 0 else "failed"
    if returncode == 5:
        status = "failed"
        stderr_str += "\n[警告] pytest 未收集到任何测试用例"

    log.info(f"[{task_id}] 完成 | status={status} | stats={stats}")

    # 8. ★ 关键：通过主事件循环更新数据库 ★
    _db_finish_run(run_id, status, **stats)

    # 9. 更新内存状态（前端轮询用）
    _tasks[task_id].update({
        "status":     status,
        "returncode": returncode,
        "stdout":     stdout_str[-8000:],
        "stderr":     stderr_str[-3000:],
        "run_id":     run_id,
        **stats,
    })

    # 10. 解析 Allure 结果，保存失败用例
    failed_cases = []
    try:
        parser = AllureParser(results_dir=str(allure_dir))
        failed_cases = parser.parse_failed_cases()
        if failed_cases:
            _db_save_cases(run_id, failed_cases)
            log.info(f"[{task_id}] 保存失败用例: {len(failed_cases)} 条")
    except Exception as e:
        log.warning(f"[{task_id}] 解析 Allure 结果失败: {e}")

    # 11. 发邮件
    _send_email_sync(run_id, req, status, stats, failed_cases)


# 数据库操作（通过主循环执行）

def _db_finish_run(run_id, status, total=0, passed=0, failed=0, skipped=0):
    _run_async_in_main_loop(
        DBClient.finish_run(run_id, status, total, passed, failed, skipped)
    )
    log.info(f"数据库更新完成 | run_id={run_id} | status={status} | "
             f"total={total} passed={passed} failed={failed}")


def _db_save_cases(run_id, cases):
    _run_async_in_main_loop(DBClient.save_cases(run_id, cases))


# 工具函数

def _parse_pytest_output(output: str) -> dict:
    import re
    result = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    for key, pattern in [
        ("passed",  r"(\d+) passed"),
        ("failed",  r"(\d+) failed"),
        ("skipped", r"(\d+) skipped"),
    ]:
        m = re.search(pattern, output)
        if m:
            result[key] = int(m.group(1))
    error = re.search(r"(\d+) error", output)
    if error:
        result["failed"] += int(error.group(1))
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    return result


def _send_email_sync(run_id, req, status, stats, failed_cases):
    to_list = [a.strip() for a in os.getenv("ALERT_EMAIL", "").split(",") if a.strip()]
    if not to_list:
        return

    platform_url = os.getenv("PLATFORM_URL", "http://localhost:5173").rstrip("/")
    allure_url   = os.getenv("ALLURE_URL",   "http://localhost:5050").rstrip("/")

    # 看板链接：指向前端报告摘要页
    dashboard_url = f"{platform_url}/reports/{run_id}/summary"

    # Allure链接：指向实际报告页面
    allure_report_url = f"{allure_url}/allure-docker-service/latest-report/index.html"

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
            dashboard_url=dashboard_url,
            allure_url=allure_report_url,
            failed_cases=failed_cases[:15],
        )
    except Exception as e:
        log.error(f"发送邮件失败: {e}")