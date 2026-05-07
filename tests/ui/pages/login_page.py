import allure
from tests.ui.pages.base_page import BasePage
from core.log_factory import log


class LoginPage(BasePage):
    """SauceDemo 登录页 https://www.saucedemo.com"""

    USERNAME_INPUT  = "#user-name"
    PASSWORD_INPUT  = "#password"
    LOGIN_BUTTON    = "#login-button"
    ERROR_CONTAINER = "[data-test='error']"
    ERROR_CLOSE_BTN = ".error-button"

    @allure.step("打开登录页")
    def open(self) -> "LoginPage":
        self.navigate("/")
        self.assert_visible(self.LOGIN_BUTTON)
        return self

    @allure.step("执行登录: username={username}")
    def login(self, username: str, password: str) -> "LoginPage":
        log.info(f"登录 | username={username}")
        self.fill(self.USERNAME_INPUT, username)
        self.fill(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)
        return self

    def is_login_success(self) -> bool:
        """用 glob 模式等待跳转，不触发 assert_url_contains 的正则"""
        try:
            self.wait_for_url("**/inventory.html", timeout=8000)
            return True
        except Exception:
            return False

    def get_error_message(self) -> str:
        self.assert_visible(self.ERROR_CONTAINER, timeout=5000)
        return self.get_text(self.ERROR_CONTAINER)

    @allure.step("关闭错误提示")
    def close_error(self):
        self.click(self.ERROR_CLOSE_BTN)