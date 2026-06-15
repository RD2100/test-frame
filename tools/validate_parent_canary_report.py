"""Validate parent canary TestExecutionReport semantics for test-frame."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REAL_E2E_CLAIM_MARKERS = (
    "real MiniApp E2E passed",
    "real environment E2E pass",
    "live E2E pass",
    "final acceptance",
)


@dataclass(frozen=True)
class ParentCanaryReview:
    fixture_id: str
    negative_case_id: str
    decision: str
    reasons: list[str]
    status: str

    @property
    def passed(self) -> bool:
        return self.decision != "pass"


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _env_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("environment_summary")
    return summary if isinstance(summary, dict) else {}


def review_fixture(path: str | Path) -> ParentCanaryReview:
    payload = _load_json(path)
    report = payload.get("synthetic_input")
    if not isinstance(report, dict):
        return ParentCanaryReview(
            fixture_id=str(payload.get("fixture_id") or ""),
            negative_case_id=str(payload.get("negative_case_id") or ""),
            decision="failed",
            reasons=["synthetic_input must be an object"],
            status="failed",
        )

    reasons: list[str] = []
    status = str(report.get("status") or "").lower()
    profile = str(report.get("profile_used") or "")
    claim = str(report.get("claim") or "")
    env = _env_summary(report)
    runtime_used = env.get("runtime_used") is True
    environment_ready = env.get("environment_ready") is True

    if status == "pass" and profile in {"dry_run", "synthetic_offline"}:
        if any(marker.lower() in claim.lower() for marker in REAL_E2E_CLAIM_MARKERS):
            reasons.append("dry-run profile cannot claim real environment E2E pass")
        if not runtime_used:
            reasons.append("dry-run or synthetic report did not use real runtime")
    if status == "pass" and not environment_ready:
        reasons.append("missing or unready environment cannot be reported as pass")
    if status == "pass" and report.get("exit_code") not in {None, 0}:
        reasons.append("pass status must not use blocked or failed exit code")
    if status in {"blocked", "fail", "failed"} and report.get("exit_code") == 0:
        reasons.append("blocked or failed status must not use pass exit code")

    decision = "pass" if not reasons else "blocked"
    expected = str(payload.get("expected_result") or "").lower()
    if expected in {"blocked", "failed", "fail"} and decision == "pass":
        reasons.append("parent canary expected a non-pass decision")
        decision = expected

    return ParentCanaryReview(
        fixture_id=str(payload.get("fixture_id") or ""),
        negative_case_id=str(payload.get("negative_case_id") or ""),
        decision=decision,
        reasons=reasons,
        status=status,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a parent canary TestExecutionReport fixture.")
    parser.add_argument("fixture", help="Parent canary fixture JSON")
    args = parser.parse_args(argv)
    review = review_fixture(args.fixture)
    print(json.dumps({
        "fixture_id": review.fixture_id,
        "negative_case_id": review.negative_case_id,
        "decision": review.decision,
        "status": review.status,
        "reasons": review.reasons,
    }, ensure_ascii=False, indent=2))
    return 0 if review.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
