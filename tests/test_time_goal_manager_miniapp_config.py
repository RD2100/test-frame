"""time-goal-manager MiniApp smoke contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


REPO_ROOT = Path(__file__).resolve().parents[1]
TGM_ROOT = Path("D:/time-goal-manager")
TGM_BRIDGE = TGM_ROOT / "scripts" / "testframe-miniapp-bridge.js"


def _miniapp_results(stdout: str) -> list[dict]:
    for line in stdout.splitlines():
        if line.startswith("MINIAPP_RESULTS:"):
            return json.loads(line.replace("MINIAPP_RESULTS:", "", 1))
    raise AssertionError(f"MINIAPP_RESULTS line not found in stdout: {stdout}")


def test_time_goal_manager_project_and_profile_load():
    import config_loader

    config = config_loader.load_config("time-goal-manager")
    profile = config_loader.load_profile("miniapp-smoke")

    assert config_loader.validate_config(config) == []
    assert config["project"]["name"] == "time-goal-manager"
    assert profile["stages"][0] == "miniapp-smoke"
    miniapp = config["miniapp"]
    assert miniapp["devtool_port"] == 19501
    assert miniapp["runtime_probe"] is False
    assert miniapp["force_clean_start"] is False
    assert miniapp["test_scripts"][0]["script"] == "D:/time-goal-manager/scripts/testframe-miniapp-bridge.js"


def test_time_goal_manager_dry_run_plan_lists_miniapp_smoke_stage(capsys):
    from orchestrator.engine import Orchestrator

    orch = Orchestrator(project_name="time-goal-manager", profile_name="miniapp-smoke")
    orch.print_plan()

    output = capsys.readouterr().out
    assert "Stage 0: [miniapp-smoke] -> tools: ['miniprogram-automator']" in output


def test_time_goal_manager_bridge_command_accepts_port_arg():
    import config_loader
    from cli.wrappers import miniapp

    config = config_loader.load_config("time-goal-manager")
    entry = config["miniapp"]["test_scripts"][0]
    cmd = miniapp._script_command(entry, config["miniapp"]["devtool_port"], config["miniapp"])

    assert cmd == [
        "node",
        "D:/time-goal-manager/scripts/testframe-miniapp-bridge.js",
        "--files",
        "connection,home,goals,time",
        "--bail",
        "--port",
        "19501",
    ]


def test_time_goal_manager_bridge_dry_run_outputs_structured_results():
    if not TGM_BRIDGE.exists():
        raise AssertionError(f"Bridge script not found: {TGM_BRIDGE}")

    result = subprocess.run(
        [
            "node",
            str(TGM_BRIDGE),
            "--files",
            "connection,home",
            "--dry-run",
            "--port",
            "19501",
        ],
        cwd=TGM_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    results = _miniapp_results(result.stdout)
    assert results == [
        {"name": "connection", "status": "passed", "dry_run": True},
        {"name": "home", "status": "passed", "dry_run": True},
    ]
    assert "TESTFRAME_ARTIFACT:" in result.stdout


def test_time_goal_manager_bridge_missing_devtools_env_is_not_fake_green():
    if not TGM_BRIDGE.exists():
        raise AssertionError(f"Bridge script not found: {TGM_BRIDGE}")

    env = os.environ.copy()
    env.pop("WECHAT_DEVTOOL_PATH", None)
    env.pop("WECHAT_DEVTOOLS_CLI", None)
    result = subprocess.run(
        [
            "node",
            str(TGM_BRIDGE),
            "--files",
            "connection",
            "--port",
            "19501",
        ],
        cwd=TGM_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    results = _miniapp_results(result.stdout)
    assert results == [
        {"name": "fatal", "status": "failed", "error": "WECHAT_DEVTOOL_PATH not set"}
    ]
