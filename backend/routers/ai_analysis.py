import tempfile
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form
from backend.models.schemas import (
    GenerateCasesRequest,
    HealLocatorRequest,
    AnalyzeFailureRequest,
)
from ai.failure_analyzer import AIFailureAnalyzer
from ai.case_generator import AICaseGenerator
from ai.locator_healer import LocatorHealer
from core.log_factory import log

router = APIRouter()

_analyzer = AIFailureAnalyzer()
_generator = AICaseGenerator()
_healer = LocatorHealer()


@router.post("/analyze-failure")
async def analyze_failure(
    screenshot: UploadFile = File(None),
    error_log: str = Form(...),
    test_code: str = Form(None),
    test_case_name: str = Form(""),
):
    """上传截图 + 错误日志，AI 分析根因"""
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

    return result


@router.post("/analyze-failure-json")
async def analyze_failure_json(req: AnalyzeFailureRequest):
    """纯 JSON 请求的失败分析（无截图）"""
    result = _analyzer.analyze(
        screenshot_path="",
        error_log=req.error_log,
        test_code=req.test_code,
        test_case_name=req.test_case_name or "",
    )
    return result


@router.post("/generate-cases")
async def generate_cases(req: GenerateCasesRequest):
    """根据用户故事/接口文档生成测试用例"""
    if req.case_type == "api":
        yaml_str = _generator.generate_api_cases(req.user_story)
        return {"type": "api", "yaml": yaml_str, "available": _generator.available}
    else:
        cases = _generator.generate_ui_cases(req.user_story)
        return {"type": "ui", "cases": cases, "count": len(cases), "available": _generator.available}


@router.post("/heal-locator")
async def heal_locator(req: HealLocatorRequest):
    """智能修复失效的元素选择器"""
    alternatives = _healer.suggest_alternatives(
        broken_selector=req.broken_selector,
        page_html=req.page_html,
        element_purpose=req.element_purpose or "",
    )
    return {
        "broken_selector": req.broken_selector,
        "alternatives": alternatives,
        "available": _healer._available,
    }


@router.get("/status")
async def ai_status():
    """检查 AI 功能是否可用"""
    return {
        "analyzer": _analyzer.available,
        "generator": _generator.available,
        "healer": _healer._available,
    }