"""
智能定位器修复
当元素定位失败时，通过 AI 分析页面 HTML 提供替代选择器
"""
import json
import os
from core.log_factory import log


class LocatorHealer:
    """
    Self-healing locator
    用法：在 BasePage._on_error 里调用，自动建议替代选择器
    """

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
        except Exception:
            pass

    def suggest_alternatives(
        self, broken_selector: str, page_html: str, element_purpose: str = ""
    ) -> list[str]:
        """
        Args:
            broken_selector: 失效的选择器
            page_html: 当前页面 HTML（建议截取关键片段）
            element_purpose: 元素用途描述，如 "登录按钮"
        Returns:
            候选替代选择器列表，优先级从高到低
        """
        if not self._available:
            return []

        prompt = f"""你是自动化测试专家。以下 CSS/XPath 选择器在页面中找不到对应元素：

失效选择器: {broken_selector}
元素用途: {element_purpose or '未知'}

当前页面 HTML 片段:
```html
{page_html[:5000]}
```

请分析 HTML，提供 3~5 个可能正确的替代选择器（优先使用 data-test、id、aria 属性）。
仅返回 JSON：{{"alternatives": ["selector1", "selector2", ...]}}"""

        try:
            resp = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.1,
            )
            result = json.loads(resp.choices[0].message.content)
            alternatives = result.get("alternatives", [])
            log.info(f"AI 建议了 {len(alternatives)} 个替代选择器: {alternatives}")
            return alternatives
        except Exception as e:
            log.error(f"LocatorHealer 失败: {e}")
            return []