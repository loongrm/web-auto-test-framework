import tempfile
import shutil
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form
from backend.models.schemas import GenerateCasesRequest, HealLocatorRequest, AnalyzeFailureRequest
from ai.failure_analyzer import AIFailureAnalyzer
from ai.case_generator import AICaseGenerator
from ai.locator_healer import LocatorHealer
from core.db_client import DBClient
from core.log_factory import log

router = APIRouter()

_analyzer = AIFailureAnalyzer()
_generator = AICaseGenerator()
_healer    = LocatorHealer()


@router.post("/analyze-failure")
async def analyze_failure_with_screenshot(
    screenshot:     UploadFile = File(None),
    error_log:      str = Form(...),
    test_code:      str = Form(None),
    test_case_name: str = Form(""),
    run_id:         int = Form(None),
    case_id:        int = Form(None),
):
    screenshot_path = ""
    tmp_file = None

    if screenshot and screenshot.filename:
        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            shutil.copyfileobj(screenshot.file, tmp_file)
            tmp_file.close()
            screenshot_path = tmp_file.name
        except Exception as e:
            log.warning(f"截图保存失败: {e}")

    result = _analyzer.analyze(
        screenshot_path=screenshot_path,
        error_log=error_log,
        test_code=test_code,
        test_case_name=test_case_name,
    )

    if tmp_file:
        Path(tmp_file.name).unlink(missing_ok=True)

    # 存储分析记录
    if result.get("available"):
        await _save_analysis(result, run_id, case_id, test_case_name)

    return result


@router.post("/analyze-failure-json")
async def analyze_failure_json(req: AnalyzeFailureRequest):
    """纯 JSON 请求（无截图），存储结果"""
    result = _analyzer.analyze(
        screenshot_path="",
        error_log=req.error_log,
        test_code=req.test_code,
        test_case_name=req.test_case_name or "",
    )

    if result.get("available"):
        await _save_analysis(
            result,
            run_id=getattr(req, "run_id", None),
            case_id=getattr(req, "case_id", None),
            test_case_name=req.test_case_name or "",
        )
        # 更新 TestCase 的 ai_analysis 字段
        if getattr(req, "case_id", None):
            await DBClient.update_case_ai_analysis(req.case_id, json.dumps(result, ensure_ascii=False))

    return result


@router.post("/generate-cases")
async def generate_cases(req: GenerateCasesRequest):
    if req.case_type == "api":
        yaml_str = _generator.generate_api_cases(req.user_story)
        return {"type": "api", "yaml": yaml_str, "available": _generator.available}
    cases = _generator.generate_ui_cases(req.user_story)
    return {"type": "ui", "cases": cases, "count": len(cases), "available": _generator.available}


@router.post("/heal-locator")
async def heal_locator(req: HealLocatorRequest):
    alternatives = _healer.suggest_alternatives(
        broken_selector=req.broken_selector,
        page_html=req.page_html,
        element_purpose=req.element_purpose or "",
    )
    return {
        "broken_selector": req.broken_selector,
        "alternatives":    alternatives,
        "available":       _healer._available,
    }


@router.get("/history/{run_id}")
async def get_ai_history(run_id: int):
    """获取某次运行的所有 AI 分析记录"""
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
            "created_at":     r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/status")
async def ai_status():
    return {
        "analyzer": _analyzer.available,
        "generator": _generator.available,
        "healer":   _healer._available,
    }


async def _save_analysis(result: dict, run_id, case_id, test_case_name: str):
    try:
        await DBClient.save_ai_analysis({
            "run_id":          run_id,
            "case_id":         case_id,
            "test_case_name":  test_case_name,
            "failure_type":    result.get("failure_type", "unknown"),
            "root_cause":      result.get("root_cause", ""),
            "suggestion":      result.get("suggestion", ""),
            "confidence":      result.get("confidence", 0.0),
            "is_flaky":        result.get("is_flaky", False),
            "flaky_reason":    result.get("flaky_reason", ""),
        })
    except Exception as e:
        log.warning(f"AI 分析记录存储失败: {e}")