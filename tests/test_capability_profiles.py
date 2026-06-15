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

TGM_MINIAPP_POSITIVE_PILOT_PREREQ_CAPABILITIES = [
    "tgm.miniapp.runtime_authorization",
    "tgm.miniapp.devtools.path",
    "tgm.miniapp.automator.package",
    "tgm.miniapp.endpoint.policy",
    "tgm.miniapp.artifact.policy",
]

METERSPHERE_TESTPLAN_CAPABILITIES = [
    "metersphere.env",
    "metersphere.real.auth",
    "metersphere.testplan.env",
]

H5_AUTH_STAGING_CAPABILITIES = [
    "playwright.cli",
    "playwright.browser.chromium",
    "h5.staging.env",
    "h5.auth.env",
    "h5.auth.storage_state",
]

H5_AUTH_LOGIN_LOCAL_CAPABILITIES = [
    "playwright.cli",
    "playwright.browser.chromium",
    "h5.auth.login.local",
    "h5.auth.storage_state.generated",
]

H5_AUTH_LOGIN_STAGING_CAPABILITIES = [
    "playwright.cli",
    "playwright.browser.chromium",
    "h5.staging.env",
    "h5.auth.env",
    "h5.auth.login.staging",
    "h5.auth.storage_state.staging.generated",
]

CLOUD_DEVICE_MATRIX_CAPABILITIES = [
    "cloud.device.env",
    "cloud.device.matrix.contract",
]

CLOUD_DEVICE_AUTH_CAPABILITIES = [
    "cloud.device.env",
    "cloud.device.provider.auth",
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


def _set_tgm_miniapp_prereq_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, TGM_MINIAPP_POSITIVE_PILOT_PREREQ_CAPABILITIES, states)


def _set_metersphere_testplan_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, METERSPHERE_TESTPLAN_CAPABILITIES, states)


def _set_h5_auth_staging_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, H5_AUTH_STAGING_CAPABILITIES, states)


def _set_h5_auth_login_local_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, H5_AUTH_LOGIN_LOCAL_CAPABILITIES, states)


def _set_h5_auth_login_staging_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, H5_AUTH_LOGIN_STAGING_CAPABILITIES, states)


def _set_cloud_device_matrix_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, CLOUD_DEVICE_MATRIX_CAPABILITIES, states)


def _set_cloud_device_auth_providers(monkeypatch, states: dict[str, tuple[str, str]]):
    _set_providers(monkeypatch, CLOUD_DEVICE_AUTH_CAPABILITIES, states)


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


def test_tgm_miniapp_positive_pilot_prereq_profile_expands_to_required_capabilities():
    assert resolve_profile("tgm.miniapp.positive_pilot.prereq") == TGM_MINIAPP_POSITIVE_PILOT_PREREQ_CAPABILITIES


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


def test_tgm_miniapp_prereq_profile_blocks_when_runtime_authorization_is_missing(monkeypatch):
    _set_tgm_miniapp_prereq_providers(
        monkeypatch,
        {"tgm.miniapp.runtime_authorization": ("BLOCKED", "missing RuntimeAuthorization")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "tgm.miniapp.positive_pilot.prereq"])

    assert result.exit_code == 1
    assert "[BLOCKED] tgm.miniapp.runtime_authorization: missing RuntimeAuthorization" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_tgm_miniapp_prereq_profile_fails_when_artifact_policy_is_outside_root(monkeypatch):
    _set_tgm_miniapp_prereq_providers(
        monkeypatch,
        {"tgm.miniapp.artifact.policy": ("FAILED", "artifact root outside allowed directory")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "tgm.miniapp.positive_pilot.prereq"])

    assert result.exit_code == 1
    assert "[FAILED] tgm.miniapp.artifact.policy: artifact root outside allowed directory" in result.output


