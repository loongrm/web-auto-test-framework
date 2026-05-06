import os
import yaml
import pytest
import allure
from pathlib import Path
from tests.ui.pages.login_page import LoginPage
from tests.ui.pages.dashboard_page import DashboardPage


def _load_cases(expected: str) -> list[dict]:
    """从 YAML 加载指定预期结果的用例"""
    p = Path("data/login_data.yaml")
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [c for c in data["login_cases"] if c["expected"] == expected]


@allure.feature("用户认证")
@allure.suite("UI自动化")
class TestLogin:

    # 成功登录

    @allure.story("正常登录流程")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    @pytest.mark.p0
    @pytest.mark.parametrize("case", _load_cases("success"), ids=[c["id"] for c in _load_cases("success")])
    def test_login_success(self, page, case):
        allure.dynamic.title(case["desc"])
        allure.dynamic.description(f"用例ID: {case['id']} | 优先级: {case.get('priority', 'P1')}")

        login_page = LoginPage(page)
        login_page.open()
        login_page.login(case["username"], case["password"])

        assert login_page.is_login_success(), \
            f"[{case['id']}] 登录应成功但未跳转到 inventory 页面"

        dashboard = DashboardPage(page)
        dashboard.verify_on_page()
        count = dashboard.get_product_count()
        assert count > 0, "商品列表为空"
        allure.attach(f"商品数量: {count}", name="商品数量", attachment_type=allure.attachment_type.TEXT)

    # 失败登录

    @allure.story("异常登录处理")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.p0
    @pytest.mark.parametrize("case", _load_cases("error"), ids=[c["id"] for c in _load_cases("error")])
    def test_login_failure(self, page, case):
        allure.dynamic.title(case["desc"])

        login_page = LoginPage(page)
        login_page.open()
        login_page.login(case["username"], case["password"])

        assert not login_page.is_login_success(), \
            f"[{case['id']}] 登录应失败但却成功了"

        error_msg = login_page.get_error_message()
        assert case["error_msg"] in error_msg, \
            f"[{case['id']}] 错误提示不匹配\n期望包含: {case['error_msg']}\n实际: {error_msg}"

    # 登出流程
    @allure.story("退出登录")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.smoke
    @pytest.mark.p1
    def test_logout(self, page):
        allure.dynamic.title("正常退出登录")

        login_page = LoginPage(page)
        login_page.open()
        login_page.login("standard_user", "secret_sauce")
        assert login_page.is_login_success()

        dashboard = DashboardPage(page)
        dashboard.logout()

        # 退出后应回到登录页
        login_page.assert_visible(LoginPage.LOGIN_BUTTON)

    # 购物车流程

    @allure.story("添加商品到购物车")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.p1
    def test_add_to_cart(self, page):
        allure.dynamic.title("登录后添加商品到购物车")

        LoginPage(page).open().login("standard_user", "secret_sauce")
        dashboard = DashboardPage(page).verify_on_page()

        assert dashboard.get_cart_count() == 0, "初始购物车应为空"
        dashboard.add_first_item_to_cart()
        assert dashboard.get_cart_count() == 1, "添加后购物车数量应为1"