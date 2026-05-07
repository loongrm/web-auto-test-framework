import yaml
import pytest
import allure
from pathlib import Path
from tests.api.client.http_client import HttpClient


def _load(section: str) -> list:
    with open(Path("data/api_data.yaml"), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get(section, [])


def _client() -> HttpClient:
    return HttpClient(base_url="https://jsonplaceholder.typicode.com")


@allure.feature("文章管理 API")
@allure.suite("API自动化")
class TestPostAPI:
    """JSONPlaceholder /posts 接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self._client = _client()

    @allure.story("文章 CRUD")
    @pytest.mark.api
    @pytest.mark.parametrize(
        "case",
        _load("posts"),
        ids=[c["id"] for c in _load("posts")],
    )
    def test_post_crud(self, case):
        allure.dynamic.title(case["desc"])
        allure.dynamic.description(f"用例ID: {case['id']}")

        method   = case["method"].lower()
        path     = case["path"]
        params   = case.get("params")
        body     = case.get("body")

        if method == "get":
            resp = self._client.get(path, params=params)
        elif method == "post":
            resp = self._client.post(path, json_body=body)
        elif method == "put":
            resp = self._client.put(path, json_body=body)
        elif method == "delete":
            resp = self._client.delete(path)
        else:
            pytest.skip(f"不支持的方法: {method}")

        HttpClient.assert_status(resp, case["expected_status"])

        # 验证字段（跳过 404 等无 body 的响应）
        if resp.status_code not in (204, 404):
            for field in case.get("expected_fields", []):
                self._assert_field(resp, field)

        HttpClient.assert_response_time(resp, max_seconds=10.0)

    @staticmethod
    def _assert_field(resp, field_path: str):
        """支持数组路径 [0].id 和普通路径 id.name"""
        import json
        try:
            data = resp.json()
        except Exception:
            raise AssertionError(f"响应非 JSON: {resp.text[:200]}")

        # 解析路径，支持 [0].title 格式
        import re
        parts = re.split(r'\.|\[(\d+)\]', field_path)
        parts = [p for p in parts if p is not None and p != ""]

        val = data
        for p in parts:
            if isinstance(val, list):
                val = val[int(p)]
            elif isinstance(val, dict):
                assert p in val, f"字段 '{field_path}' 中 '{p}' 不存在，实际: {list(val.keys())}"
                val = val[p]
            else:
                raise AssertionError(f"字段路径 '{field_path}' 无法继续遍历，当前值: {val}")


@allure.feature("用户管理 API")
@allure.suite("API自动化")
class TestUserAPI:
    """JSONPlaceholder /users 接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self._client = _client()

    @allure.story("用户查询")
    @pytest.mark.api
    @pytest.mark.parametrize(
        "case",
        _load("users"),
        ids=[c["id"] for c in _load("users")],
    )
    def test_user_query(self, case):
        allure.dynamic.title(case["desc"])
        resp = self._client.get(case["path"])
        HttpClient.assert_status(resp, case["expected_status"])
        if resp.status_code == 200:
            for field in case.get("expected_fields", []):
                TestPostAPI._assert_field(resp, field)

    @allure.story("分页查询")
    @pytest.mark.api
    @pytest.mark.p1
    def test_pagination(self):
        allure.dynamic.title("验证分页参数生效")
        page1 = self._client.get("/posts", params={"_page": 1, "_limit": 5})
        page2 = self._client.get("/posts", params={"_page": 2, "_limit": 5})

        HttpClient.assert_status(page1, 200)
        HttpClient.assert_status(page2, 200)

        ids1 = {p["id"] for p in page1.json()}
        ids2 = {p["id"] for p in page2.json()}
        assert not ids1 & ids2, f"两页数据有重叠: {ids1 & ids2}"
        assert len(ids1) == 5, f"第1页应返回5条，实际{len(ids1)}条"
        assert len(ids2) == 5, f"第2页应返回5条，实际{len(ids2)}条"

    @allure.story("创建后校验数据一致性")
    @pytest.mark.api
    @pytest.mark.p1
    def test_create_and_verify(self):
        allure.dynamic.title("创建文章后验证响应数据一致性")
        payload = {"title": "测试文章", "body": "测试内容", "userId": 1}
        resp = self._client.post("/posts", json_body=payload)
        HttpClient.assert_status(resp, 201)

        data = resp.json()
        assert data["title"] == payload["title"], "标题不匹配"
        assert data["body"]  == payload["body"],  "内容不匹配"
        assert data["userId"] == payload["userId"], "userId不匹配"
        assert "id" in data, "响应缺少 id 字段"

    @allure.story("评论关联查询")
    @pytest.mark.api
    @pytest.mark.p1
    def test_comments_by_post(self):
        allure.dynamic.title("根据文章ID查询关联评论")
        resp = self._client.get("/comments", params={"postId": 1})
        HttpClient.assert_status(resp, 200)
        data = resp.json()
        assert isinstance(data, list) and len(data) > 0, "评论列表不应为空"
        assert all(c["postId"] == 1 for c in data), "存在非 postId=1 的评论"

    @allure.story("待办事项查询")
    @pytest.mark.api
    @pytest.mark.p2
    def test_todos_by_user(self):
        allure.dynamic.title("根据用户ID查询待办事项")
        resp = self._client.get("/todos", params={"userId": 1})
        HttpClient.assert_status(resp, 200)
        data = resp.json()
        assert isinstance(data, list) and len(data) > 0
        assert all(t["userId"] == 1 for t in data)