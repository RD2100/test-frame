"""Unit tests for quality gate logic (orchestrator.gate)."""

import pytest

from orchestrator.gate import evaluate, load_gate_config


class TestGateMinEvidenceCount:
    """Risk 4: Gate min_evidence_count properly blocks insufficient evidence."""

    def test_min_evidence_blocks_when_below_min(self, monkeypatch):
        """Gate fails when evidence count is below the configured minimum."""
        fake_gate = {
            "gates": {
                "pr": {"min_evidence_count": {"min": 5}},
            }
        }
        monkeypatch.setattr(
            "orchestrator.gate.load_gate_config",
            lambda gate_type: fake_gate["gates"].get(gate_type, {}),
        )

        passed, failures, _ = evaluate("pr", [{"status": "passed"}], crash_count=0)
        assert not passed
        assert any("min_evidence_count" in f for f in failures)

    def test_min_evidence_passes_when_above_min(self, monkeypatch):
        """Gate passes when evidence count meets the configured minimum."""
        fake_gate = {
            "gates": {
                "pr": {"min_evidence_count": {"min": 1}},
            }
        }
        monkeypatch.setattr(
            "orchestrator.gate.load_gate_config",
            lambda gate_type: fake_gate["gates"].get(gate_type, {}),
        )

        passed, failures, _ = evaluate(
            "pr",
            [{"status": "passed"}, {"status": "passed"}, {"status": "failed"}],
            crash_count=0,
        )
        assert passed
        assert len(failures) == 0
