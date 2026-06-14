"""Shared schema for capability probe results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from capability.command import CommandEvidence


CapabilityStatus = Literal["PASS", "FAILED", "BLOCKED", "UNSUPPORTED", "NOT_REQUIRED"]
ALLOWED_STATUSES: tuple[str, ...] = (
    "PASS",
    "FAILED",
    "BLOCKED",
    "UNSUPPORTED",
    "NOT_REQUIRED",
)

REDACTION = "[REDACTED]"
SECRET_KEYS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "ACCESS_KEY")


def redact(value: str) -> str:
    text = value
    for marker in SECRET_KEYS:
        if marker in text.upper():
            return REDACTION
    return text


def summarize(text: str, limit: int = 500) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "...[truncated]"


@dataclass(frozen=True)
class CapabilityResult:
    capability: str
    status: CapabilityStatus
    required: bool
    reason: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "status": self.status,
            "required": self.required,
            "reason": self.reason,
            "evidence": self.evidence,
        }

    @property
    def blocks_required_gate(self) -> bool:
        return self.required and self.status != "PASS"


def evidence_from_command(command: CommandEvidence) -> dict[str, Any]:
    return {
        "command": command.command,
        "exit_code": command.exit_code,
        "stdout": summarize(redact(command.stdout)),
        "stderr": summarize(redact(command.stderr)),
    }
