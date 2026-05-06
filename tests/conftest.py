import pytest
import allure
import os
from pathlib import Path
from datetime import datetime
from typing import Generator
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from core.config_reader import config
from core.log_factory import log
from core.allure_helper import AllureHelper


# 目录初始化
def pytest_configure(config_obj):
    """创建必要的输出目录"""
    for d in ["reports/allure-results", "logs", "screenshots", "data"]:
        Path(d).mkdir(parents=True, exist_ok=True)


# Playwright生命周期Fixtures

@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance):
    """会话级浏览器（所有用例共用一个浏览器进程）"""
    browser_type_name = config.get("browser.type", "chromium")
    headless = config.get_bool("browser.headless", False)
    slow_mo = config.get_int("browser.slow_mo", 0)

    launcher = getattr(playwright_instance, browser_type_name)
    _browser: Browser = launcher.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    log.info(f"浏览器已启动 | type={browser_type_name} | headless={headless}")

    yield _browser

    _browser.close()
    log.info("浏览器已关闭")


@pytest.fixture(scope="function")
def context(browser) -> Generator[BrowserContext, None, None]:
    """每条用例独立上下文（隔离 Cookie / localStorage）"""
    ctx = browser.new_context(
        viewport={
            "width": config.get_int("browser.viewport.width", 1920),
            "height": config.get_int("browser.viewport.height", 1080),
        },
        locale=config.get("browser.locale", "zh-CN"),
        timezone_id=config.get("browser.timezone", "Asia/Shanghai"),
        record_video_dir="reports/videos" if not config.get_bool("browser.headless") else None,
    )
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def page(context) -> Generator[Page, None, None]:
    """每条用例独立页面"""
    _page = context.new_page()
    yield _page
    _page.close()


# 失败自动截图 + Allure附件Hook

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        _page: Page = item.funcargs.get("page")
        if _page:
            try:
                # 截图
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_dir = Path(config.get("screenshot.dir", "screenshots"))
                shot_dir.mkdir(exist_ok=True)
                shot_path = shot_dir / f"FAIL_{item.name}_{ts}.png"
                screenshot_bytes = _page.screenshot(
                    path=str(shot_path),
                    full_page=config.get_bool("screenshot.full_page", True),
                )
                AllureHelper.attach_screenshot(screenshot_bytes, name="失败截图")
                AllureHelper.attach_html(_page.content(), name="失败时页面源码")
                allure.attach(
                    _page.url,
                    name="失败时URL",
                    attachment_type=allure.attachment_type.URI_LIST,
                )
                log.error(f"用例失败截图: {shot_path}")
            except Exception as e:
                log.warning(f"截图失败: {e}")


# 写入Allure环境信息
def pytest_sessionfinish(session, exitstatus):
    AllureHelper.set_environment_info(
        Environment=os.getenv("TEST_ENV", "dev"),
        Browser=config.get("browser.type", "chromium"),
        BaseURL=config.get("base_url", ""),
        Python=f"{__import__('sys').version}",
        Platform=__import__("platform").platform(),
    )


# API测试Fixtures

@pytest.fixture(scope="session")
def api_client():
    """会话级 HTTP 客户端"""
    from tests.api.client.http_client import HttpClient
    return HttpClient(base_url=config.get("api_base_url", "https://reqres.in"))