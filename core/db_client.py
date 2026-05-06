import json
from fastapi import APIRouter
from backend.models.schemas import DashboardData, SummaryStats, TestRunSummary
from backend.services.allure_parser import AllureParser
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard():
    stats_raw = await DBClient.get_summary()
    total  = stats_raw["total"]
    passed = stats_raw["passed"]
    stats = SummaryStats(
        total     = total,
        passed    = passed,
        failed    = stats_raw["failed"],
        skipped   = stats_raw["skipped"],
        pass_rate = round(passed / total * 100, 1) if total else 0.0,
    )
    trend       = await DBClient.get_trend(days=10)
    recent_raw  = await DBClient.get_recent_runs(limit=10)
    recent_runs = [TestRunSummary.from_db(r) for r in recent_raw]
    return DashboardData(stats=stats, trend=trend, recent_runs=recent_runs)


@router.get("/runs")
async def get_runs(limit: int = 20):
    runs = await DBClient.get_recent_runs(limit=limit)
    return {"runs": [TestRunSummary.from_db(r).model_dump() for r in runs]}


@router.get("/runs/{run_id}", response_model=TestRunSummary)
async def get_run_detail(run_id: int):
    async with DBClient.get_session() as session:
        from core.db_client import TestRun
        run = await session.get(TestRun, run_id)
        if not run:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found")
        return TestRunSummary.from_db(run)


@router.get("/runs/{run_id}/failed-cases")
async def get_failed_cases(run_id: int):
    """
    获取指定运行的失败用例列表。
    优先从 DB（已解析过），否则实时解析 Allure 结果并存入 DB。
    """
    cases = await DBClient.get_failed_cases(run_id)

    if not cases:
        # 实时解析 Allure 结果
        parser = AllureParser()
        parsed = parser.parse_failed_cases()
        if parsed:
            await DBClient.save_cases(run_id, parsed)
            cases = await DBClient.get_failed_cases(run_id)
        log.info(f"[run {run_id}] 实时解析失败用例: {len(parsed)} 条")

    return [
        {
            "id":              c.id,
            "name":            c.name,
            "module":          c.module,
            "status":          c.status,
            "duration":        c.duration,
            "error_message":   c.error_message,
            "screenshot_path": c.screenshot_path,
            "ai_analysis":     c.ai_analysis,
        }
        for c in cases
    ]


@router.get("/runs/{run_id}/ai-summary")
async def get_ai_summary(run_id: int):
    """
    获取 AI 执行摘要。
    有缓存直接返回，否则调用 AI 生成。
    """
    from ai.case_generator import AICaseGenerator
    from core.db_client import TestRun

    async with DBClient.get_session() as session:
        run = await session.get(TestRun, run_id)
        if not run:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found")

        # 有缓存直接返回
        if run.ai_summary:
            try:
                cached = json.loads(run.ai_summary)
                cached["cached"] = True
                return cached
            except Exception:
                pass

    # 解析失败用例
    parser = AllureParser()
    failed = parser.parse_failed_cases()
    stats  = parser.get_stats()

    generator = AICaseGenerator()
    if not generator.available:
        return {
            "run_id": run_id,
            "summary": "AI 服务不可用，请配置 OPENAI_API_KEY。",
            "key_issues": [],
            "recommendations": [],
            "risk_level": "unknown",
            "available": False,
            "cached": False,
        }

    # 构建摘要上下文
    context = f"""
测试运行 #{run_id} 执行完毕：
- 总用例: {stats['total']}，通过: {stats['passed']}，失败: {stats['failed']}，跳过: {stats['skipped']}
- 通过率: {round(stats['passed']/stats['total']*100,1) if stats['total'] else 0}%

失败用例（前10条）：
{chr(10).join(f"  - {c['name']}: {(c.get('error_message') or '')[:150]}" for c in failed[:10])}
"""

    prompt = f"""你是资深测试经理。根据以下测试执行结果，生成一份专业的测试报告摘要。
以 JSON 格式返回，结构为：
{{
  "summary": "2-3句话的总结（中文）",
  "key_issues": ["问题1", "问题2", ...],
  "recommendations": ["建议1", "建议2", ...],
  "risk_level": "high|medium|low"
}}

{context}

仅返回 JSON。"""

    try:
        import os
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1000,
            temperature=0.3,
        )
        result = json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.error(f"AI 摘要生成失败: {e}")
        result = {
            "summary": f"AI 分析失败: {str(e)}",
            "key_issues": [],
            "recommendations": [],
            "risk_level": "unknown",
        }

    result["run_id"]   = run_id
    result["available"] = True
    result["cached"]    = False

    # 缓存到数据库
    await DBClient.save_ai_summary(run_id, json.dumps(result, ensure_ascii=False))

    return result