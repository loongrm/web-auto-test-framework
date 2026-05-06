"""
解析 allure-results 目录中的 JSON 结果文件
用于提取失败用例详情并存入数据库
"""
import json
import os
from pathlib import Path
from typing import List, Dict
from core.log_factory import log


class AllureParser:

    def __init__(self, results_dir: str = "reports/allure-results"):
        self.results_dir = Path(results_dir)

    def parse_results(self) -> List[Dict]:
        """
        解析所有 *-result.json 文件
        Returns: 测试用例结果列表
        """
        if not self.results_dir.exists():
            log.warning(f"Allure 结果目录不存在: {self.results_dir}")
            return []

        cases = []
        for f in self.results_dir.glob("*-result.json"):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                case = self._parse_case(data)
                if case:
                    cases.append(case)
            except Exception as e:
                log.warning(f"解析文件失败 {f.name}: {e}")

        log.info(f"Allure 解析完成: {len(cases)} 条用例")
        return cases

    def parse_failed_cases(self) -> List[Dict]:
        """只返回失败用例"""
        return [c for c in self.parse_results() if c["status"] == "failed"]

    def get_stats(self) -> Dict:
        """统计通过/失败/跳过数量"""
        cases = self.parse_results()
        stats = {"total": len(cases), "passed": 0, "failed": 0, "skipped": 0, "broken": 0}
        for c in cases:
            status = c.get("status", "unknown")
            if status in stats:
                stats[status] += 1
        return stats

    def _parse_case(self, data: dict) -> Dict:
        """解析单个用例 JSON"""
        status = data.get("status", "unknown")
        # Allure 状态映射
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "broken": "failed",   # broken 也算 failed
            "skipped": "skipped",
            "pending": "skipped",
        }
        status = status_map.get(status, "unknown")

        # 错误信息
        status_detail = data.get("statusDetails", {})
        error_message = None
        if status == "failed":
            msg = status_detail.get("message", "")
            trace = status_detail.get("trace", "")
            error_message = f"{msg}\n{trace}".strip() if (msg or trace) else None

        # 截图附件
        screenshot_path = None
        for attachment in data.get("attachments", []):
            if attachment.get("type") in ("image/png", "image/jpeg"):
                source = attachment.get("source", "")
                if source:
                    full_path = self.results_dir / source
                    if full_path.exists():
                        screenshot_path = str(full_path)
                    break

        # 模块：从 labels 中提取 suite/feature
        module = ""
        for label in data.get("labels", []):
            if label.get("name") in ("suite", "feature", "parentSuite"):
                module = label.get("value", "")
                break

        return {
            "name":            data.get("name", "unknown"),
            "full_name":       data.get("fullName", ""),
            "status":          status,
            "duration":        round(data.get("duration", 0) / 1000, 3),  # ms → s
            "error_message":   error_message,
            "screenshot_path": screenshot_path,
            "module":          module,
        }