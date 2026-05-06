"""
Allure 报告辅助工具
封装常用的 attach 操作
"""
import json
import allure
from pathlib import Path
from typing import Any


class AllureHelper:

    @staticmethod
    def attach_screenshot(screenshot_bytes: bytes, name: str = "截图"):
        allure.attach(
            screenshot_bytes,
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )

    @staticmethod
    def attach_screenshot_file(path: str, name: str = "截图"):
        with open(path, "rb") as f:
            allure.attach(
                f.read(),
                name=name,
                attachment_type=allure.attachment_type.PNG,
            )

    @staticmethod
    def attach_html(html: str, name: str = "页面源码"):
        allure.attach(html, name=name, attachment_type=allure.attachment_type.HTML)

    @staticmethod
    def attach_json(data: Any, name: str = "数据"):
        text = json.dumps(data, ensure_ascii=False, indent=2) if not isinstance(data, str) else data
        allure.attach(text, name=name, attachment_type=allure.attachment_type.JSON)

    @staticmethod
    def attach_text(text: str, name: str = "文本"):
        allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)

    @staticmethod
    def attach_log_file(log_path: str, name: str = "执行日志"):
        p = Path(log_path)
        if p.exists():
            with open(p, encoding="utf-8", errors="replace") as f:
                allure.attach(f.read(), name=name, attachment_type=allure.attachment_type.TEXT)

    @staticmethod
    def set_environment_info(**kwargs):
        """
        写入环境信息到 Allure 报告（在 conftest session 结束时调用）
        会生成 environment.properties 文件
        """
        results_dir = Path("reports/allure-results")
        results_dir.mkdir(parents=True, exist_ok=True)
        env_file = results_dir / "environment.properties"
        with open(env_file, "w", encoding="utf-8") as f:
            for k, v in kwargs.items():
                f.write(f"{k}={v}\n")