def test_tgm_miniapp_prereq_profile_writes_structured_evidence(monkeypatch, tmp_path):
    def provider(capability: str, status: str, reason: str = "ok"):
        def run(required: bool = False) -> CapabilityResult:
            evidence = {}
            if capability == "tgm.miniapp.runtime_authorization":
                evidence["runtime_authorization"] = {
                    "value": "real_env_probe_only",
                    "permits_real_e2e": False,
                }
            if capability == "tgm.miniapp.endpoint.policy":
                evidence["endpoint_policy"] = {"configured": True, "does_not_connect_endpoint": True}
            if capability == "tgm.miniapp.artifact.policy":
                evidence["artifact_policy"] = {"within_allowed_root": True}
            return CapabilityResult(
                capability=capability,
                status=status,
                required=required,
                reason=reason,
                evidence=evidence,
            )

        return run

    monkeypatch.setattr(
        probe_module,
        "PROVIDERS",
        {
            capability: provider(capability, "PASS")
            for capability in TGM_MINIAPP_POSITIVE_PILOT_PREREQ_CAPABILITIES
        },
    )
    evidence_path = tmp_path / "tgm-miniapp-positive-pilot-prereq.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "tgm.miniapp.positive_pilot.prereq",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["profile_name"] == "tgm.miniapp.positive_pilot.prereq"
    assert payload["status"] == "PASS"
    assert payload["permits_real_e2e"] is False
    assert payload["runtime_authorization"]["value"] == "real_env_probe_only"
    assert payload["endpoint_policy"]["does_not_connect_endpoint"] is True
    assert payload["artifact_policy"]["within_allowed_root"] is True
    assert [item["capability"] for item in payload["capability_results"]] == TGM_MINIAPP_POSITIVE_PILOT_PREREQ_CAPABILITIES


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


def test_h5_auth_staging_profile_expands_to_required_capabilities():
    assert resolve_profile("h5.auth.staging") == H5_AUTH_STAGING_CAPABILITIES


