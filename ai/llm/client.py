"""
LLM 客户端（三级降级架构）

降级链：云端 OpenAI  →  本地 Ollama  →  规则引擎
        （最强但要钱）   （免费离线）    （永远兜底）

设计理念：
  生产级 LLM 应用不能假设"模型永远可用"。这里设计了三级降级：
    1. 云端 GPT-4o：能力最强，但依赖余额和网络
    2. 本地 Ollama：免费、离线、数据不出本机，能力够用于失败分类
    3. 规则引擎：基于关键词的本地兜底，保证永远有结果

  后端选择是"探测式"的：启动时自动检测哪些后端可用，
  调用时按优先级尝试，任一层失败自动降到下一层。

三层可靠性保障（在选定后端内部）：
  - 结构化约束：用 function calling 强制模型按 Pydantic schema 输出
  - 重试：tenacity 指数退避，区分可重试/不可重试错误
  - 校验：Pydantic 二次校验模型输出
"""

import os
import json
import logging
from typing import Optional
from pydantic import ValidationError
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

from core.log_factory import log
from ai.schemas.analysis import FailureAnalysis, FailureType, pydantic_to_openai_tool


class RetryableError(Exception):
    """可重试错误（网络抖动、限流）。"""


class NonRetryableError(Exception):
    """不可重试错误（余额不足、认证失败），应立即降级。"""


