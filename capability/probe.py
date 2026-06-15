"""Capability probe registry and evidence writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable

from capability.providers import adb, allure, cloud_device, h5, maestro, metersphere, miniapp, playwright
from capability.schema import CapabilityResult


Provider = Callable[[bool], CapabilityResult]

PROVIDERS: dict[str, Provider] = {
    "android.adb.cli": adb.probe_cli,
    "android.adb.devices": adb.probe_devices,
    "maestro.cli": maestro.probe_cli,
    "maestro.flow.contract": maestro.probe_flow_contract,
    "allure": allure.probe,
    "playwright.cli": playwright.probe,
    "playwright.browser.chromium": playwright.probe_chromium,
    "h5.staging.env": h5.probe_staging_env,
    "h5.auth.env": h5.probe_auth_env,
    "h5.auth.storage_state": h5.probe_auth_storage_state,
    "h5.auth.login.local": h5.probe_auth_login_local,
    "h5.auth.storage_state.generated": h5.probe_auth_storage_state_generated,
    "h5.auth.login.staging": h5.probe_auth_login_staging,
    "h5.auth.storage_state.staging.generated": h5.probe_auth_storage_state_staging_generated,
    "cloud.device.env": cloud_device.probe_env,
    "cloud.device.matrix.contract": cloud_device.probe_matrix_contract,
    "cloud.device.provider.fake": cloud_device.probe_provider_fake,
    "cloud.device.provider.auth": cloud_device.probe_provider_auth,
    "miniapp.devtools.path": miniapp.probe_path,
    "miniapp.devtools.cli": miniapp.probe_cli,
    "miniapp.automator.sdk": miniapp.probe_sdk,
    "miniapp.automator.endpoint": miniapp.probe_endpoint,
    "tgm.miniapp.runtime_authorization": miniapp.probe_tgm_runtime_authorization,
    "tgm.miniapp.devtools.path": miniapp.probe_tgm_devtools_path,
    "tgm.miniapp.automator.package": miniapp.probe_tgm_automator_package,
    "tgm.miniapp.endpoint.policy": miniapp.probe_tgm_endpoint_policy,
    "tgm.miniapp.artifact.policy": miniapp.probe_tgm_artifact_policy,
    "metersphere.env": metersphere.probe_env,
    "metersphere.fake.contract": metersphere.probe_fake_contract,
    "metersphere.real.auth": metersphere.probe_real_auth,
    "metersphere.testplan.env": metersphere.probe_testplan_env,
}


def resolve_names(names: Iterable[str] | None) -> list[str]:
    if not names:
        return list(PROVIDERS)
    resolved: list[str] = []
    for name in names:
        if name == "all":
            resolved.extend(PROVIDERS)
        else:
            resolved.append(name)
    unknown = [name for name in resolved if name not in PROVIDERS]
    if unknown:
        raise ValueError(f"Unknown capability: {', '.join(unknown)}")
    return list(dict.fromkeys(resolved))


def run_probes(names: Iterable[str] | None = None, required: Iterable[str] | None = None) -> list[CapabilityResult]:
    required_set = set(required or [])
    resolved = resolve_names(names)
    unknown_required = sorted(required_set - set(PROVIDERS))
    if unknown_required:
        raise ValueError(f"Unknown required capability: {', '.join(unknown_required)}")
    missing_required = sorted(required_set - set(resolved))
    if missing_required:
        raise ValueError(
            "Required capabilities were not selected by --capability: "
            + ", ".join(missing_required)
        )
    return [PROVIDERS[name](name in required_set) for name in resolved]


def required_gate_failed(results: Iterable[CapabilityResult]) -> bool:
    return any(result.blocks_required_gate for result in results)


def _overall_status(results: list[CapabilityResult]) -> str:
    statuses = {result.status for result in results}
    if "FAILED" in statuses:
        return "FAILED"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if statuses == {"PASS"}:
        return "PASS"
    return "BLOCKED" if statuses else "BLOCKED"


def _first_reason(results: list[CapabilityResult], status: str) -> str:
    for result in results:
        if result.status == status:
            return result.reason
    return ""


def _find_evidence(results: list[CapabilityResult], key: str) -> object | None:
    for result in results:
        if key in result.evidence:
            return result.evidence[key]
    return None


def write_evidence(
    results: Iterable[CapabilityResult],
    output_path: str | Path,
    profile_name: str | None = None,
    command_invoked: list[str] | None = None,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result_list = list(results)
    payload = {
        "schema_version": "1.0.0",
        "results": [result.to_dict() for result in result_list],
    }
    if profile_name:
        payload.update({
            "profile_name": profile_name,
            "status": _overall_status(result_list),
            "blocked_reason": _first_reason(result_list, "BLOCKED"),
            "failed_reason": _first_reason(result_list, "FAILED"),
            "capability_results": payload["results"],
            "runtime_authorization": _find_evidence(result_list, "runtime_authorization"),
            "permits_real_e2e": False,
            "artifact_policy": _find_evidence(result_list, "artifact_policy"),
            "endpoint_policy": _find_evidence(result_list, "endpoint_policy"),
            "command_invoked": command_invoked or [],
        })
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
