import json
import os
from fastapi import APIRouter, HTTPException
from backend.models.schemas import DashboardData, SummaryStats, TestRunSummary
from backend.services.allure_parser import AllureParser
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()

# 复用与失败分析同一套 LLM 客户端（三级降级：云端 → 本地 Ollama → 规则）
# 模块级单例：避免每次请求重新初始化
_llm = None


def _get_llm():
    """惰性获取 LLM 客户端单例。"""
    global _llm
    if _llm is None:
        from ai.llm.client import LLMClient
        _llm = LLMClient()
    return _llm


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
    有缓存直接返回，否则调用 LLM 生成并缓存到数据库。
    LLM 走三级降级：云端 → 本地 Ollama → 规则兜底。
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

    llm = _get_llm()

    # 3. LLM 完全不可用（连本地 Ollama 都没有）→ 返回基于规则的简单摘要
    if not llm.available:
        total  = stats.get("total", 0)
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)
        rate   = round(passed / total * 100, 1) if total else 0
        rule_summary = (
            f"本次执行共 {total} 条用例，通过 {passed}，失败 {failed}，通过率 {rate}%。"
            + ("存在失败用例，建议优先排查。" if failed > 0 else "全部通过。")
        )
        result = {
            "run_id":          run_id,
            "available":       True,           # 仍可用（规则兜底），不再返回 False
            "cached":          False,
            "summary":         rule_summary,
            "key_issues":      [c["name"] for c in failed_cases[:5]],
            "recommendations": ["配置本地 Ollama 或云端 API 可获得更智能的分析"] if failed else [],
            "risk_level":      "high" if failed > 0 else "low",
            "llm_backend":     "rule_fallback",
        }
        await DBClient.save_ai_summary(run_id, json.dumps(result, ensure_ascii=False))
        return result

    total  = stats.get("total", 0)
    passed = stats.get("passed", 0)
    failed = stats.get("failed", 0)

    # 4. 生成纯文本摘要（供邮件使用）
    summary_text = _generate_ai_summary_text(llm, failed_cases, stats)

    # 5. 构建基础结果
    result = {
        "run_id":          run_id,
        "available":       True,
        "cached":          False,
        "summary":         summary_text or "（摘要生成中）",
        "key_issues":      [],
        "recommendations": [],
        "risk_level":      "high" if failed > 0 else "low",
        "llm_backend":     llm.backend,
    }

    # 6. 生成完整结构化摘要（走三级降级的 chat_json）
    context = (
        f"测试运行 #{run_id} 完成：总 {total}，通过 {passed}，失败 {failed}。\n"
        f"通过率: {round(passed / total * 100, 1) if total else 0}%\n"
        f"失败用例（前10条）:\n" +
        "\n".join(
            f"  - {c['name']}: {(c.get('error_message') or '')[:120]}"
            for c in failed_cases[:10]
        )
    )
    system_prompt = (
        "你是测试经理，根据测试结果生成报告摘要。"
        "必须严格返回如下 JSON，不要任何额外文字：\n"
        '{"summary":"2-3句总结","key_issues":["问题1","问题2"],'
        '"recommendations":["建议1","建议2"],"risk_level":"high|medium|low"}'
    )
    structured = llm.chat_json(system_prompt, context)
    if structured:
        result.update(structured)
        log.info(f"[run {run_id}] 结构化 AI 摘要生成成功 | backend={llm.backend}")
    else:
        log.warning(f"[run {run_id}] 结构化摘要失败，保留基础摘要")

    # 7. 缓存到数据库
    await DBClient.save_ai_summary(run_id, json.dumps(result, ensure_ascii=False))
    return result


def _generate_ai_summary_text(llm, failed_cases: list, stats: dict) -> str:
    """
    生成纯文本 AI 摘要（2-3句话），供邮件通知使用。
    走三级降级的 chat_text，失败时静默返回空字符串。
    """
    total  = stats.get("total", 0)
    passed = stats.get("passed", 0)
    failed = stats.get("failed", 0)
    context = (
        f"本次执行共 {total} 条用例，通过 {passed}，失败 {failed}，"
        f"通过率 {round(passed / total * 100, 1) if total else 0}%。\n"
        f"主要失败用例：" + "；".join(c["name"] for c in failed_cases[:5])
    )
    system_prompt = "你是测试经理，用2-3句话总结测试结果，指出主要问题和风险。"
    return llm.chat_text(system_prompt, context)


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
