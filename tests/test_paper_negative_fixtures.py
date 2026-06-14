"""Paper/WriteLab redacted reviewer-pack negative fixture contract tests."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "docs" / "agent-runtime" / "negative-test-fixtures"

PAPER_FIXTURE_IDS = {
    "NEG-031": {
        "gate_level": "P1",
        "decision": "fail",
        "tag": "no-tests-run",
    },
    "NEG-032": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "fake-green",
    },
    "NEG-033": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "summary-as-final-verdict",
    },
    "NEG-034": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "artifact-outside-root",
    },
    "NEG-035": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "secret-token-stdout",
    },
    "NEG-036": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "redacted-pack-raw-paragraph",
    },
    "NEG-037": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "human-required-promoted-pass",
    },
    "NEG-038": {
        "gate_level": "P2",
        "decision": "warning",
        "tag": "missing-hash-manifest",
    },
    "NEG-039": {
        "gate_level": "P1",
        "decision": "fail",
        "tag": "missing-command-chain",
    },
    "NEG-040": {
        "gate_level": "P1",
        "decision": "fail",
        "tag": "summary-only-production-path-skipped",
    },
    "NEG-041": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "audit-zip-as-final-acceptance",
    },
    "NEG-042": {
        "gate_level": "P1",
        "decision": "fail",
        "tag": "offline-handoff-integrity-missing",
    },
    "NEG-043": {
        "gate_level": "P1",
        "decision": "fail",
        "tag": "business-manifest-incomplete",
    },
    "NEG-044": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "invalid-validation-mode",
    },
    "NEG-045": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "candidate-status-final-acceptance",
    },
    "NEG-046": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "missing-fresh-authorization-gate",
    },
    "NEG-047": {
        "gate_level": "P1",
        "decision": "fail",
        "tag": "incomplete-command-chain",
    },
    "NEG-048": {
        "gate_level": "P0",
        "decision": "blocked",
        "tag": "privacy-boundary-leak",
    },
}

REQUIRED_FIELDS = {
    "test_id",
    "scenario",
    "input_report_features",
    "expected_gate_decision",
    "expected_findings",
    "related_invariant",
    "hard_stop",
}


def _load_fixtures() -> list[dict]:
    fixtures: list[dict] = []
    for path in sorted(FIXTURE_DIR.glob("NEG-*.json")):
        fixtures.append(json.loads(path.read_text(encoding="utf-8")))
    return fixtures


def test_all_negative_fixtures_keep_core_contract_shape():
    fixtures = _load_fixtures()

    assert len(fixtures) == 48
    assert {fixture["test_id"] for fixture in fixtures} == {
        f"NEG-{index:03d}" for index in range(1, 49)
    }
    for fixture in fixtures:
        assert REQUIRED_FIELDS <= set(fixture), fixture["test_id"]
        assert fixture["expected_gate_decision"] != "pass", fixture["test_id"]
        assert fixture["expected_findings"], fixture["test_id"]


def test_paper_writelab_negative_fixtures_cover_required_canaries():
    fixtures = {
        fixture["test_id"]: fixture
        for fixture in _load_fixtures()
        if fixture.get("domain", "").startswith("paper_writelab_")
    }

    assert set(fixtures) == set(PAPER_FIXTURE_IDS)
    assert {fixture["gate_level"] for fixture in fixtures.values()} == {"P0", "P1", "P2"}

    for test_id, expected in PAPER_FIXTURE_IDS.items():
        fixture = fixtures[test_id]
        assert fixture["gate_level"] == expected["gate_level"]
        assert fixture["expected_gate_decision"] == expected["decision"]
        assert expected["tag"] in fixture["canary_tags"]
        assert fixture["contract_surface"], test_id
        assert fixture["test_frame_boundary"]["produces"] == [
            "verification evidence",
            "reviewer detection input",
        ]
        assert "final acceptance" in fixture["test_frame_boundary"]["does_not_produce"]


def test_paper_writelab_p0_fixtures_are_hard_stops():
    fixtures = {
        fixture["test_id"]: fixture
        for fixture in _load_fixtures()
        if fixture.get("domain", "").startswith("paper_writelab_")
    }

    for fixture in fixtures.values():
        if fixture["gate_level"] == "P0":
            assert fixture["hard_stop"] is True, fixture["test_id"]
            assert fixture["expected_gate_decision"] == "blocked", fixture["test_id"]
