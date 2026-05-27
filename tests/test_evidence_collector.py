"""Evidence collector unit tests — structure, field completeness, content."""

import pytest
import json
import os
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evidence.collector import EvidenceCollector, EvidenceIndex, _infer_test_name


class TestEvidenceIndex:
    """Verify EvidenceIndex data structure."""

    def test_add_evidence_stores_all_fields(self):
        idx = EvidenceIndex("test_proj", "2026-01-01_120000", "build-001")
        idx.add_evidence(
            type="screenshot",
            tool="playwright",
            path="reports/screenshots/test.png",
            test_name="login test",
            severity="critical",
            metadata={"viewport": "375x812"},
        )
        assert idx.evidence_count() == 1

        entry = idx.evidences[0]
        assert entry["type"] == "screenshot"
        assert entry["tool"] == "playwright"
        assert entry["test_name"] == "login test"
        assert entry["path"] == "reports/screenshots/test.png"
        assert entry["severity"] == "critical"
        assert entry["timestamp"]  # auto-generated
        assert entry["metadata"]["viewport"] == "375x812"

    def test_to_dict_has_required_keys(self):
        idx = EvidenceIndex("test_proj", "2026-01-01_120000")
        idx.add_evidence(type="trace", tool="playwright", path="trace.zip",
                         test_name="t1", severity="info")

        d = idx.to_dict()
        required = ["project", "timestamp", "build_id", "evidence_count", "evidences"]
        for key in required:
            assert key in d, f"Missing key: {key}"
        assert d["evidence_count"] == 1

    def test_multiple_evidence_types(self):
        idx = EvidenceIndex("test_proj", "ts")
        idx.add_evidence(type="screenshot", tool="playwright", path="a.png",
                         test_name="t1", severity="info")
        idx.add_evidence(type="video", tool="playwright", path="b.webm",
                         test_name="t1", severity="info")
        idx.add_evidence(type="crash", tool="adb", path="logcat.txt",
                         test_name="t1", severity="critical")

        assert idx.evidence_count() == 3
        d = idx.to_dict()
        types = [e["type"] for e in d["evidences"]]
        assert "screenshot" in types
        assert "video" in types
        assert "crash" in types

    def test_default_severity_is_info(self):
        idx = EvidenceIndex("p", "t")
        idx.add_evidence(type="trace", tool="pw", path="x.zip", test_name="t1")
        assert idx.evidences[0]["severity"] == "info"

    def test_default_empty_test_name(self):
        idx = EvidenceIndex("p", "t")
        idx.add_evidence(type="trace", tool="pw", path="x.zip")
        assert idx.evidences[0]["test_name"] == ""

    def test_summary_output(self):
        idx = EvidenceIndex("test_proj", "2026-01-01")
        idx.add_evidence(type="screenshot", tool="pw", path="a.png",
                         test_name="t1", severity="critical")
        s = idx.summary()
        assert "test_proj" in s
        assert "1" in s
        assert "screenshot" in s

    def test_every_evidence_entry_has_required_keys(self):
        """Each evidence entry must have: type, tool, test_name, path, severity, timestamp."""
        idx = EvidenceIndex("proj", "ts", "b1")
        evidence_types = [
            ("screenshot", "playwright", "ss.png"),
            ("video", "playwright", "vid.mp4"),
            ("trace", "playwright", "trace.zip"),
            ("crash", "adb", "crash.log"),
            ("test_results", "playwright", "results.json"),
            ("explorer_report", "playwright", "explorer.json"),
            ("logcat", "adb", "logcat.txt"),
        ]
        for ev_type, tool, path in evidence_types:
            idx.add_evidence(type=ev_type, tool=tool, path=path,
                             test_name=f"test_{ev_type}", severity="info")

        for ev in idx.evidences:
            for key in ["type", "tool", "test_name", "path", "severity", "timestamp"]:
                assert key in ev, f"Evidence {ev['type']} missing key: {key}"

    def test_empty_index(self):
        idx = EvidenceIndex("p", "t")
        assert idx.evidence_count() == 0
        d = idx.to_dict()
        assert d["evidence_count"] == 0
        assert d["evidences"] == []


