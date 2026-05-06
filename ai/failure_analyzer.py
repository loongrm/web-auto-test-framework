import base64
import json
import os
from pathlib import Path
from core.log_factory import log


class AIFailureAnalyzer:
    """
    分析测试失败原因
    输入：失败截图 + 错误日志
    输出：根因分析、修复建议、是否 flaky
    """

    FAILURE_TYPES = [
        "element_not_found",
        "timeout",
        "assertion_error",
        "network_error",
        "environment_issue",
        "test_data_issue",
        "application_bug",
    ]

    def __init__(self):
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
            self._available = True
        except Exception as e:
            log.error(f"AI 分析器初始化失败: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def analyze(
        self,
        screenshot_path: str,
        error_log: str,
        test_code: str = None,
        test_case_name: str = "",
    ) -> dict:
        """
        Returns:
        {
            "root_cause": str,
            "failure_type": str,
            "suggestion": str,
            "confidence": float,
            "is_flaky": bool,
            "flaky_reason": str,
            "available": bool
        }
        """
        if not self._available:
            return self._unavailable_result()

        try:
            img_b64 = self._encode_image(screenshot_path)
        except Exception as e:
            log.warning(f"截图读取失败: {e}")
            img_b64 = None

        messages = self._build_messages(img_b64, error_log, test_code, test_case_name)

        try:
            resp = self._client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=1000,
                temperature=0.1,
            )
            result = json.loads(resp.choices[0].message.content)
            result["available"] = True
            log.info(
                f"AI 分析完成 | 类型: {result.get('failure_type')} | "
                f"置信度: {result.get('confidence')}"
            )
            return result
        except Exception as e:
            log.error(f"AI 分析失败: {e}")
            return self._unavailable_result(reason=str(e))

    def analyze_batch(self, failures: list[dict]) -> list[dict]:
        """批量分析多个失败用例"""
        results = []
        for item in failures:
            result = self.analyze(
                screenshot_path=item.get("screenshot", ""),
                error_log=item.get("error_log", ""),
                test_code=item.get("test_code"),
                test_case_name=item.get("name", ""),
            )
            result["test_case"] = item.get("name", "")
            results.append(result)
        return results

    # ─── 内部方法 ──────────────────────────────────────────────────────────

    def _build_messages(self, img_b64, error_log, test_code, test_case_name) -> list:
        system = """你是资深自动化测试工程师，专门分析测试失败原因。
根据截图和日志，给出精准的根因分析。
仅返回 JSON，格式：
{
  "root_cause": "根本原因（中文，简洁）",
  "failure_type": "element_not_found|timeout|assertion_error|network_error|environment_issue|test_data_issue|application_bug",
  "suggestion": "具体可执行的修复步骤（中文）",
  "confidence": 0.0~1.0,
  "is_flaky": true/false,
  "flaky_reason": "如果是flaky，说明原因，否则为空字符串"
}"""

        user_parts = []
        if img_b64:
            user_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"},
            })

        text_content = f"用例名称: {test_case_name}\n\n错误日志:\n```\n{error_log[:3000]}\n```"
        if test_code:
            text_content += f"\n\n测试代码:\n```python\n{test_code[:2000]}\n```"
        user_parts.append({"type": "text", "text": text_content})

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_parts},
        ]

    @staticmethod
    def _encode_image(path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _unavailable_result(reason: str = "AI 服务不可用") -> dict:
        return {
            "root_cause": reason,
            "failure_type": "unknown",
            "suggestion": "请手动查看截图和日志",
            "confidence": 0.0,
            "is_flaky": False,
            "flaky_reason": "",
            "available": False,
        }