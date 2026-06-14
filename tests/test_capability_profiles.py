import json

from click.testing import CliRunner

from capability import probe as probe_module
from capability.profiles import resolve_profile
from capability.schema import CapabilityResult
from cli.main import cli


ANDROID_MAESTRO_CAPABILITIES = [
    "android.adb.cli",
    "android.adb.devices",
    "maestro.cli",
    "maestro.flow.contract",
]

MINIAPP_AUTOMATOR_CAPABILITIES = [
    "miniapp.devtools.path",
    "miniapp.devtools.cli",
    "miniapp.automator.sdk",
    "miniapp.automator.endpoint",
]

METERSPHERE_TESTPLAN_CAPABILITIES = [
    "metersphere.env",
    "metersphere.real.auth",
    "metersphere.testplan.env",
]


def _provider(capability: str, status: str, reason: str = "ok"):
    def run(required: bool = False) -> CapabilityResult:
        return CapabilityResult(
            capability=capability,
            status=status,
            required=required,
            reason=reason,
            evidence={},
        )

    return run


def _set_android_maestro_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, ANDROID_MAESTRO_CAPABILITIES, states)


def _set_miniapp_automator_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, MINIAPP_AUTOMATOR_CAPABILITIES, states)


def _set_metersphere_testplan_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, METERSPHERE_TESTPLAN_CAPABILITIES, states)


def _set_providers(monkeypatch, capabilities: list[str], states: dict[str, tuple[str, str]]):
    monkeypatch.setattr(
        probe_module,
        "PROVIDERS",
        {
            capability: _provider(capability, *states.get(capability, ("PASS", "ok")))
            for capability in capabilities
        },
    )


def test_android_maestro_real_profile_expands_to_required_capabilities():
    assert resolve_profile("android.maestro.real") == ANDROID_MAESTRO_CAPABILITIES


def test_unknown_capability_profile_exits_nonzero():
    result = CliRunner().invoke(cli, ["check", "--profile", "does.not.exist"])

    assert result.exit_code == 1
    assert "Unknown capability profile: does.not.exist" in result.output


