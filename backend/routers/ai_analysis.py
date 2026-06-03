import json
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel

from core.db_client import DBClient
from core.log_factory import log
from ai.rag.analyzer import RAGFailureAnalyzer

router = APIRouter()

_analyzer: Optional[RAGFailureAnalyzer] = None


def get_analyzer() -> RAGFailureAnalyzer:
    """惰性初始化分析器单例，首次调用时加载 embedding 模型。"""
    global _analyzer
    if _analyzer is None:
        log.info("首次调用，正在初始化 RAG 分析器...")
        _analyzer = RAGFailureAnalyzer()
    return _analyzer


def _short_uuid() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


async def _run_analysis(error_log: str, test_case_name: str,
                        test_code: str, run_id, case_id) -> dict:
    """统一的分析逻辑，被 JSON 接口和截图接口共用。

    返回结构对齐旧前端期望的扁平字段，同时附带 RAG 检索信息。
    """
    analyzer = get_analyzer()
    cid = str(case_id) if case_id else f"{test_case_name or 'case'}_{_short_uuid()}"

    result = analyzer.analyze(
        case_id=cid,
        error_message=error_log,
        test_name=test_case_name,
        test_code=test_code or "",
    )
    a = result["analysis"]

    # 把分析结果回写数据库
    if case_id:
        try:
            await DBClient.update_case_ai_analysis(
                int(case_id), json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            log.warning(f"回写用例 AI 分析失败: {e}")

    if run_id or case_id:
        try:
            await DBClient.save_ai_analysis({
                "run_id":         run_id,
                "case_id":        case_id,
                "test_case_name": test_case_name,
                "failure_type":   a["failure_type"],
                "root_cause":     a["root_cause"],
                "suggestion":     a["suggestion"],
                "confidence":     a["confidence"],
                "is_flaky":       a["is_flaky"],
            })
        except Exception as e:
            log.warning(f"保存 AI 分析记录失败: {e}")

    # 扁平结构（对齐旧前端）+ RAG 增强字段
    return {
        "available":       True,
        "failure_type":    a["failure_type"],
        "root_cause":      a["root_cause"],
        "suggestion":      a["suggestion"],
        "confidence":      a["confidence"],
        "is_flaky":        a["is_flaky"],
        "retrieved_cases": result["retrieved_cases"],
        "retrieval_used":  result["retrieval_used"],
        "llm_backend":     result["llm_backend"],
    }


# JSON 入参接口（前端主用）

class AnalyzeFailureRequest(BaseModel):
    error_log: str = ""
    test_case_name: str = ""
    test_code: str = ""
    run_id: Optional[int] = None
    case_id: Optional[int] = None


@router.post("/analyze-failure-json")
async def analyze_failure_json(req: AnalyzeFailureRequest):
    """失败根因分析（JSON 入参）。"""
    return await _run_analysis(
        error_log=req.error_log,
        test_case_name=req.test_case_name,
        test_code=req.test_code,
        run_id=req.run_id,
        case_id=req.case_id,
    )


# 截图上传接口

@router.post("/analyze-failure")
async def analyze_failure_with_screenshot(
    screenshot:     UploadFile = File(None),
    error_log:      str = Form(...),
    test_code:      str = Form(None),
    test_case_name: str = Form(""),
    run_id:         int = Form(None),
    case_id:        int = Form(None),
):
    """失败根因分析（支持截图上传）。

    注：当前 RAG 文本分析不消费截图，截图参数保留是为了兼容旧前端表单，
    后续若接入多模态视觉模型可在此扩展。
    """
    return await _run_analysis(
        error_log=error_log,
        test_case_name=test_case_name,
        test_code=test_code or "",
        run_id=run_id,
        case_id=case_id,
    )


# 历史记录

@router.get("/history/{run_id}")
async def get_ai_history(run_id: int):
    """获取某次执行的 AI 分析历史记录。"""
    try:
        records = await DBClient.get_ai_history(run_id)
        return [
            {
                "id":             r.id,
                "test_case_name": r.test_case_name,
                "failure_type":   r.failure_type,
                "root_cause":     r.root_cause,
                "suggestion":     r.suggestion,
                "confidence":     r.confidence,
                "is_flaky":       r.is_flaky,
                "created_at":     r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]
    except Exception as e:
        log.warning(f"获取 AI 历史失败: {e}")
        return []


# 状态

@router.get("/status")
async def ai_status():
    """AI 子系统状态。

    返回字段对齐旧前端期望的 {analyzer, generator, healer} 结构，
    避免前端 getAIStatus 解构报错；generator/healer 固定 false（已移除）。
    """
    st = get_analyzer().status
    return {
        "analyzer":  st["llm_available"],
        "generator": False, 
        "healer":    False, 
        "rag":       st["kb_stats"], 
    }
