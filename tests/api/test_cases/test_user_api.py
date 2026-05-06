import yaml
import pytest
import allure
from pathlib import Path
from tests.api.client.http_client import HttpClient
from core.config_reader import config


def _load_api_data(section: str) -> list[dict]:
    p = Path("data/api_data.yaml")
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get(section, [])


@allure.feature("用户管理 API")
@allure.suite("API自动化")
class TestUserAPI:

    @pytest.fixture(autouse=True)
    def client(self):
        self._client = HttpClient(base_url=config.get("api_base_url", "https://reqres.in"))

    # 参数化CRUD测试

    @allure.story("用户资源 CRUD")
    @pytest.mark.api
    @pytest.mark.parametrize("case", _load_api_data("users"), ids=[c["id"] for c in _load_api_data("users")])
    def test_user_crud(self, case):
        allure.dynamic.title(case["desc"])
        allure.dynamic.description(f"用例ID: {case['id']}")

        method = case["method"].lower()
        path = case["path"]
        params = case.get("params")
        body = case.get("body")

        resp = getattr(self._client, method)(path, params=params, json_body=body) \
            if method == "get" \
            else getattr(self._client, method)(path, json_body=body)

        # 验证状态码
        HttpClient.assert_status(resp, case["expected_status"])

        # 验证字段
        for field in case.get("expected_fields", []):
            HttpClient.assert_field_exists(resp, field)

        # 响应时间
        HttpClient.assert_response_time(resp, max_seconds=5.0)

    # 认证相关测试

    @allure.story("用户认证 API")
    @pytest.mark.api
    @pytest.mark.parametrize("case", _load_api_data("auth"), ids=[c["id"] for c in _load_api_data("auth")])
    def test_auth(self, case):
        allure.dynamic.title(case["desc"])

        resp = self._client.post(case["path"], json_body=case.get("body"))
        HttpClient.assert_status(resp, case["expected_status"])
        for field in case.get("expected_fields", []):
            HttpClient.assert_field_exists(resp, field)

    # 独立业务场景测试

    @allure.story("分页查询")
    @pytest.mark.api
    @pytest.mark.p1
    def test_pagination(self):
        allure.dynamic.title("验证分页参数生效")

        page1 = self._client.get("/api/users", params={"page": 1})
        page2 = self._client.get("/api/users", params={"page": 2})

        HttpClient.assert_status(page1, 200)
        HttpClient.assert_status(page2, 200)

        data1 = page1.json()["data"]
        data2 = page2.json()["data"]

        ids1 = {u["id"] for u in data1}
        ids2 = {u["id"] for u in data2}
        assert not ids1 & ids2, f"两页数据有重叠: {ids1 & ids2}"

    @allure.story("创建后查询验证")
    @pytest.mark.api
    @pytest.mark.p1
    def test_create_and_verify(self):
        allure.dynamic.title("创建用户后验证数据一致性")

        payload = {"name": "auto_test_user", "job": "QA Engineer"}
        create_resp = self._client.post("/api/users", json_body=payload)
        HttpClient.assert_status(create_resp, 201)

        created = create_resp.json()
        assert created["name"] == payload["name"]
        assert created["job"] == payload["job"]
        assert "id" in created
        assert "createdAt" in created