def test_profile_blocks_when_adb_cli_is_missing(monkeypatch):
    _set_android_maestro_providers(
        monkeypatch,
        {"android.adb.cli": ("BLOCKED", "adb not found in PATH")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "android.maestro.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] android.adb.cli: adb not found in PATH" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_profile_blocks_when_no_adb_device_is_available(monkeypatch):
    _set_android_maestro_providers(
        monkeypatch,
        {"android.adb.devices": ("BLOCKED", "no adb devices detected")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "android.maestro.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] android.adb.devices: no adb devices detected" in result.output


def test_profile_blocks_when_maestro_cli_is_missing(monkeypatch):
    _set_android_maestro_providers(
        monkeypatch,
        {"maestro.cli": ("BLOCKED", "maestro not found in PATH")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "android.maestro.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] maestro.cli: maestro not found in PATH" in result.output


def test_profile_fails_when_maestro_flow_fails(monkeypatch):
    _set_android_maestro_providers(
        monkeypatch,
        {"maestro.flow.contract": ("FAILED", "maestro test returned a non-zero exit code")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "android.maestro.real"])

    assert result.exit_code == 1
    assert "[FAILED] maestro.flow.contract: maestro test returned a non-zero exit code" in result.output


def test_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_android_maestro_providers(monkeypatch, {})
    evidence_path = tmp_path / "android.maestro.real.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "android.maestro.real",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] android.maestro.real" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == ANDROID_MAESTRO_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_capability_all_still_allows_blocked_results(monkeypatch):
    monkeypatch.setattr(
        probe_module,
        "PROVIDERS",
        {"optional.blocked": _provider("optional.blocked", "BLOCKED", "not installed")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] optional.blocked: not installed" in result.output
    assert "[OK] Capability check completed" in result.output


def test_miniapp_automator_real_profile_expands_to_required_capabilities():
    assert resolve_profile("miniapp.automator.real") == MINIAPP_AUTOMATOR_CAPABILITIES


def test_miniapp_profile_blocks_when_devtools_path_is_missing(monkeypatch):
    _set_miniapp_automator_providers(
        monkeypatch,
        {"miniapp.devtools.path": ("BLOCKED", "WeChat DevTools path env is not set")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "miniapp.automator.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] miniapp.devtools.path: WeChat DevTools path env is not set" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_miniapp_profile_blocks_when_devtools_cli_is_missing(monkeypatch):
    _set_miniapp_automator_providers(
        monkeypatch,
        {"miniapp.devtools.cli": ("BLOCKED", "WeChat DevTools CLI/path env is not set")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "miniapp.automator.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] miniapp.devtools.cli: WeChat DevTools CLI/path env is not set" in result.output


def test_miniapp_profile_blocks_when_automator_sdk_is_missing(monkeypatch):
    _set_miniapp_automator_providers(
        monkeypatch,
        {"miniapp.automator.sdk": ("BLOCKED", "miniprogram automator package could not be resolved")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "miniapp.automator.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] miniapp.automator.sdk: miniprogram automator package could not be resolved" in result.output


def test_miniapp_profile_blocks_when_automator_endpoint_is_missing(monkeypatch):
    _set_miniapp_automator_providers(
        monkeypatch,
        {"miniapp.automator.endpoint": ("BLOCKED", "MINIAPP_AUTOMATOR_ENDPOINT is not set")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "miniapp.automator.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] miniapp.automator.endpoint: MINIAPP_AUTOMATOR_ENDPOINT is not set" in result.output


def test_miniapp_profile_fails_when_automator_endpoint_fails(monkeypatch):
    _set_miniapp_automator_providers(
        monkeypatch,
        {"miniapp.automator.endpoint": ("FAILED", "unexpected protocol response")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "miniapp.automator.real"])

    assert result.exit_code == 1
    assert "[FAILED] miniapp.automator.endpoint: unexpected protocol response" in result.output


def test_miniapp_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_miniapp_automator_providers(monkeypatch, {})
    evidence_path = tmp_path / "miniapp.automator.real.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "miniapp.automator.real",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] miniapp.automator.real" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == MINIAPP_AUTOMATOR_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_miniapp_capability_all_still_allows_blocked_results(monkeypatch):
    _set_miniapp_automator_providers(
        monkeypatch,
        {"miniapp.automator.endpoint": ("BLOCKED", "MINIAPP_AUTOMATOR_ENDPOINT is not set")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] miniapp.automator.endpoint: MINIAPP_AUTOMATOR_ENDPOINT is not set" in result.output
    assert "[OK] Capability check completed" in result.output


def test_metersphere_testplan_real_profile_expands_to_required_capabilities():
    assert resolve_profile("metersphere.testplan.real") == METERSPHERE_TESTPLAN_CAPABILITIES


def test_metersphere_profile_blocks_when_env_is_missing(monkeypatch):
    _set_metersphere_testplan_providers(
        monkeypatch,
        {"metersphere.env": ("BLOCKED", "missing MeterSphere environment variables")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "metersphere.testplan.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] metersphere.env: missing MeterSphere environment variables" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_metersphere_profile_blocks_when_real_auth_is_not_enabled(monkeypatch):
    _set_metersphere_testplan_providers(
        monkeypatch,
        {"metersphere.real.auth": ("BLOCKED", "real MeterSphere auth probe is not enabled")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "metersphere.testplan.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] metersphere.real.auth: real MeterSphere auth probe is not enabled" in result.output


def test_metersphere_profile_blocks_when_test_plan_id_is_missing(monkeypatch):
    _set_metersphere_testplan_providers(
        monkeypatch,
        {"metersphere.testplan.env": ("BLOCKED", "missing MeterSphere test plan id")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "metersphere.testplan.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] metersphere.testplan.env: missing MeterSphere test plan id" in result.output


def test_metersphere_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_metersphere_testplan_providers(monkeypatch, {})
    evidence_path = tmp_path / "metersphere.testplan.real.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "metersphere.testplan.real",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] metersphere.testplan.real" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == METERSPHERE_TESTPLAN_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_metersphere_capability_all_still_allows_blocked_results(monkeypatch):
    _set_metersphere_testplan_providers(
        monkeypatch,
        {"metersphere.testplan.env": ("BLOCKED", "missing MeterSphere test plan id")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] metersphere.testplan.env: missing MeterSphere test plan id" in result.output
    assert "[OK] Capability check completed" in result.output
