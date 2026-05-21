"""Maestro wrapper — 封装 maestro test 命令"""

import subprocess
import os
from pathlib import Path


def run(project_config: dict) -> dict:
    """执行Maestro冒烟测试，返回 {passed: bool, results: [...]}"""
    flow_dir = project_config.get("maestro", {}).get("flow_dir", "tests/android/maestro/")
    format_type = project_config.get("maestro", {}).get("format", "junit")
    output_dir = project_config.get("maestro", {}).get("output_dir", "reports/maestro/")

    os.makedirs(output_dir, exist_ok=True)

    flows = list(Path(flow_dir).glob("*.yaml")) if os.path.isdir(flow_dir) else []
    if not flows:
        print("    [WARN] No Maestro flow files found")
        return {"passed": True, "tool": "maestro", "results": []}

    results = {"passed": True, "tool": "maestro", "results": [], "failed": []}
    for flow in flows:
        flow_name = flow.stem
        print(f"    ▶ {flow_name}")
        cmd = [
            "maestro", "test",
            str(flow),
            "--format", format_type,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                results["results"].append({"name": flow_name, "status": "passed"})
            else:
                results["passed"] = False
                results["failed"].append(flow_name)
                results["results"].append({
                    "name": flow_name, "status": "failed",
                    "error": r.stderr[:500] if r.stderr else ""
                })
                print(f"      [FAIL] {r.stderr[:200]}")
        except FileNotFoundError:
            print("    [WARN] Maestro CLI not installed, skip")
            return {"passed": True, "tool": "maestro", "results": [], "skipped": True}
        except subprocess.TimeoutExpired:
            results["passed"] = False
            results["failed"].append(flow_name)
            results["results"].append({"name": flow_name, "status": "timeout"})

    return results