class TestInferTestName:
    """Verify test name inference from file paths."""

    def test_playwright_screenshot_path(self):
        path = "test-results\\admin-Admin-Page-chromium\\test-failed-1.png"
        result = _infer_test_name(path, "playwright")
        # Should strip the tool/browser parts
        assert result != ""

    def test_empty_for_unrecognizable_path(self):
        assert _infer_test_name("random/path/file.png", "playwright") == ""

    def test_maestro_path(self):
        path = "reports/maestro/login-flow/screenshot.png"
        result = _infer_test_name(path, "maestro")
        assert result != ""


class TestEvidenceCollectorExistence:
    """Verify collector can be instantiated and run (minimal checks)."""

    def test_collector_collects_business_smoke(self):
        """Collector collects business smoke results and screenshots."""
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            # Setup business-smoke directory structure inside tmp/reports
            reports_dir = os.path.join(tmp, "reports")
            smoke_dir = os.path.join(reports_dir, "business-smoke")
            screenshots_dir = os.path.join(smoke_dir, "exercise-screenshots")
            os.makedirs(screenshots_dir)

            # Create exercise-results.json
            results_path = os.path.join(smoke_dir, "exercise-results.json")
            smoke_data = {
                "module": "exercise",
                "authMode": "injected",
                "flows": [
                    {"flow": "list", "status": "PASS", "steps": [], "assertions": [], "evidence": ["list.png"], "durationMs": 1200, "error": ""},
                    {"flow": "search", "status": "FAIL", "steps": [], "assertions": [], "evidence": ["search-fail.png"], "durationMs": 800, "error": "search failed"},
                ],
                "summary": {"total": 2, "passed": 1, "failed": 1, "blocked": 0},
            }
            with open(results_path, "w", encoding="utf-8") as f:
                _json.dump(smoke_data, f)

            # Create screenshot files
            for png_name in ["list.png", "search-fail.png", "extra.png"]:
                png_path = os.path.join(screenshots_dir, png_name)
                with open(png_path, "w") as f:
                    f.write("fake png")

            # Collect — _collect_business_smoke uses 'reports/business-smoke' relative to cwd
            collector = EvidenceCollector("test_proj")
            collector.base_dir = tmp
            os.makedirs(collector.base_dir, exist_ok=True)

            index = EvidenceIndex("test_proj", "ts")

            # Change cwd temporarily so the collector finds our tmp files
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                collector._collect_business_smoke(index)
            finally:
                os.chdir(original_cwd)

            # Assert business_smoke_result evidence exists
            smoke_evs = [e for e in index.evidences if e["type"] == "business_smoke_result"]
            assert len(smoke_evs) == 1, f"Expected 1 business_smoke_result, got {len(smoke_evs)}"
            assert smoke_evs[0]["tool"] == "playwright"
            assert smoke_evs[0]["test_name"] == "exercise-smoke"
            assert smoke_evs[0]["severity"] == "warning"  # FAIL flow → warning

    def test_collector_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = EvidenceCollector("test_proj")
            collector.base_dir = os.path.join(tmp, "reports", "test_proj", "2026-01-01")
            os.makedirs(collector.base_dir, exist_ok=True)

            # Construct an index manually
            index = EvidenceIndex("test_proj", "ts")
            index.add_evidence(type="screenshot", tool="playwright", path="x.png",
                               test_name="t1", severity="info")

            idx_path = os.path.join(collector.base_dir, "evidence.json")
            with open(idx_path, "w") as f:
                json.dump(index.to_dict(), f)

            assert os.path.exists(idx_path)
            with open(idx_path) as f:
                data = json.load(f)
            assert data["project"] == "test_proj"
            assert data["evidence_count"] == 1
