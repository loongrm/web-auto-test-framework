import json
import os
from fastapi import APIRouter, HTTPException
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
    trend      = await DBClient.get_trend(days=10)
    recent_raw = await DBClient.get_recent_runs(limit=10)
    return DashboardData(
        stats       = stats,
        trend       = trend,
        recent_runs = [TestRunSummary.from_db(r) for r in recent_raw],
    )


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
            raise HTTPException(status_code=404, detail="Run not found")
        return TestRunSummary.from_db(run)


@router.get("/runs/{run_id}/failed-cases")
async def get_failed_cases(run_id: int):
    """
    获取指定运行的失败用例列表。
    优先从 DB 读取，若无则实时解析 Allure 结果并存入 DB。
    """
    cases = await DBClient.get_failed_cases(run_id)

    if not cases:
        parser = AllureParser()
        parsed = parser.parse_failed_cases()
        if parsed:
            await DBClient.save_cases(run_id, parsed)
            cases = await DBClient.get_failed_cases(run_id)
        # 修复：parsed 可能为空列表，用 len(parsed) 前先确认 parsed 已定义
        log.info(f"[run {run_id}] 实时解析失败用例: {len(parsed) if parsed else 0} 条")

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
    有缓存直接返回，否则调用 AI 生成并缓存到数据库。
    """
    from core.db_client import TestRun

    # 1. 先检查数据库缓存
    async with DBClient.get_session() as session:
        run = await session.get(TestRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.ai_summary:
            try:
                cached = json.loads(run.ai_summary)
                cached["cached"] = True
                return cached
            except Exception:
                pass  # 缓存损坏，重新生成

    # 2. 解析 Allure 结果
    parser       = AllureParser()
    failed_cases = parser.parse_failed_cases()
    stats        = parser.get_stats()

    # 3. 检查 AI 是否可用
    from ai.case_generator import AICaseGenerator
    generator = AICaseGenerator()
    if not generator.available:
        return {
            "run_id":          run_id,
            "available":       False,
            "cached":          False,
            "summary":         "AI 服务不可用，请在 .env 中配置 OPENAI_API_KEY。",
            "key_issues":      [],
            "recommendations": [],
            "risk_level":      "unknown",
        }

    # 4. 生成简单文本摘要（供邮件使用）
    summary_text = await _generate_ai_summary_text(run_id, failed_cases, stats)

    # 5. 构建基础结果
    result = {
        "run_id":          run_id,
        "available":       True,
        "cached":          False,
        "summary":         summary_text,
        "key_issues":      [],
        "recommendations": [],
        "risk_level":      "high" if stats.get("failed", 0) > 0 else "low",
    }

    # 6. 尝试生成完整结构化摘要（覆盖基础结果）
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key  = os.getenv("OPENAI_API_KEY"),
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        total  = stats.get("total", 0)
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)

        context = (
            f"测试运行 #{run_id} 完成：总 {total}，通过 {passed}，失败 {failed}。\n"
            f"通过率: {round(passed / total * 100, 1) if total else 0}%\n"
            f"失败用例（前10条）:\n" +
            "\n".join(
                f"  - {c['name']}: {(c.get('error_message') or '')[:120]}"
                for c in failed_cases[:10]
            )
        )

        resp = client.chat.completions.create(
            model    = "gpt-4o",
            messages = [{"role": "user", "content": (
                f"你是测试经理，根据以下结果生成测试报告摘要。\n"
                f"返回JSON格式：{{\"summary\":\"2-3句总结\","
                f"\"key_issues\":[\"问题1\",\"问题2\"],"
                f"\"recommendations\":[\"建议1\",\"建议2\"],"
                f"\"risk_level\":\"high|medium|low\"}}\n\n"
                f"{context}"
            )}],
            response_format = {"type": "json_object"},
            max_tokens  = 800,
            temperature = 0.3,
        )
        structured = json.loads(resp.choices[0].message.content)
        result.update(structured)
        log.info(f"[run {run_id}] 结构化 AI 摘要生成成功")

    except Exception as e:
        log.warning(f"[run {run_id}] 结构化 AI 摘要失败，使用简单摘要: {e}")

    # 7. 缓存到数据库
    await DBClient.save_ai_summary(run_id, json.dumps(result, ensure_ascii=False))

    return result


async def _generate_ai_summary_text(run_id: int, failed_cases: list, stats: dict) -> str:
    """
    生成纯文本 AI 摘要（2-3句话），供邮件通知使用。
    失败时静默返回空字符串，不影响主流程。
    """
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key  = os.getenv("OPENAI_API_KEY"),
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        total  = stats.get("total", 0)
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)

        context = (
            f"本次执行共 {total} 条用例，通过 {passed}，失败 {failed}，"
            f"通过率 {round(passed / total * 100, 1) if total else 0}%。\n"
            f"主要失败用例：" +
            "；".join(c["name"] for c in failed_cases[:5])
        )

        resp = client.chat.completions.create(
            model    = "gpt-4o-mini",
            messages = [{"role": "user", "content": (
                f"你是测试经理，用2-3句话总结以下测试结果，指出主要问题和风险：\n{context}"
            )}],
            max_tokens  = 200,
            temperature = 0.3,
        )
        text = resp.choices[0].message.content.strip()
        log.info(f"[run {run_id}] 文本摘要生成成功")
        return text

    except Exception as e:
        log.warning(f"[run {run_id}] AI 文本摘要失败: {e}")
        return ""
    
@router.post("/runs/{run_id}/ai-summary/clear")
async def clear_ai_summary_cache(run_id: int):
    """清除 AI 摘要缓存，下次请求时重新生成"""
    from core.db_client import TestRun
    async with DBClient.get_session() as session:
        run = await session.get(TestRun, run_id)
        if run:
            run.ai_summary = None
            await session.commit()
    return {"success": True, "message": f"Run {run_id} 的 AI 摘要缓存已清除"}