def test_h5_profile_blocks_when_playwright_cli_is_missing(monkeypatch):
    _set_h5_auth_staging_providers(
        monkeypatch,
        {"playwright.cli": ("BLOCKED", "npx not found in PATH")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.staging"])

    assert result.exit_code == 1
    assert "[BLOCKED] playwright.cli: npx not found in PATH" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_h5_profile_blocks_when_chromium_is_missing(monkeypatch):
    _set_h5_auth_staging_providers(
        monkeypatch,
        {"playwright.browser.chromium": ("BLOCKED", "Chromium browser binary is not installed")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.staging"])

    assert result.exit_code == 1
    assert "[BLOCKED] playwright.browser.chromium: Chromium browser binary is not installed" in result.output


def test_h5_profile_fails_when_staging_url_is_malformed(monkeypatch):
    _set_h5_auth_staging_providers(
        monkeypatch,
        {"h5.staging.env": ("FAILED", "H5 staging base URL is not a valid http(s) URL")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.staging"])

    assert result.exit_code == 1
    assert "[FAILED] h5.staging.env: H5 staging base URL is not a valid http(s) URL" in result.output


def test_h5_profile_blocks_when_auth_env_is_missing(monkeypatch):
    _set_h5_auth_staging_providers(
        monkeypatch,
        {"h5.auth.env": ("BLOCKED", "missing H5 auth environment variables")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.staging"])

    assert result.exit_code == 1
    assert "[BLOCKED] h5.auth.env: missing H5 auth environment variables" in result.output


def test_h5_profile_blocks_when_storage_state_is_missing(monkeypatch):
    _set_h5_auth_staging_providers(
        monkeypatch,
        {"h5.auth.storage_state": ("BLOCKED", "missing H5 auth storageState path")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.staging"])

    assert result.exit_code == 1
    assert "[BLOCKED] h5.auth.storage_state: missing H5 auth storageState path" in result.output


def test_h5_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_h5_auth_staging_providers(monkeypatch, {})
    evidence_path = tmp_path / "h5.auth.staging.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "h5.auth.staging",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] h5.auth.staging" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == H5_AUTH_STAGING_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_h5_capability_all_still_allows_blocked_results(monkeypatch):
    _set_h5_auth_staging_providers(
        monkeypatch,
        {"h5.auth.storage_state": ("BLOCKED", "missing H5 auth storageState path")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] h5.auth.storage_state: missing H5 auth storageState path" in result.output
    assert "[OK] Capability check completed" in result.output


def test_h5_auth_login_local_profile_expands_to_required_capabilities():
    assert resolve_profile("h5.auth.login.local") == H5_AUTH_LOGIN_LOCAL_CAPABILITIES


def test_h5_auth_login_local_profile_blocks_when_playwright_cli_is_missing(monkeypatch):
    _set_h5_auth_login_local_providers(
        monkeypatch,
        {"playwright.cli": ("BLOCKED", "npx not found in PATH")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.login.local"])

    assert result.exit_code == 1
    assert "[BLOCKED] playwright.cli: npx not found in PATH" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_h5_auth_login_local_profile_fails_when_login_script_fails(monkeypatch):
    _set_h5_auth_login_local_providers(
        monkeypatch,
        {"h5.auth.login.local": ("FAILED", "H5 local auth login script failed")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.login.local"])

    assert result.exit_code == 1
    assert "[FAILED] h5.auth.login.local: H5 local auth login script failed" in result.output


def test_h5_auth_login_local_profile_blocks_when_generated_state_is_missing(monkeypatch):
    _set_h5_auth_login_local_providers(
        monkeypatch,
        {"h5.auth.storage_state.generated": ("BLOCKED", "H5 generated auth storageState file does not exist")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.login.local"])

    assert result.exit_code == 1
    assert "[BLOCKED] h5.auth.storage_state.generated: H5 generated auth storageState file does not exist" in result.output


def test_h5_auth_login_local_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_h5_auth_login_local_providers(monkeypatch, {})
    evidence_path = tmp_path / "h5.auth.login.local.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "h5.auth.login.local",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] h5.auth.login.local" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == H5_AUTH_LOGIN_LOCAL_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_h5_auth_login_local_capability_all_still_allows_blocked_results(monkeypatch):
    _set_h5_auth_login_local_providers(
        monkeypatch,
        {"h5.auth.login.local": ("BLOCKED", "node not found in PATH")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] h5.auth.login.local: node not found in PATH" in result.output
    assert "[OK] Capability check completed" in result.output


def test_h5_auth_login_staging_real_profile_expands_to_required_capabilities():
    assert resolve_profile("h5.auth.login.staging.real") == H5_AUTH_LOGIN_STAGING_CAPABILITIES


def test_h5_auth_login_staging_profile_blocks_when_real_login_is_not_enabled(monkeypatch):
    _set_h5_auth_login_staging_providers(
        monkeypatch,
        {"h5.auth.login.staging": ("BLOCKED", "real H5 staging login is not enabled")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.login.staging.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] h5.auth.login.staging: real H5 staging login is not enabled" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_h5_auth_login_staging_profile_blocks_when_staging_url_is_missing(monkeypatch):
    _set_h5_auth_login_staging_providers(
        monkeypatch,
        {"h5.staging.env": ("BLOCKED", "missing H5 staging base URL")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.login.staging.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] h5.staging.env: missing H5 staging base URL" in result.output


def test_h5_auth_login_staging_profile_fails_when_login_script_fails(monkeypatch):
    _set_h5_auth_login_staging_providers(
        monkeypatch,
        {"h5.auth.login.staging": ("FAILED", "H5 staging auth login script failed")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "h5.auth.login.staging.real"])

    assert result.exit_code == 1
    assert "[FAILED] h5.auth.login.staging: H5 staging auth login script failed" in result.output


def test_h5_auth_login_staging_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_h5_auth_login_staging_providers(monkeypatch, {})
    evidence_path = tmp_path / "h5.auth.login.staging.real.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "h5.auth.login.staging.real",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] h5.auth.login.staging.real" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == H5_AUTH_LOGIN_STAGING_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_h5_auth_login_staging_capability_all_still_allows_blocked_results(monkeypatch):
    _set_h5_auth_login_staging_providers(
        monkeypatch,
        {"h5.auth.login.staging": ("BLOCKED", "real H5 staging login is not enabled")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] h5.auth.login.staging: real H5 staging login is not enabled" in result.output
    assert "[OK] Capability check completed" in result.output


def test_cloud_device_matrix_real_profile_expands_to_required_capabilities():
    assert resolve_profile("cloud.device.matrix.real") == CLOUD_DEVICE_MATRIX_CAPABILITIES


def test_cloud_device_profile_blocks_when_env_is_missing(monkeypatch):
    _set_cloud_device_matrix_providers(
        monkeypatch,
        {"cloud.device.env": ("BLOCKED", "missing cloud device environment variables")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "cloud.device.matrix.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] cloud.device.env: missing cloud device environment variables" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_cloud_device_profile_blocks_when_matrix_file_is_missing(monkeypatch):
    _set_cloud_device_matrix_providers(
        monkeypatch,
        {"cloud.device.matrix.contract": ("BLOCKED", "missing cloud device matrix file path")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "cloud.device.matrix.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] cloud.device.matrix.contract: missing cloud device matrix file path" in result.output


def test_cloud_device_profile_fails_when_matrix_contract_is_malformed(monkeypatch):
    _set_cloud_device_matrix_providers(
        monkeypatch,
        {"cloud.device.matrix.contract": ("FAILED", "cloud device matrix file is not valid JSON")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "cloud.device.matrix.real"])

    assert result.exit_code == 1
    assert "[FAILED] cloud.device.matrix.contract: cloud device matrix file is not valid JSON" in result.output


def test_cloud_device_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_cloud_device_matrix_providers(monkeypatch, {})
    evidence_path = tmp_path / "cloud.device.matrix.real.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "cloud.device.matrix.real",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] cloud.device.matrix.real" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == CLOUD_DEVICE_MATRIX_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_cloud_device_capability_all_still_allows_blocked_results(monkeypatch):
    _set_cloud_device_matrix_providers(
        monkeypatch,
        {"cloud.device.env": ("BLOCKED", "missing cloud device environment variables")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] cloud.device.env: missing cloud device environment variables" in result.output
    assert "[OK] Capability check completed" in result.output


def test_cloud_device_provider_auth_real_profile_expands_to_required_capabilities():
    assert resolve_profile("cloud.device.provider.auth.real") == CLOUD_DEVICE_AUTH_CAPABILITIES


def test_cloud_device_auth_profile_blocks_when_env_is_missing(monkeypatch):
    _set_cloud_device_auth_providers(
        monkeypatch,
        {"cloud.device.env": ("BLOCKED", "missing cloud device environment variables")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "cloud.device.provider.auth.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] cloud.device.env: missing cloud device environment variables" in result.output
    assert "[FAIL] Required capability check failed" in result.output


def test_cloud_device_auth_profile_blocks_when_real_auth_is_not_enabled(monkeypatch):
    _set_cloud_device_auth_providers(
        monkeypatch,
        {"cloud.device.provider.auth": ("BLOCKED", "real cloud device auth probe is not enabled")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "cloud.device.provider.auth.real"])

    assert result.exit_code == 1
    assert "[BLOCKED] cloud.device.provider.auth: real cloud device auth probe is not enabled" in result.output


def test_cloud_device_auth_profile_fails_on_http_auth_failure(monkeypatch):
    _set_cloud_device_auth_providers(
        monkeypatch,
        {"cloud.device.provider.auth": ("FAILED", "cloud device provider auth returned HTTP 401")},
    )

    result = CliRunner().invoke(cli, ["check", "--profile", "cloud.device.provider.auth.real"])

    assert result.exit_code == 1
    assert "[FAILED] cloud.device.provider.auth: cloud device provider auth returned HTTP 401" in result.output


def test_cloud_device_auth_profile_passes_when_all_required_capabilities_pass(monkeypatch, tmp_path):
    _set_cloud_device_auth_providers(monkeypatch, {})
    evidence_path = tmp_path / "cloud.device.provider.auth.real.json"

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--profile",
            "cloud.device.provider.auth.real",
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0
    assert "[PROFILE] cloud.device.provider.auth.real" in result.output
    assert "[OK] Capability check completed" in result.output
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert [item["capability"] for item in payload["results"]] == CLOUD_DEVICE_AUTH_CAPABILITIES
    assert all(item["required"] is True for item in payload["results"])
    assert all(item["status"] == "PASS" for item in payload["results"])


def test_optional_cloud_device_auth_capability_all_still_allows_blocked_results(monkeypatch):
    _set_cloud_device_auth_providers(
        monkeypatch,
        {"cloud.device.provider.auth": ("BLOCKED", "real cloud device auth probe is not enabled")},
    )

    result = CliRunner().invoke(cli, ["check", "--capability", "all"])

    assert result.exit_code == 0
    assert "[BLOCKED] cloud.device.provider.auth: real cloud device auth probe is not enabled" in result.output
    assert "[OK] Capability check completed" in result.output
