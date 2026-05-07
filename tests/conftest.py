import json
import pytest
import allure
import os
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Page
from core.config_reader import config
from core.log_factory import log
from core.allure_helper import AllureHelper


def pytest_configure(config):
    for d in ["reports/allure-results", "logs", "screenshots", "data"]:
        Path(d).mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance):
    """会话级浏览器，所有用例共用一个进程"""
    browser_type_name = config.get("browser.type", "chromium")
    headless          = config.get_bool("browser.headless", False)
    slow_mo           = config.get_int("browser.slow_mo", 0)

    launcher = getattr(playwright_instance, browser_type_name)
    _browser = launcher.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    log.info(f"浏览器已启动 | type={browser_type_name} | headless={headless}")
    yield _browser
    _browser.close()
    log.info("浏览器已关闭")


@pytest.fixture(scope="function")
def context(browser):
    """每条用例独立上下文，隔离 Cookie/Storage"""
    ctx = browser.new_context(
        viewport={
            "width":  config.get_int("browser.viewport.width",  1920),
            "height": config.get_int("browser.viewport.height", 1080),
        },
        locale=config.get("browser.locale", "zh-CN"),
        timezone_id=config.get("browser.timezone", "Asia/Shanghai"),
    )
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def page(context):
    """每条用例独立页面"""
    _page = context.new_page()
    yield _page
    _page.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report  = outcome.get_result()

    if report.when == "call" and report.failed:
        _page = item.funcargs.get("page")
        if _page:
            try:
                ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_dir  = Path(config.get("screenshot.dir", "screenshots"))
                shot_dir.mkdir(exist_ok=True)
                shot_path = shot_dir / f"FAIL_{item.name}_{ts}.png"
                data = _page.screenshot(
                    path=str(shot_path),
                    full_page=config.get_bool("screenshot.full_page", True),
                )
                AllureHelper.attach_screenshot(data, name="失败截图")
                AllureHelper.attach_html(_page.content(), name="失败时页面源码")
                allure.attach(
                    _page.url,
                    name="失败时URL",
                    attachment_type=allure.attachment_type.URI_LIST,
                )
                log.error(f"用例失败截图: {shot_path}")
            except Exception as e:
                log.warning(f"截图失败: {e}")


@pytest.fixture(scope="session")
def api_client():
    from tests.api.client.http_client import HttpClient
    return HttpClient(
        base_url=config.get("api_base_url", "https://jsonplaceholder.typicode.com")
    )


def pytest_sessionfinish(session, exitstatus):
    # 写入 Allure 环境信息
    AllureHelper.set_environment_info(
        环境=os.getenv("TEST_ENV", "dev"),
        浏览器=config.get("browser.type", "chromium"),
        目标站点=config.get("base_url", ""),
        Python=f"{__import__('sys').version.split()[0]}",
        平台=__import__("platform").platform(),
    )

    # 写入中文分类
    categories = [
        {
            "name": "产品缺陷 - 断言失败",
            "messageRegex": ".*AssertionError.*|.*assert.*",
            "matchedStatuses": ["failed"],
        },
        {
            "name": "测试代码缺陷 - 运行异常",
            "messageRegex": ".*Error.*",
            "matchedStatuses": ["broken"],
        },
        {
            "name": "超时失败",
            "messageRegex": ".*TimeoutError.*|.*timeout.*|.*Timeout.*",
            "matchedStatuses": ["failed", "broken"],
        },
        {
            "name": "API 状态码不匹配",
            "messageRegex": ".*状态码不匹配.*",
            "matchedStatuses": ["failed"],
        },
        {
            "name": "已跳过",
            "matchedStatuses": ["skipped"],
        },
    ]
    results_dir = Path("reports/allure-results")
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(results_dir / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)