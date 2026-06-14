"""Shared schema for capability probe results."""

from __future__ import annotations

from dataclasses import dataclass
import re
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
SENSITIVE_KEYS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "API-KEY",
    "X-API-KEY",
    "ACCESS_KEY",
    "ACCESS-KEY",
    "AUTHORIZATION",
    "BEARER",
    "COOKIE",
    "SET-COOKIE",
)

AUTHORIZATION_BEARER_RE = re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)([^\s,;]+)")
BEARER_RE = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9._~+/=-]{8,})")
KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key|access[_-]?key)=([^\s,;&]+)"
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.upper().replace("_", "-")
    return any(marker.replace("_", "-") in normalized for marker in SENSITIVE_KEYS)


def redact_string(value: str) -> str:
    text = value
    text = AUTHORIZATION_BEARER_RE.sub(r"\1" + REDACTION, text)
    text = BEARER_RE.sub(r"\1" + REDACTION, text)
    text = KEY_VALUE_SECRET_RE.sub(r"\1=" + REDACTION, text)
    return text


def redact_value(value: Any, parent_key: str | None = None) -> Any:
    if parent_key and is_sensitive_key(parent_key):
        return REDACTION
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, list):
        redacted: list[Any] = []
        redact_next = False
        for item in value:
            if redact_next:
                redacted.append(REDACTION)
                redact_next = False
                continue
            redacted_item = redact_value(item)
            redacted.append(redacted_item)
            if isinstance(item, str) and is_sensitive_key(item.lstrip("-")):
                redact_next = True
        return redacted
    if isinstance(value, dict):
        return {key: redact_value(item, str(key)) for key, item in value.items()}
    return value


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

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid capability status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "status": self.status,
            "required": self.required,
            "reason": self.reason,
            "evidence": redact_value(self.evidence),
        }

    @property
    def blocks_required_gate(self) -> bool:
        return self.required and self.status != "PASS"


def evidence_from_command(command: CommandEvidence) -> dict[str, Any]:
    return redact_value({
        "command": command.command,
        "exit_code": command.exit_code,
        "stdout": summarize(redact_string(command.stdout)),
        "stderr": summarize(redact_string(command.stderr)),
    })
