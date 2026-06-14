"""Named capability profiles for explicit required environment gates."""

from __future__ import annotations


PROFILES: dict[str, tuple[str, ...]] = {
    "android.maestro.real": (
        "android.adb.cli",
        "android.adb.devices",
        "maestro.cli",
        "maestro.flow.contract",
    ),
}


def resolve_profile(name: str) -> list[str]:
    try:
        return list(PROFILES[name])
    except KeyError as exc:
        raise ValueError(f"Unknown capability profile: {name}") from exc