class LLMClient:
    """三级降级 LLM 客户端。"""

    def __init__(self):
        # 后端配置（均可由环境变量覆盖）
        self._cloud_key      = os.getenv("OPENAI_API_KEY", "").strip()
        self._cloud_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._cloud_model    = os.getenv("OPENAI_MODEL", "gpt-4o")

        self._ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self._ollama_model    = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

        self._cloud_client  = None
        self._ollama_client = None
        self._backend: Optional[str] = None  # "cloud" | "ollama" | None

        self._detect_backends()

    def _detect_backends(self):
        """启动时探测可用后端，按优先级选定。"""
        from openai import OpenAI

        # 1. 优先云端：仅当配置了有效 key
        if self._cloud_key and self._cloud_key.lower() not in ("ollama", "none", ""):
            try:
                self._cloud_client = OpenAI(
                    api_key=self._cloud_key, base_url=self._cloud_base_url
                )
                self._backend = "cloud"
                log.info(f"LLM 后端=云端 | model={self._cloud_model} | base={self._cloud_base_url}")
                return
            except Exception as e:
                log.warning(f"云端 LLM 初始化失败，尝试本地 Ollama: {e}")

        # 2. 降级本地 Ollama
        if self._probe_ollama():
            self._ollama_client = OpenAI(
                api_key="ollama", base_url=self._ollama_base_url
            )
            self._backend = "ollama"
            log.info(f"LLM 后端=本地Ollama | model={self._ollama_model}")
            return

        # 3. 都不可用 → 规则引擎
        log.warning("云端与本地 LLM 均不可用，将使用规则降级")
        self._backend = None

    def _probe_ollama(self) -> bool:
        """探测本地 Ollama 服务是否运行。"""
        try:
            import urllib.request
            base = self._ollama_base_url.replace("/v1", "")
            with urllib.request.urlopen(f"{base}/api/tags", timeout=2) as resp:
                return resp.status == 200
        except Exception as e:
            log.debug(f"Ollama 探测失败: {e}")
            return False

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend(self) -> Optional[str]:
        return self._backend

    def _active_client_and_model(self):
        if self._backend == "cloud":
            return self._cloud_client, self._cloud_model
        if self._backend == "ollama":
            return self._ollama_client, self._ollama_model
        return None, None

    @retry(
        retry=retry_if_exception_type(RetryableError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logging.getLogger(), logging.WARNING),
        reraise=True,
    )
    def _call_json_mode(self, system_prompt: str, user_prompt: str) -> dict:
        """JSON 模式调用（对小模型友好）。

        不用 function calling —— 3B 等小模型对 tools 的 schema 遵守能力差，
        常把字段名搞错。改为在 prompt 里明确给出 JSON 结构示例，
        用 response_format 约束输出 JSON，再手动解析。实测对小模型稳得多。
        """
        client, model = self._active_client_and_model()
        if client is None:
            raise NonRetryableError("无可用 LLM 后端")
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = resp.choices[0].message.content or ""
            return self._extract_json(content)
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("quota", "insufficient", "invalid_api_key",
                                       "authentication", "401", "403")):
                raise NonRetryableError(str(e))
            if any(k in msg for k in ("rate", "429", "timeout", "connection",
                                       "500", "502", "503")):
                raise RetryableError(str(e))
            raise RetryableError(str(e))

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从模型输出中提取 JSON。

        小模型有时会在 JSON 前后带上多余文字（如 ```json 代码块包裹），
        这里做容错提取：优先直接 parse，失败则用正则抠出第一个 {...}。
        """
        text = text.strip()
        # 去掉可能的 markdown 代码块包裹
        if text.startswith("```"):
            text = text.split("```")[1] if "```" in text[3:] else text
            text = text.replace("json", "", 1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise RetryableError("无法从模型输出中解析出 JSON")

    def analyze_failure(self, error_message: str, test_name: str,
                        test_code: str = "", retrieved_context: str = "") -> FailureAnalysis:
        """分析单条失败，返回结构化结果。无论后端是否可用都保证有返回。"""
        if not self.available:
            return self._rule_based_fallback(error_message, test_name)

        # 用明确的 JSON 格式说明替代 function calling，对小模型友好
        system_prompt = (
            "你是资深测试工程师，分析自动化测试失败的根本原因。\n"
            "必须严格返回如下 JSON 格式，不要有任何额外文字：\n"
            "{\n"
            '  "failure_type": "从 [element_not_found, timeout, assertion_failed, '
            'network_error, auth_error, data_error, env_error, unknown] 中选一个",\n'
            '  "root_cause": "根本原因，1-3句话",\n'
            '  "suggestion": "具体修复建议，1-3句话",\n'
            '  "confidence": 0.85,\n'
            '  "is_flaky": false\n'
            "}\n"
            "如果提供了历史相似案例，请参考其解决方案。"
        )
        user_prompt = self._build_user_prompt(error_message, test_name, test_code, retrieved_context)

        try:
            raw = self._call_json_mode(system_prompt, user_prompt)
            return FailureAnalysis.model_validate(raw)
        except NonRetryableError as e:
            log.warning(f"LLM 不可重试错误，降级到规则引擎: {e}")
            return self._rule_based_fallback(error_message, test_name)
        except ValidationError as e:
            log.warning(f"LLM 输出未通过校验，降级: {e}")
            return self._rule_based_fallback(error_message, test_name)
        except Exception as e:
            log.warning(f"LLM 调用最终失败（已重试），降级到规则引擎: {e}")
            return self._rule_based_fallback(error_message, test_name)
    def chat_json(self, system_prompt: str, user_prompt: str) -> dict | None:
        """通用 JSON 模式对话，返回解析后的 dict。

        供执行摘要等需要结构化输出的场景复用，自动走三级降级。
        LLM 不可用或解析失败时返回 None，由调用方决定兜底逻辑。
        """
        if not self.available:
            return None
        try:
            return self._call_json_mode(system_prompt, user_prompt)
        except Exception as e:
            log.warning(f"chat_json 调用失败: {e}")
            return None

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        """通用纯文本对话，返回字符串。

        供邮件文本摘要等场景复用。LLM 不可用或失败时返回空字符串。
        """
        if not self.available:
            return ""
        client, model = self._active_client_and_model()
        if client is None:
            return ""
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.3,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            log.warning(f"chat_text 调用失败: {e}")
            return ""

    @staticmethod
    def _build_user_prompt(error_message: str, test_name: str,
                           test_code: str, retrieved_context: str) -> str:
        parts = [f"## 当前失败\n测试用例: {test_name}\n错误信息:\n{error_message[:2000]}"]
        if test_code:
            parts.append(f"\n## 测试代码\n{test_code[:1500]}")
        if retrieved_context:
            parts.append(f"\n## 历史相似案例（供参考）\n{retrieved_context}")
        return "\n".join(parts)

    @staticmethod
    def _rule_based_fallback(error_message: str, test_name: str) -> FailureAnalysis:
        """规则降级引擎：基于关键词的本地失败分类，保证永远有合理输出。"""
        msg = error_message.lower()
        rules = [
            (["targetclosederror", "page.goto", "browser has been closed", "context or browser"],
             FailureType.ENV_ERROR,
             "浏览器上下文被意外关闭，通常是 headless 配置问题",
             "通过后端触发时需设置 browser.headless=true"),
            (["timeout", "timeouterror", "waiting for", "exceeded"],
             FailureType.TIMEOUT,
             "操作等待超时，元素未在规定时间内就绪",
             "检查元素加载时机，适当增加 wait_for 超时或改用更稳定的等待条件"),
            (["no element", "not found", "no node found", "locator", "selector"],
             FailureType.ELEMENT_NOT_FOUND,
             "元素定位失败，选择器未匹配到页面元素",
             "检查选择器是否因页面改版失效，使用 data-test 等稳定属性"),
            (["assertionerror", "assert", "expected", "状态码不匹配"],
             FailureType.ASSERTION_FAILED,
             "断言失败，实际结果与预期不符，疑似真实缺陷",
             "核对预期值，确认是被测功能缺陷还是用例预期写错"),
            (["401", "403", "unauthorized", "forbidden", "auth"],
             FailureType.AUTH_ERROR,
             "认证或权限错误，请求未通过鉴权",
             "检查测试账号 Token 是否有效，接口是否需要登录态"),
            (["connection", "network", "500", "502", "503", "refused", "econnrefused"],
             FailureType.NETWORK_ERROR,
             "网络或服务端错误，请求未正常完成",
             "确认被测服务可用性与网络连通性"),
        ]
        for keywords, ftype, cause, suggestion in rules:
            if any(k in msg for k in keywords):
                return FailureAnalysis(
                    failure_type=ftype,
                    root_cause=f"[规则引擎] {cause}",
                    suggestion=suggestion,
                    confidence=0.4,
                    is_flaky=(ftype in (FailureType.TIMEOUT, FailureType.NETWORK_ERROR)),
                )
        return FailureAnalysis(
            failure_type=FailureType.UNKNOWN,
            root_cause="[规则引擎] 无法自动归类，建议人工排查错误日志",
            suggestion="查看完整错误堆栈与失败截图进行人工分析",
            confidence=0.2,
        )