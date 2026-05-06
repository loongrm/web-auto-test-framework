from fastapi import APIRouter
from backend.models.schemas import DashboardData, SummaryStats, TestRunSummary
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard():
    """看板汇总数据"""
    stats_raw = await DBClient.get_summary()
    total = stats_raw["total"]
    passed = stats_raw["passed"]

    stats = SummaryStats(
        total=total,
        passed=passed,
        failed=stats_raw["failed"],
        skipped=stats_raw["skipped"],
        pass_rate=round(passed / total * 100, 1) if total else 0.0,
    )
    trend = await DBClient.get_trend(days=10)
    recent_runs_raw = await DBClient.get_recent_runs(limit=10)
    recent_runs = [TestRunSummary.from_db(r) for r in recent_runs_raw]

    return DashboardData(stats=stats, trend=trend, recent_runs=recent_runs)


@router.get("/runs")
async def get_runs(limit: int = 20):
    """获取最近运行记录"""
    runs = await DBClient.get_recent_runs(limit=limit)
    return {"runs": [TestRunSummary.from_db(r).model_dump() for r in runs]}


@router.get("/runs/{run_id}")
async def get_run_detail(run_id: int):
    """获取单次运行详情"""
    async with DBClient.get_session() as session:
        from core.db_client import TestRun
        run = await session.get(TestRun, run_id)
        if not run:
            return {"error": "not found"}
        return TestRunSummary.from_db(run).model_dump()