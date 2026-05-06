"""
Postman Collection 执行器（通过 Newman CLI）
需先安装 Node.js 并执行: npm install -g newman newman-reporter-htmlextra
"""
import json
import subprocess
import shutil
import allure
from pathlib import Path
from core.log_factory import log


class PostmanRunner:

    def __init__(self, collection_path: str, env_file: str = None):
        self.collection_path = Path(collection_path)
        self.env_file = env_file
        self.report_dir = Path("reports/newman")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, folder: str = None, iterations: int = 1) -> dict:
        """
        执行 Postman Collection
        Returns: 执行统计结果字典
        """
        if not shutil.which("newman"):
            log.warning("Newman 未安装，跳过 Postman 执行。请运行: npm install -g newman")
            return {}

        result_json = self.report_dir / "result.json"
        html_report = self.report_dir / "report.html"

        cmd = [
            "newman", "run", str(self.collection_path),
            "--reporters", "cli,json",
            f"--reporter-json-export={result_json}",
            "--iteration-count", str(iterations),
        ]

        if self.env_file:
            cmd += ["--environment", self.env_file]
        if folder:
            cmd += ["--folder", folder]

        # 如果安装了 htmlextra reporter
        if shutil.which("newman") and self._has_htmlextra():
            cmd += ["--reporters", "cli,json,htmlextra", f"--reporter-htmlextra-export={html_report}"]

        log.info(f"执行 Newman: {' '.join(cmd)}")

        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        log.info(proc.stdout[-2000:] if proc.stdout else "(无输出)")

        if result_json.exists():
            with open(result_json, encoding="utf-8") as f:
                data = json.load(f)
            stats = data.get("run", {}).get("stats", {})
            self._attach_allure(stats, html_report)
            return stats

        return {}

    def _has_htmlextra(self) -> bool:
        result = subprocess.run(
            ["npm", "list", "-g", "newman-reporter-htmlextra"],
            capture_output=True, text=True
        )
        return "newman-reporter-htmlextra" in result.stdout

    def _attach_allure(self, stats: dict, html_path: Path):
        req = stats.get("requests", {})
        asrt = stats.get("assertions", {})
        summary = (
            f"请求总数: {req.get('total', 0)}\n"
            f"请求失败: {req.get('failed', 0)}\n"
            f"断言总数: {asrt.get('total', 0)}\n"
            f"断言失败: {asrt.get('failed', 0)}\n"
        )
        allure.attach(summary, name="Newman 执行摘要", attachment_type=allure.attachment_type.TEXT)
        if html_path.exists():
            with open(html_path, encoding="utf-8") as f:
                allure.attach(f.read(), name="Newman HTML 报告", attachment_type=allure.attachment_type.HTML)