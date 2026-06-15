import json
from pathlib import Path

from tools.validate_parent_canary_report import review_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "parent-canary"
PARENT_FIXTURE_DIR = Path("D:/devframe-system/integration/fixtures/parent-canary")


def _load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_parent_canary_fixture_copies_match_parent_when_available():
    for local_path in sorted(FIXTURE_DIR.glob("NEG-PARENT-*.json")):
        payload = _load(local_path)
        parent_path = Path(payload["source_parent_path"])
        assert payload["owner"] == "test-frame"
        assert payload["contract_under_test"] == "TestExecutionReport"
        assert payload["runtime_allowed"] is False
        if parent_path.exists():
            parent_payload = _load(parent_path)
            comparable = dict(payload)
            comparable.pop("source_parent_path")
            assert comparable == parent_payload


def test_dry_run_report_cannot_claim_live_e2e_pass():
    review = review_fixture(FIXTURE_DIR / "NEG-PARENT-002-dry-run-live-e2e-pass.json")

    assert review.decision == "blocked"
    assert review.negative_case_id == "NEG-PARENT-002"
    assert "dry-run profile cannot claim real environment E2E pass" in review.reasons
    assert "dry-run or synthetic report did not use real runtime" in review.reasons


def test_missing_environment_report_cannot_be_pass():
    review = review_fixture(FIXTURE_DIR / "NEG-PARENT-013-missing-env-reported-pass.json")

    assert review.decision == "blocked"
    assert review.negative_case_id == "NEG-PARENT-013"
    assert "missing or unready environment cannot be reported as pass" in review.reasons


def test_parent_canary_ids_are_limited_to_task_scope():
    ids = {
        _load(path)["negative_case_id"]
        for path in FIXTURE_DIR.glob("NEG-PARENT-*.json")
    }

    assert ids == {"NEG-PARENT-002", "NEG-PARENT-013"}
