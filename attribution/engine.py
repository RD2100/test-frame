"""缺陷归因规则引擎 — 基于规则匹配失败用例，自动推断根因"""

import os
import re
import yaml
from pathlib import Path
from datetime import datetime


class AttributionEngine:
    def __init__(self, rules_dir: str = "attribution/rules/"):
        self.rules = self._load_rules(rules_dir)

    def _load_rules(self, rules_dir: str) -> list:
        rules = []
        rules_path = Path(rules_dir)
        if not rules_path.exists():
            return rules
        for f in rules_path.glob("*.yaml"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if data and "rules" in data:
                    rules.extend(data["rules"])
            except Exception:
                continue
        return rules

    def attribute(self, test_result: dict) -> dict:
        """对单个失败用例进行归因分析"""
        error_msg = ""
        stack_trace = ""
        if test_result.get("error"):
            error_msg = test_result["error"].get("message", "")
            stack_trace = test_result["error"].get("stack_trace", "")

        text_to_search = f"{error_msg}\n{stack_trace}"

        for rule in self.rules:
            pattern = rule.get("pattern", "")
            sources = rule.get("source", [])

            search_text = ""
            if "stacktrace" in sources:
                search_text += stack_trace
            if "error_message" in sources:
                search_text += error_msg
            if "logcat" in sources:
                search_text += text_to_search

            if re.search(pattern, search_text, re.IGNORECASE):
                return {
                    "test_name": test_result.get("test_name", "unknown"),
                    "matched_rule": rule["id"],
                    "root_cause": rule.get("attribution", {}).get("root_cause", "未知"),
                    "likely_module": rule.get("attribution", {}).get("likely_module", "未知"),
                    "severity": rule.get("attribution", {}).get("severity", "P3"),
                    "suggestion": rule.get("attribution", {}).get("suggestion", "人工分析"),
                }

        # 无匹配规则
        return {
            "test_name": test_result.get("test_name", "unknown"),
            "matched_rule": None,
            "root_cause": "未匹配已知规则",
            "likely_module": "未知",
            "severity": "P3",
            "suggestion": "人工分析失败原因",
        }

    def attribute_batch(self, test_results: list[dict]) -> list[dict]:
        """批量归因"""
        return [self.attribute(r) for r in test_results if r.get("status") == "failed"]

    def generate_report(self, project_name: str, results_dir: str = None) -> str:
        """生成归因报告"""
        # 查找失败结果
        results_dir = results_dir or os.path.join("reports", project_name)
        allure_results = os.path.join(results_dir, "allure-results")

        failed_results = []
        if os.path.isdir(allure_results):
            import json
            for f in Path(allure_results).glob("*result.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if data.get("status") == "failed":
                        error_msg = ""
                        details = data.get("statusDetails", {})
                        error_msg = details.get("message", "")
                        failed_results.append({
                            "test_name": data.get("name", "unknown"),
                            "status": "failed",
                            "tool": "unknown",
                            "error": {
                                "message": error_msg,
                                "stack_trace": details.get("trace", ""),
                            }
                        })
                except Exception:
                    continue

        attributed = self.attribute_batch(failed_results) if failed_results else []

        # 生成Markdown报告
        lines = [
            f"# 缺陷归因报告 - {project_name}",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## 概览",
            f"- 失败用例总数: {len(failed_results)}",
            f"- 成功归因数: {sum(1 for a in attributed if a.get('matched_rule'))}",
            f"- 待人工分析: {sum(1 for a in attributed if not a.get('matched_rule'))}",
            "",
        ]

        if attributed:
            lines.append("## 归因详情")
            lines.append("")
            lines.append("| 用例 | 根因 | 模块 | 严重级别 | 建议修复 |")
            lines.append("|------|------|------|---------|---------|")
            for a in attributed:
                lines.append(
                    f"| {a['test_name'][:30]} | {a['root_cause'][:20]} | "
                    f"{a['likely_module'][:15]} | {a['severity']} | {a['suggestion'][:30]} |"
                )

        report = "\n".join(lines)

        # 输出报告
        output_dir = os.path.join("attribution", "output")
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(
            output_dir,
            f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"  [DOC] Attribution report: {report_path}")
        return report
