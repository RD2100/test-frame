"""Capability probe registry and evidence writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable

from capability.providers import adb, allure, h5, maestro, metersphere, miniapp, playwright
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
    "miniapp.devtools.path": miniapp.probe_path,
    "miniapp.devtools.cli": miniapp.probe_cli,
    "miniapp.automator.sdk": miniapp.probe_sdk,
    "miniapp.automator.endpoint": miniapp.probe_endpoint,
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


def write_evidence(results: Iterable[CapabilityResult], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "results": [result.to_dict() for result in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
