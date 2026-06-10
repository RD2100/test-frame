"""MiniApp preflight/profile/wrapper regression tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_SCRIPT = REPO_ROOT / "scripts" / "miniapp_route_preflight.js"
RUNTIME_PROBE_SCRIPT = REPO_ROOT / "scripts" / "miniapp_runtime_probe.js"


def _make_miniapp_project(tmp_path: Path, pages: list[str]) -> Path:
    project_root = tmp_path / "fittrack"
    miniapp_root = project_root / "miniprogram"
    miniapp_root.mkdir(parents=True)
    (project_root / "project.config.json").write_text(
        json.dumps({"miniprogramRoot": "miniprogram/"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (miniapp_root / "app.json").write_text(
        json.dumps({"pages": pages}, ensure_ascii=False),
        encoding="utf-8",
    )

    for page in pages:
        page_base = miniapp_root / Path(page)
        page_base.parent.mkdir(parents=True, exist_ok=True)
        page_base.with_suffix(".js").write_text("Page({});\n", encoding="utf-8")
        page_base.with_suffix(".wxml").write_text(
            '<view bindtap="wechatLogin"><button>Login</button></view>\n',
            encoding="utf-8",
        )

    return project_root


def _run_preflight(project_root: Path, required_routes: list[str]) -> dict:
    result = subprocess.run(
        [
            "node",
            str(PREFLIGHT_SCRIPT),
            "--project",
            str(project_root),
            "--required-routes",
            ",".join(required_routes),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def test_preflight_resolves_wechat_page_files_from_route_base(tmp_path):
    project_root = _make_miniapp_project(tmp_path, ["pages/login/login"])

    result = _run_preflight(project_root, ["pages/login/login"])

    assert result["status"] == "passed"
    assert result["missingRoutes"] == []
    assert result["missingFiles"] == []
    login_summary = result["clickableSummary"][0]
    assert login_summary["exists"] is True
    assert login_summary["wxmlPath"].endswith("pages\\login\\login.wxml") or (
        login_summary["wxmlPath"].endswith("pages/login/login.wxml")
    )
    assert login_summary["tapEvents"] == ["wechatLogin"]
    assert login_summary["buttonCount"] == 1


def test_preflight_blocks_when_required_route_is_absent(tmp_path):
    project_root = _make_miniapp_project(tmp_path, ["pages/login/login"])

    result = _run_preflight(project_root, ["pages/index/index"])

    assert result["status"] == "blocked"
    assert result["missingRoutes"] == ["pages/index/index"]
    assert result["missingFiles"] == []


def test_runtime_probe_helper_normalizes_routes():
    result = subprocess.run(
        [
            "node",
            "-e",
            (
                f"const p=require({json.dumps(str(RUNTIME_PROBE_SCRIPT))});"
                "console.log(JSON.stringify({"
                "route:p.normalizeRoute('/pages/login/login'),"
                "routes:p.uniqueRoutes(' /a,/a,b '),"
                "args:p.parseArgs(['--port','9420','--flag'])"
                "}));"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["route"] == "pages/login/login"
    assert data["routes"] == ["a", "b"]
    assert data["args"] == {"port": "9420", "flag": True}


def test_runtime_probe_artifact_path_is_attached_when_enabled(monkeypatch):
    from cli.wrappers import miniapp

    calls = []

    def fake_write(project_config, file_name, payload):
        calls.append((project_config, file_name, payload))
        return str(REPO_ROOT / "reports" / "fittrack" / "2026-06-09" / file_name)

    monkeypatch.setattr(miniapp, "_write_json_artifact", fake_write)

    probe = {"status": "blocked", "reason": "no endpoint"}
    result = miniapp._persist_runtime_probe(
        {"project": {"name": "fittrack"}, "miniapp": {"runtime_probe_artifact": True}},
        probe,
        "miniapp-runtime-probe-login-index.json",
    )

    assert result is not probe
    assert result["artifact_path"].endswith("miniapp-runtime-probe-login-index.json")
    assert "artifact_path" not in probe
    assert calls[0][1] == "miniapp-runtime-probe-login-index.json"


def test_script_result_payload_summarizes_group_result():
    from cli.wrappers import miniapp

    payload = miniapp._script_result_payload(
        {"name": "profile", "script": "tests/fittrack/miniapp/e2e_group.js"},
        SimpleNamespace(returncode=1),
        [
            {"name": "profile:page_loaded", "status": "passed", "group": "profile"},
            {"name": "profile-edit:page_loaded", "status": "failed", "group": "profile"},
        ],
    )

    assert payload["schema_version"] == "test-frame.miniapp-script-results.v1"
    assert payload["name"] == "profile"
    assert payload["status"] == "failed"
    assert payload["passed"] is False
    assert payload["failed"] == ["profile-edit:page_loaded"]
    assert payload["result_count"] == 2


def test_script_result_payload_marks_connection_loss_as_blocked():
    from cli.wrappers import miniapp

    payload = miniapp._script_result_payload(
        {"name": "tabs", "script": "tests/fittrack/miniapp/e2e_group.js"},
        SimpleNamespace(returncode=1),
        [
            {"name": "index:page_loaded", "status": "passed", "group": "tabs"},
            {
                "name": "exercise",
                "status": "failed",
                "error": "Connection closed, check if wechat web devTools is still running",
                "group": "tabs",
            },
        ],
    )

    assert payload["status"] == "blocked"
    assert payload["error_type"] == "RESOURCE_UNAVAILABLE"
    assert "connection closed" in payload["reason"]


def test_miniapp_wrapper_blocks_when_project_path_missing():
    from cli.wrappers import miniapp

    result = miniapp.run({"miniapp": {}})

    assert result["status"] == "blocked"
    assert result["error_type"] == "CONFIG_ERROR"


def test_miniapp_wrapper_reports_preflight_invalid_json_as_error(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="not-json", stderr="", returncode=0)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)

    result = miniapp.run({"miniapp": {"project_path": str(tmp_path)}})

    assert result["status"] == "error"
    assert result["error_type"] == "TOOL_PROCESS_ERROR"
    assert "invalid JSON" in result["reason"]


def test_miniapp_wrapper_blocks_when_devtools_missing_after_valid_preflight(tmp_path):
    from cli.wrappers import miniapp

    project_root = _make_miniapp_project(tmp_path, ["pages/login/login"])

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(project_root),
                "devtool_path": str(tmp_path / "missing-cli.bat"),
                "required_routes": ["pages/login/login"],
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "WeChat DevTools CLI not found"
    assert result["preflight"]["status"] == "passed"


def test_miniapp_wrapper_blocks_when_devtools_needs_port_restart(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node":
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed"}),
                stderr="",
                returncode=0,
            )
        return SimpleNamespace(
            stdout=(
                "IDE server has started on http://127.0.0.1:12652 "
                "and must be restarted on port 9420 first"
            ),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
            }
        }
    )

    assert result["status"] == "blocked"
    assert "different automation port" in result["reason"]
    assert seen_commands[1][1] == "open"
    assert "--port" in seen_commands[1]


def test_miniapp_wrapper_blocks_automator_connection_failure(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed"}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="√ auto", stderr="", returncode=0)
        return SimpleNamespace(
            stdout=(
                "MINIAPP_RESULTS:"
                + json.dumps(
                    [
                        {
                            "name": "fatal",
                            "status": "failed",
                            "error": "Failed connecting to ws://127.0.0.1:9420",
                        }
                    ]
                )
            ),
            stderr="",
            returncode=1,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "runtime_probe": False,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["error_type"] == "RESOURCE_UNAVAILABLE"
    assert result["results"][0]["name"] == "fatal"
    auto_commands = [cmd for cmd in seen_commands if cmd[0] == str(devtool_path) and cmd[1] == "auto"]
    assert auto_commands
    assert "--auto-port" in auto_commands[0]
    assert "--port" not in auto_commands[0]


def test_miniapp_wrapper_blocks_connection_closed_cascade(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="√ auto", stderr="", returncode=0)
        return SimpleNamespace(
            stdout=(
                "MINIAPP_RESULTS:"
                + json.dumps(
                    [
                        {
                            "name": "env",
                            "status": "failed",
                            "error": "Connection closed, check if wechat web devTools is still running",
                        },
                        {"name": "env:abort", "status": "skipped", "error": "automation connection closed"},
                    ]
                )
            ),
            stderr="",
            returncode=1,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "runtime_probe": False,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["error_type"] == "RESOURCE_UNAVAILABLE"
    assert "connection closed" in result["reason"]


def test_miniapp_wrapper_blocks_partial_group_when_only_failures_are_connection_closed(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        return SimpleNamespace(
            stdout=(
                "MINIAPP_RESULTS:"
                + json.dumps(
                    [
                        {"name": "profile:page_loaded", "status": "passed"},
                        {
                            "name": "body-metrics",
                            "status": "failed",
                            "error": "Connection closed, check if wechat web devTools is still running",
                        },
                    ]
                )
            ),
            stderr="",
            returncode=1,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "runtime_probe": False,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["error_type"] == "RESOURCE_UNAVAILABLE"
    assert "during MiniApp E2E" in result["reason"]


def test_miniapp_wrapper_blocks_runtime_project_mismatch(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps(
                    {
                        "status": "passed",
                        "pages": ["pages/login/login", "pages/index/index"],
                    }
                ),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="√ auto", stderr="", returncode=0)
        return SimpleNamespace(
            stdout=(
                "MINIAPP_RESULTS:"
                + json.dumps(
                    [
                        {"name": "env:page=pages/home/home", "status": "passed"},
                        {
                            "name": "env:project_mismatch",
                            "status": "failed",
                            "error": "unexpected initial page: pages/home/home",
                        },
                    ]
                )
            ),
            stderr="",
            returncode=1,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "runtime_probe": False,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["error_type"] == "RUNTIME_PROJECT_MISMATCH"
    assert "pages/home/home" in result["reason"]


def test_miniapp_wrapper_blocks_when_runtime_probe_fails(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "pages": ["pages/login/login"]}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "error_type": "RUNTIME_PROJECT_MISMATCH",
                        "reason": "MiniApp runtime opened unexpected page: pages/home/home",
                    }
                ),
                stderr="",
                returncode=2,
            )
        return SimpleNamespace(
            stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "should_not_run", "status": "passed"}]),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["error_type"] == "RUNTIME_PROJECT_MISMATCH"
    assert "pages/home/home" in result["reason"]
    assert not any("e2e_full.js" in cmd for cmd in seen_commands if cmd[0] == "node")


def test_miniapp_wrapper_persists_runtime_probe_timeout(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    artifacts = []

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "pages": ["pages/login/login"]}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1]:
            return SimpleNamespace(stdout="", stderr="", returncode=-9, timed_out=True)
        raise AssertionError(f"unexpected command: {cmd}")

    def fake_write(project_config, file_name, payload):
        artifacts.append((file_name, payload))
        return str(tmp_path / file_name)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp, "_write_json_artifact", fake_write)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "project": {"name": "fittrack"},
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "runtime_probe_artifact": True,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            },
        }
    )

    assert result["status"] == "blocked"
    assert result["runtime_probe"]["reason"] == "miniapp runtime probe timed out"
    assert result["runtime_probe"]["artifact_path"].endswith("miniapp-runtime-probe-e2e_full.json")
    assert artifacts[0][0] == "miniapp-runtime-probe-e2e_full.json"
    assert artifacts[0][1]["endpoint"] == "ws://localhost:9420"


def test_miniapp_wrapper_retries_recoverable_runtime_probe_failure(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []
    artifacts = []
    probe_calls = {"count": 0}

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "pages": ["pages/login/login"]}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1]:
            probe_calls["count"] += 1
            if probe_calls["count"] == 1:
                return SimpleNamespace(
                    stdout=json.dumps(
                        {
                            "status": "blocked",
                            "error_type": "RESOURCE_UNAVAILABLE",
                            "reason": "miniprogram-automator could not connect to ws://localhost:9420",
                        }
                    ),
                    stderr="",
                    returncode=2,
                )
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "currentPage": "pages/login/login"}),
                stderr="",
                returncode=0,
            )
        return SimpleNamespace(
            stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "login:page_loaded", "status": "passed"}]),
            stderr="",
            returncode=0,
        )

    def fake_write(project_config, file_name, payload):
        artifacts.append((file_name, payload))
        return str(tmp_path / file_name)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp, "_write_json_artifact", fake_write)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "project": {"name": "fittrack"},
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "runtime_probe_artifact": True,
                "runtime_probe_attempts": 2,
                "runtime_probe_retry_interval": 0,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            },
        }
    )

    devtool_commands = [cmd[1] for cmd in seen_commands if cmd[0] == str(devtool_path)]
    assert result["status"] == "passed"
    assert probe_calls["count"] == 2
    assert devtool_commands == ["open", "auto", "open", "auto"]
    assert result["runtime_probe"]["attempts"][0]["status"] == "blocked"
    assert result["runtime_probe"]["attempts"][1]["status"] == "passed"
    assert artifacts[-1][1]["attempts"][1]["status"] == "passed"


def test_miniapp_wrapper_does_not_retry_runtime_project_mismatch(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "pages": ["pages/login/login"]}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps(
                    {
                        "status": "blocked",
                        "error_type": "RUNTIME_PROJECT_MISMATCH",
                        "reason": "MiniApp runtime opened unexpected page: pages/home/home",
                    }
                ),
                stderr="",
                returncode=2,
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "runtime_probe_attempts": 3,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    probe_commands = [cmd for cmd in seen_commands if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1]]
    devtool_commands = [cmd for cmd in seen_commands if cmd[0] == str(devtool_path)]
    assert result["status"] == "blocked"
    assert result["error_type"] == "RUNTIME_PROJECT_MISMATCH"
    assert len(probe_commands) == 1
    assert [cmd[1] for cmd in devtool_commands] == ["open", "auto"]


def test_miniapp_wrapper_force_clean_start_runs_before_open(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == "powershell":
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="√ ok", stderr="", returncode=0)
        return SimpleNamespace(
            stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "smoke", "status": "passed"}]),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "force_clean_start": True,
                "runtime_probe": False,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "passed"
    assert seen_commands[1][0] == "powershell"
    assert "WeChatAppEx" in seen_commands[1][-1]
    assert seen_commands[2][1] == "open"
    assert seen_commands[3][1] == "auto"


def test_miniapp_wrapper_runs_multiple_test_scripts(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []
    artifacts = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "pages": ["pages/login/login"]}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "e2e_group.js" in cmd[1]:
            group = cmd[cmd.index("--group") + 1]
            if group == "login-index":
                return SimpleNamespace(
                    stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "login:page_loaded", "status": "passed"}]),
                    stderr="",
                    returncode=0,
                )
            return SimpleNamespace(
                stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "profile:page_loaded", "status": "failed"}]),
                stderr="",
                returncode=1,
            )
        raise AssertionError(f"unexpected command: {cmd}")

    def fake_write(project_config, file_name, payload):
        artifacts.append((file_name, payload))
        return str(tmp_path / file_name)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp, "_write_json_artifact", fake_write)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "runtime_probe": False,
                "results_artifact": True,
                "test_scripts": [
                    {
                        "name": "login-index",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "login-index"],
                    },
                    {
                        "name": "profile",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "profile"],
                    },
                ],
            }
        }
    )

    assert result["status"] == "failed"
    assert result["passed"] is False
    assert result["failed"] == ["profile:page_loaded"]
    assert [run["name"] for run in result["script_runs"]] == ["login-index", "profile"]
    assert result["results"][0]["group"] == "login-index"
    assert result["results"][1]["group"] == "profile"
    assert [run["artifact_path"] for run in result["script_runs"]] == [
        str(tmp_path / "miniapp-results-login-index.json"),
        str(tmp_path / "miniapp-results-profile.json"),
    ]
    assert [item[0] for item in artifacts] == [
        "miniapp-results-login-index.json",
        "miniapp-results-profile.json",
    ]
    assert artifacts[1][1]["failed"] == ["profile:page_loaded"]
    group_commands = [cmd for cmd in seen_commands if cmd[0] == "node" and "e2e_group.js" in cmd[1]]
    assert len(group_commands) == 2


def test_miniapp_wrapper_passes_automator_package_and_operation_timeout(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "endpoint": "ws://localhost:9420"}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == "node" and "e2e_group.js" in cmd[1]:
            return SimpleNamespace(
                stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "login:page_loaded", "status": "passed"}]),
                stderr="",
                returncode=0,
            )
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "automator_package": "@weapp-vite/miniprogram-automator",
                "operation_timeout_ms": 1234,
                "runtime_probe": True,
                "test_scripts": [
                    {
                        "name": "login-index",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "login-index"],
                    }
                ],
            }
        }
    )

    runtime_probe_cmd = next(cmd for cmd in seen_commands if cmd[0] == "node" and "miniapp_runtime_probe.js" in cmd[1])
    group_cmd = next(cmd for cmd in seen_commands if cmd[0] == "node" and "e2e_group.js" in cmd[1])
    assert result["status"] == "passed"
    assert runtime_probe_cmd[-4:] == [
        "--automator-package",
        "@weapp-vite/miniprogram-automator",
        "--operation-timeout-ms",
        "1234",
    ]
    assert group_cmd[-4:] == [
        "--automator-package",
        "@weapp-vite/miniprogram-automator",
        "--operation-timeout-ms",
        "1234",
    ]


def test_miniapp_wrapper_reports_results_artifact_write_failure(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        return SimpleNamespace(
            stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "login:page_loaded", "status": "passed"}]),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp, "_write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "runtime_probe": False,
                "results_artifact": True,
                "test_scripts": [
                    {
                        "name": "login-index",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "login-index"],
                    }
                ],
            }
        }
    )

    assert result["status"] == "passed"
    assert result["artifact_errors"] == [
        "failed to write miniapp results artifact: miniapp-results-login-index.json"
    ]
    assert result["script_runs"][0]["artifact_path"] is None
    assert result["script_runs"][0]["artifact_error"] == result["artifact_errors"][0]


def test_miniapp_wrapper_persists_script_timeout_result(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    artifacts = []

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        return SimpleNamespace(stdout="", stderr="", returncode=-9, timed_out=True)

    def fake_write(project_config, file_name, payload):
        artifacts.append((file_name, payload))
        return str(tmp_path / file_name)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp, "_write_json_artifact", fake_write)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "runtime_probe": False,
                "results_artifact": True,
                "test_timeout": 12,
                "test_scripts": [
                    {
                        "name": "login-index",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "login-index"],
                    }
                ],
            }
        }
    )

    assert result["status"] == "error"
    assert result["error_type"] == "TOOL_TIMEOUT"
    assert result["script_runs"][0]["artifact_path"].endswith("miniapp-results-login-index.json")
    assert artifacts[0][0] == "miniapp-results-login-index.json"
    assert artifacts[0][1]["status"] == "error"
    assert artifacts[0][1]["failed"] == ["login-index:timeout"]


def test_miniapp_wrapper_can_reopen_devtools_between_scripts(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        return SimpleNamespace(
            stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "group:page_loaded", "status": "passed"}]),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "runtime_probe": False,
                "reopen_between_scripts": True,
                "test_scripts": [
                    {"name": "first", "script": "tests/fittrack/miniapp/e2e_group.js"},
                    {"name": "second", "script": "tests/fittrack/miniapp/e2e_group.js"},
                ],
            }
        }
    )

    devtool_commands = [cmd[1] for cmd in seen_commands if cmd[0] == str(devtool_path)]
    assert result["status"] == "passed"
    assert devtool_commands == ["open", "auto", "open", "auto"]
    first_script_index = next(
        index for index, cmd in enumerate(seen_commands)
        if cmd[0] == "node" and "e2e_group.js" in cmd[1]
    )
    second_open_index = next(
        index for index, cmd in enumerate(seen_commands[first_script_index + 1:], start=first_script_index + 1)
        if cmd[0] == str(devtool_path) and cmd[1] == "open"
    )
    assert second_open_index > first_script_index


def test_miniapp_wrapper_retries_port_drift_after_force_clean(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    seen_commands = []
    open_attempts = {"count": 0}

    def fake_run(cmd, *args, **kwargs):
        seen_commands.append(cmd)
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), stderr="", returncode=0)
        if cmd[0] == "powershell":
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        if cmd[0] == str(devtool_path) and cmd[1] == "open":
            open_attempts["count"] += 1
            if open_attempts["count"] == 1:
                return SimpleNamespace(
                    stdout="IDE server has started on http://127.0.0.1:12000 and must be restarted on port 9420 first",
                    stderr="",
                    returncode=0,
                )
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == str(devtool_path) and cmd[1] == "auto":
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        return SimpleNamespace(
            stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "login:page_loaded", "status": "passed"}]),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "force_clean_start": True,
                "runtime_probe": False,
                "test_script": "tests/fittrack/miniapp/e2e_full.js",
            }
        }
    )

    assert result["status"] == "passed"
    assert open_attempts["count"] == 2
    assert [cmd[0] for cmd in seen_commands].count("powershell") == 2


def test_miniapp_wrapper_blocks_when_later_test_script_connection_closes(monkeypatch, tmp_path):
    from cli.wrappers import miniapp

    devtool_path = tmp_path / "cli.bat"
    devtool_path.write_text("", encoding="utf-8")
    artifacts = []

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "node" and "miniapp_route_preflight.js" in cmd[1]:
            return SimpleNamespace(
                stdout=json.dumps({"status": "passed", "pages": ["pages/login/login"]}),
                stderr="",
                returncode=0,
            )
        if cmd[0] == str(devtool_path):
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        if cmd[0] == "node" and "e2e_group.js" in cmd[1]:
            group = cmd[cmd.index("--group") + 1]
            if group == "login-index":
                return SimpleNamespace(
                    stdout="MINIAPP_RESULTS:" + json.dumps([{"name": "login:page_loaded", "status": "passed"}]),
                    stderr="",
                    returncode=0,
                )
            return SimpleNamespace(
                stdout=(
                    "MINIAPP_RESULTS:"
                    + json.dumps(
                        [
                            {
                                "name": "fatal",
                                "status": "failed",
                                "error": "Connection closed, check if wechat web devTools is still running",
                            }
                        ]
                    )
                ),
                stderr="",
                returncode=1,
            )
        raise AssertionError(f"unexpected command: {cmd}")

    def fake_write(project_config, file_name, payload):
        artifacts.append((file_name, payload))
        return str(tmp_path / file_name)

    monkeypatch.setattr(miniapp, "_run_command", fake_run)
    monkeypatch.setattr(miniapp, "_write_json_artifact", fake_write)
    monkeypatch.setattr(miniapp.time, "sleep", lambda seconds: None)

    result = miniapp.run(
        {
            "miniapp": {
                "project_path": str(tmp_path),
                "devtool_path": str(devtool_path),
                "devtool_port": 9420,
                "runtime_probe": False,
                "results_artifact": True,
                "test_scripts": [
                    {
                        "name": "login-index",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "login-index"],
                    },
                    {
                        "name": "profile",
                        "script": "tests/fittrack/miniapp/e2e_group.js",
                        "args": ["--group", "profile"],
                    },
                ],
            }
        }
    )

    assert result["status"] == "blocked"
    assert result["error_type"] == "RESOURCE_UNAVAILABLE"
    assert result["results"][0]["name"] == "login:page_loaded"
    assert result["results"][1]["name"] == "fatal"
    assert result["results"][1]["group"] == "profile"
    assert len(result["script_runs"]) == 2
    assert [item[0] for item in artifacts] == [
        "miniapp-results-login-index.json",
        "miniapp-results-profile.json",
    ]
    assert artifacts[1][1]["failed"] == ["fatal"]


def test_fittrack_miniapp_profile_is_explicit_opt_in():
    import config_loader

    config = config_loader.load_config("fittrack")
    profile = config_loader.load_profile("miniapp_e2e")

    smoke_stage = next(stage for stage in config["stages"] if stage["stage"] == "smoke")
    miniapp_stage = next(stage for stage in config["stages"] if stage["stage"] == "miniapp_e2e")

    assert smoke_stage["tools"] == ["pytest_api"]
    assert miniapp_stage["tools"] == ["miniprogram-automator"]
    assert [entry["name"] for entry in config["miniapp"]["test_scripts"]] == [
        "login-index",
        "training",
        "exercise",
        "profile-main",
        "profile-edit",
        "profile-body-metrics",
        "profile-personal-records",
        "workout-detail",
        "plan-edit",
        "stats",
        "seed-data",
    ]
    assert profile["stages"][0] == "miniapp_e2e"
    assert "smoke" not in profile["stages"]
