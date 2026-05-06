import allure
import time
from pathlib import Path
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeout
from core.log_factory import log
from core.config_reader import config
from core.allure_helper import AllureHelper


class BasePage:
    def __init__(self, page: Page):
        self.page = page
        self.timeout = config.get_int("browser.timeout", 30000)
        self.base_url = config.get("base_url", "")

    # ─── 导航 ─────────────────────────────────────────────────────────────────

    @allure.step("打开页面: {url}")
    def navigate(self, url: str):
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"
        log.info(f"导航至: {full_url}")
        self.page.goto(full_url, timeout=self.timeout, wait_until="networkidle")

    def get_current_url(self) -> str:
        return self.page.url

    def get_title(self) -> str:
        return self.page.title()

    def refresh(self):
        self.page.reload(wait_until="networkidle")

    # ─── 元素操作 ─────────────────────────────────────────────────────────────

    @allure.step("点击: {selector}")
    def click(self, selector: str, timeout: int = None):
        log.debug(f"点击: {selector}")
        try:
            loc = self.page.locator(selector)
            loc.wait_for(state="visible", timeout=timeout or self.timeout)
            loc.click()
        except PlaywrightTimeout:
            self._on_error(f"点击超时: {selector}")
            raise

    @allure.step("输入文本: {selector}")
    def fill(self, selector: str, text: str, clear: bool = True):
        log.debug(f"输入 '{text}' → {selector}")
        loc = self.page.locator(selector)
        loc.wait_for(state="visible", timeout=self.timeout)
        if clear:
            loc.clear()
        loc.fill(text)

    @allure.step("获取文本: {selector}")
    def get_text(self, selector: str) -> str:
        text = self.page.locator(selector).inner_text()
        log.debug(f"获取文本: {selector} = '{text}'")
        return text

    def get_value(self, selector: str) -> str:
        return self.page.locator(selector).input_value()

    @allure.step("选择下拉选项: {selector} = {value}")
    def select_option(self, selector: str, value: str):
        self.page.locator(selector).select_option(value=value)

    @allure.step("悬停: {selector}")
    def hover(self, selector: str):
        self.page.locator(selector).hover()

    def press_key(self, key: str):
        self.page.keyboard.press(key)

    # ─── 等待 ─────────────────────────────────────────────────────────────────

    def wait_for_element(self, selector: str, state: str = "visible", timeout: int = None):
        self.page.locator(selector).wait_for(
            state=state, timeout=timeout or self.timeout
        )

    def wait_for_url(self, url_pattern: str, timeout: int = None):
        self.page.wait_for_url(url_pattern, timeout=timeout or self.timeout)

    def wait_for_network_idle(self):
        self.page.wait_for_load_state("networkidle")

    def wait_ms(self, ms: int):
        self.page.wait_for_timeout(ms)

    # ─── 断言 ─────────────────────────────────────────────────────────────────

    @allure.step("断言元素可见: {selector}")
    def assert_visible(self, selector: str, timeout: int = None):
        expect(self.page.locator(selector)).to_be_visible(
            timeout=timeout or self.timeout
        )
        log.debug(f"✓ 可见: {selector}")

    @allure.step("断言元素不可见: {selector}")
    def assert_hidden(self, selector: str):
        expect(self.page.locator(selector)).to_be_hidden()
        log.debug(f"✓ 不可见: {selector}")

    @allure.step("断言文本包含: '{expected}'")
    def assert_text_contains(self, selector: str, expected: str):
        expect(self.page.locator(selector)).to_contain_text(expected)
        log.debug(f"✓ 文本包含 '{expected}'")

    @allure.step("断言文本等于: '{expected}'")
    def assert_text_equals(self, selector: str, expected: str):
        expect(self.page.locator(selector)).to_have_text(expected)

    @allure.step("断言URL包含: '{path}'")
    def assert_url_contains(self, path: str):
        expect(self.page).to_have_url(lambda url: path in url)
        log.debug(f"✓ URL 包含 '{path}'")

    @allure.step("断言页面标题: '{expected}'")
    def assert_title(self, expected: str):
        expect(self.page).to_have_title(expected)

    @allure.step("断言元素数量: {selector} 数量={count}")
    def assert_element_count(self, selector: str, count: int):
        expect(self.page.locator(selector)).to_have_count(count)

    # ─── 截图 ─────────────────────────────────────────────────────────────────

    def screenshot(self, name: str = "screenshot") -> bytes:
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = Path("screenshots") / f"{name}_{ts}.png"
        path.parent.mkdir(exist_ok=True)
        data = self.page.screenshot(path=str(path), full_page=True)
        AllureHelper.attach_screenshot(data, name=name)
        log.info(f"截图: {path}")
        return data

    # ─── 内部辅助 ─────────────────────────────────────────────────────────────

    def _on_error(self, msg: str):
        log.error(msg)
        self.screenshot(name="error")

    def is_element_visible(self, selector: str) -> bool:
        try:
            return self.page.locator(selector).is_visible()
        except Exception:
            return False

    def count_elements(self, selector: str) -> int:
        return self.page.locator(selector).count()