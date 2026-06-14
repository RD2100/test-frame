"""Small command runner used by capability probes."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandEvidence:
    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: int = 15) -> CommandEvidence:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return CommandEvidence(
            command=command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except FileNotFoundError:
        return CommandEvidence(
            command=command,
            exit_code=None,
            stdout="",
            stderr="executable not found",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandEvidence(
            command=command,
            exit_code=None,
            stdout=exc.stdout or "",
            stderr=f"command timed out after {timeout}s",
        )
