"""小程序自动化 wrapper — 封装 miniprogram-automator + Jest

Environment variables:
  WECHAT_DEVTOOLS_CLI — path to 微信web开发者工具 CLI (e.g., cli.bat)
                         No default fallback — if not set, test is skipped.

TODO(2026-05-26): 真实微信开发者工具依赖
  - 需要安装微信web开发者工具（Windows/macOS）并启用自动化端口
  - 设置 WECHAT_DEVTOOLS_CLI 指向 IDE 安装目录下的 cli.bat/cli
  - 测试需要 miniprogram project 路径在 project_config.miniapp.project_path
"""

import subprocess
import json
import os


def run(project_config: dict) -> dict:
    """执行微信小程序自动化测试"""
    test_dir = project_config.get("miniapp", {}).get("test_dir", "tests/miniapp/specs/")
    port = project_config.get("miniapp", {}).get("devtool_port", 9420)

    if not os.path.isdir(test_dir):
        print("    [WARN] 未找到小程序测试目录")
        return {"passed": False, "tool": "miniapp", "results": [], "skipped": True,
                "reason": f"miniapp test directory not found: {test_dir}"}

    # 启动微信开发者工具（自动化模式）
    devtool_path = os.environ.get("WECHAT_DEVTOOLS_CLI", "")
    if not devtool_path or not os.path.exists(devtool_path):
        print("    [WARN] 微信开发者工具CLI未找到，跳过")
        print("    设置 WECHAT_DEVTOOLS_CLI 环境变量指到 cli.bat")
        return {"passed": False, "tool": "miniapp", "results": [], "skipped": True,
                "reason": "WeChat DevTools CLI not found — set WECHAT_DEVTOOLS_CLI"}

    project_path = project_config.get("miniapp", {}).get("project_path", "./")
    subprocess.Popen(
        [devtool_path, "auto", "--port", str(port), "--open", project_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    import time
    time.sleep(3)

    print(f"    ▶ 小程序自动化测试")
    cmd = ["npx", "jest", test_dir, "--json"]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        results = {"passed": r.returncode == 0, "tool": "miniapp", "results": [], "failed": []}
        try:
            data = json.loads(r.stdout)
            for tr in data.get("testResults", []):
                name = tr.get("name", "unknown")
                if tr.get("status") == "failed":
                    results["failed"].append(name)
                    results["results"].append({"name": name, "status": "failed"})
                else:
                    results["results"].append({"name": name, "status": "passed"})
        except json.JSONDecodeError:
            pass
        return results
    except FileNotFoundError:
        print("    [WARN] Jest 未安装，跳过 (npm install -g jest)")
        return {"passed": False, "tool": "miniapp", "results": [], "skipped": True,
                "reason": "Jest not installed — run: npm install -g jest"}
    except subprocess.TimeoutExpired:
        return {"passed": False, "tool": "miniapp", "results": [], "skipped": True,
                "error": "timeout", "reason": "miniapp test timed out after 300s"}
