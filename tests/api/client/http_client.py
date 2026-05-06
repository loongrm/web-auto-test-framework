import json
import time
import allure
import requests
from typing import Any, Dict, Optional
from core.log_factory import log
from core.config_reader import config
from core.allure_helper import AllureHelper


class HttpClient:
    """
    requests 封装
    - 自动记录请求/响应日志
    - 自动附加到 Allure 报告
    - 支持 Bearer Token 认证
    - 支持重试
    """

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or config.get("api_base_url", "")).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # 核心请求方法

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Dict = None,
        json_body: Any = None,
        data: Any = None,
        headers: Dict = None,
        timeout: int = 30,
        **kwargs,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        merged_headers = {**self.session.headers, **(headers or {})}

        # 请求日志
        log.info(f"→ {method.upper()} {url}")
        if params:
            log.debug(f"  Params: {params}")
        if json_body:
            log.debug(f"  Body: {json.dumps(json_body, ensure_ascii=False)}")

        start = time.time()
        resp = self.session.request(
            method,
            url,
            params=params,
            json=json_body,
            data=data,
            headers=merged_headers,
            timeout=timeout,
            **kwargs,
        )
        elapsed = time.time() - start

        # 响应日志
        log.info(f"← {resp.status_code} ({elapsed:.3f}s) {url}")
        try:
            log.debug(f"  Response: {resp.json()}")
        except Exception:
            log.debug(f"  Response (text): {resp.text[:300]}")

        # 附加到 Allure
        self._attach_to_allure(method, url, params, json_body, resp, elapsed)

        return resp

    # 快捷方法
    def get(self, path: str, params: Dict = None, **kw) -> requests.Response:
        return self.request("GET", path, params=params, **kw)

    def post(self, path: str, json_body: Any = None, **kw) -> requests.Response:
        return self.request("POST", path, json_body=json_body, **kw)

    def put(self, path: str, json_body: Any = None, **kw) -> requests.Response:
        return self.request("PUT", path, json_body=json_body, **kw)

    def patch(self, path: str, json_body: Any = None, **kw) -> requests.Response:
        return self.request("PATCH", path, json_body=json_body, **kw)

    def delete(self, path: str, **kw) -> requests.Response:
        return self.request("DELETE", path, **kw)

    # 认证

    def set_bearer_token(self, token: str):
        self.session.headers["Authorization"] = f"Bearer {token}"
        log.debug("Bearer Token 已设置")

    def clear_auth(self):
        self.session.headers.pop("Authorization", None)

    # 断言辅助
    @staticmethod
    def assert_status(resp: requests.Response, expected: int):
        assert resp.status_code == expected, (
            f"状态码不匹配 | 期望: {expected} | 实际: {resp.status_code}\n"
            f"响应体: {resp.text[:500]}"
        )

    @staticmethod
    def assert_field_exists(resp: requests.Response, field_path: str):
        """
        验证响应 JSON 中某字段存在
        支持点号路径: 'data.id', 'data.list'
        """
        try:
            data = resp.json()
        except Exception:
            raise AssertionError(f"响应非 JSON 格式: {resp.text[:200]}")

        parts = field_path.split(".")
        val = data
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                raise AssertionError(
                    f"字段 '{field_path}' 不存在\n响应体: {json.dumps(data, ensure_ascii=False)[:500]}"
                )

    @staticmethod
    def assert_response_time(resp: requests.Response, max_seconds: float = 3.0):
        actual = resp.elapsed.total_seconds()
        assert actual <= max_seconds, f"响应时间过长: {actual:.3f}s > {max_seconds}s"

    # 内部
    def _attach_to_allure(
        self, method, url, params, body, resp: requests.Response, elapsed: float
    ):
        detail = {
            "request": {
                "method": method.upper(),
                "url": url,
                "params": params,
                "body": body,
            },
            "response": {
                "status_code": resp.status_code,
                "elapsed_s": round(elapsed, 3),
                "body": self._safe_json(resp),
            },
        }
        AllureHelper.attach_json(detail, name=f"[{resp.status_code}] {method.upper()} {url}")

    @staticmethod
    def _safe_json(resp: requests.Response):
        try:
            return resp.json()
        except Exception:
            return resp.text[:1000]