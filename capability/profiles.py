"""Named capability profiles for explicit required environment gates."""

from __future__ import annotations


PROFILES: dict[str, tuple[str, ...]] = {
    "android.maestro.real": (
        "android.adb.cli",
        "android.adb.devices",
        "maestro.cli",
        "maestro.flow.contract",
    ),
    "miniapp.automator.real": (
        "miniapp.devtools.path",
        "miniapp.devtools.cli",
        "miniapp.automator.sdk",
        "miniapp.automator.endpoint",
    ),
    "h5.auth.staging": (
        "playwright.cli",
        "playwright.browser.chromium",
        "h5.staging.env",
        "h5.auth.env",
        "h5.auth.storage_state",
    ),
    "h5.auth.login.local": (
        "playwright.cli",
        "playwright.browser.chromium",
        "h5.auth.login.local",
        "h5.auth.storage_state.generated",
    ),
    "cloud.device.matrix.real": (
        "cloud.device.env",
        "cloud.device.matrix.contract",
    ),
    "cloud.device.provider.auth.real": (
        "cloud.device.env",
        "cloud.device.provider.auth",
    ),
    "metersphere.testplan.real": (
        "metersphere.env",
        "metersphere.real.auth",
        "metersphere.testplan.env",
    ),
}


def resolve_profile(name: str) -> list[str]:
    try:
        return list(PROFILES[name])
    except KeyError as exc:
        raise ValueError(f"Unknown capability profile: {name}") from exc
