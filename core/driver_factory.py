"""
Playwright 浏览器工厂
提供在非 pytest 场景（如后端服务）下同步/异步启动浏览器的能力
pytest 场景下请直接使用 conftest.py 中的 fixture
"""
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from playwright.async_api import async_playwright
from typing import Literal, Optional
from core.config_reader import config
from core.log_factory import log


BrowserType = Literal["chromium", "firefox", "webkit"]


class SyncDriverFactory:
    """同步浏览器工厂（适用于脚本、调试场景）"""

    def __init__(self):
        self._pw = None
        self._browser: Optional[Browser] = None

    def start(self, browser_type: BrowserType = None, headless: bool = None) -> Browser:
        self._pw = sync_playwright().start()
        _type = browser_type or config.get("browser.type", "chromium")
        _headless = headless if headless is not None else config.get_bool("browser.headless", False)
        _slow_mo = config.get_int("browser.slow_mo", 0)

        launcher = getattr(self._pw, _type)
        self._browser = launcher.launch(headless=_headless, slow_mo=_slow_mo)
        log.info(f"浏览器启动: {_type}, headless={_headless}")
        return self._browser

    def new_context(self) -> BrowserContext:
        return self._browser.new_context(
            viewport={
                "width": config.get_int("browser.viewport.width", 1920),
                "height": config.get_int("browser.viewport.height", 1080),
            },
            locale=config.get("browser.locale", "zh-CN"),
            timezone_id=config.get("browser.timezone", "Asia/Shanghai"),
        )

    def new_page(self) -> Page:
        ctx = self.new_context()
        return ctx.new_page()

    def stop(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        log.info("浏览器已关闭")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()