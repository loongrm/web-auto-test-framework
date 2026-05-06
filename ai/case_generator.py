import json
import os
from typing import Optional
from core.log_factory import log


class AICaseGenerator:
    """
    通过 LLM 根据用户故事或接口文档生成测试用例
    若未配置 OPENAI_API_KEY，所有方法返回空结果（降级处理）
    """

    def __init__(self):
        self._client = None
        self._model = "gpt-4o"
        self._available = False
        self._init_client()

    def _init_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            log.warning("OPENAI_API_KEY 未配置，AI 功能不可用")
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
            self._available = True
            log.info("AI 客户端初始化成功")
        except Exception as e:
            log.error(f"AI 客户端初始化失败: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def generate_ui_cases(self, user_story: str) -> list[dict]:
        """
        根据用户故事生成 UI 测试用例（结构化 JSON）
        Returns: [{"id", "title", "precondition", "steps", "expected", "priority"}, ...]
        """
        if not self._available:
            return []

        prompt = f"""你是资深测试工程师。根据以下用户故事，生成全面的 UI 自动化测试用例。

要求：
1. 覆盖正常流程、边界值、异常场景
2. 每条用例结构：id、title、precondition、steps（数组）、expected、priority（P0/P1/P2）
3. 仅返回 JSON，格式为 {{"cases": [...]}}，不包含任何其他文字

用户故事：
{user_story}"""

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            result = json.loads(resp.choices[0].message.content)
            cases = result.get("cases", [])
            log.info(f"AI 生成了 {len(cases)} 条用例，Token: {resp.usage.total_tokens}")
            return cases
        except Exception as e:
            log.error(f"AI 生成用例失败: {e}")
            return []

    def generate_api_cases(self, api_doc: str) -> str:
        """
        根据接口文档生成 API 测试用例（YAML 格式字符串）
        """
        if not self._available:
            return "# AI 不可用"

        prompt = f"""你是资深测试工程师。根据以下接口文档，生成全面的 API 测试用例。

要求：
1. 覆盖正常响应、参数边界、权限校验、错误响应
2. 以 YAML 格式输出，包含 id、desc、method、path、body、expected_status、expected_fields
3. 仅返回 YAML 内容，不包含说明文字

接口文档：
{api_doc}"""

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=3000,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.error(f"AI 生成 API 用例失败: {e}")
            return f"# 生成失败: {e}"

    def suggest_test_strategy(self, feature_desc: str) -> dict:
        """根据功能描述，建议测试策略"""
        if not self._available:
            return {}

        prompt = f"""你是测试架构师。针对以下功能，给出测试策略建议。
以 JSON 格式返回，包含：
- risk_level: 风险等级 (high/medium/low)
- test_types: 建议的测试类型列表
- focus_areas: 重点测试点
- automation_priority: 哪些场景优先自动化

功能描述：{feature_desc}

仅返回 JSON。"""

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            log.error(f"AI 策略建议失败: {e}")
            return {}