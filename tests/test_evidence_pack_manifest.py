import json
from zipfile import ZipFile

from click.testing import CliRunner

from cli.main import cli
from tools.validate_evidence_pack import validate_pack


def _manifest(evidence_path="evidence/tgm-miniapp-positive-pilot-prereq.json"):
    return {
        "task_id": "TESTFRAME-EVIDENCE-PACK-MANIFEST-A1",
        "module": "test-frame",
        "branch": "codex/adapter-negative-matrix",
        "base_head": "941819b8d251b4363777d7f2d90c10f46fa59da6",
        "final_head": "HEAD",
        "generated_at": "2026-06-15T00:00:00Z",
        "verdict_claimed_by_agent": "READY",
        "source_changes": [],
        "changed_files": [],
        "files_outside_allowed_scope": [],
        "commands": [{"command": "python -m pytest -q", "exit_code": 0, "summary": "passed"}],
        "tests": [{"command": "python -m pytest -q", "exit_code": 0, "passed": 1, "failed": 0}],
        "evidence_files": [
            {
                "path": evidence_path,
                "required": True,
                "status": "BLOCKED",
                "included_in_zip": True,
                "sensitive_scan": "clean",
            }
        ],
        "artifacts": [],
        "runtime_authorization": {
            "required": True,
            "value": "",
            "permits_real_e2e": False,
        },
        "fake_green_check": "BLOCKED evidence remains BLOCKED",
        "known_gaps": ["Not Real MiniApp E2E ready"],
        "reviewer_index_path": "REVIEWER_INDEX.md",
        "execution_report_path": "EXECUTION_REPORT.md",
    }


def _write_pack(path, omit=(), manifest=None, evidence_status="BLOCKED"):
    entries = {
        "EXECUTION_REPORT.md": "# ExecutionReport\n",
        "REVIEWER_INDEX.md": "# Reviewer Index\n",
        "STATUS_SUMMARY.md": "# Status\n",
        "commands/verification-summary.txt": "verification summary\n",
        "git/show.patch": "diff --git a/example b/example\n",
        "evidence/evidence-pack-manifest.json": json.dumps(manifest or _manifest()),
        "evidence/tgm-miniapp-positive-pilot-prereq.json": json.dumps({
            "status": evidence_status,
            "profile_name": "tgm.miniapp.positive_pilot.prereq",
            "capability_results": [],
        }),
    }
    with ZipFile(path, "w") as zip_file:
        for name, content in entries.items():
            if name not in omit:
                zip_file.writestr(name, content)


def test_valid_pack_passes_even_when_raw_evidence_is_blocked(tmp_path):
    pack = tmp_path / "evidence.zip"
    _write_pack(pack, evidence_status="BLOCKED")

    result = validate_pack(pack)

    assert result.passed is True
    assert result.raw_evidence_json == ["evidence/tgm-miniapp-positive-pilot-prereq.json"]


def test_pack_without_raw_evidence_json_fails(tmp_path):
    pack = tmp_path / "missing-raw.zip"
    _write_pack(pack, omit={"evidence/tgm-miniapp-positive-pilot-prereq.json"})

    result = validate_pack(pack)

    assert result.passed is False
    assert "missing raw evidence JSON under evidence/" in result.errors


def test_pack_without_git_patch_fails(tmp_path):
    pack = tmp_path / "missing-patch.zip"
    _write_pack(pack, omit={"git/show.patch"})

    result = validate_pack(pack)

    assert result.passed is False
    assert result.has_git_patch is False


def test_pack_without_execution_report_fails(tmp_path):
    pack = tmp_path / "missing-report.zip"
    _write_pack(pack, omit={"EXECUTION_REPORT.md"})

    result = validate_pack(pack)

    assert result.passed is False
    assert "EXECUTION_REPORT.md" in result.missing_required


def test_manifest_required_evidence_must_be_included(tmp_path):
    pack = tmp_path / "manifest-missing-evidence.zip"
    manifest = _manifest("evidence/missing.json")
    _write_pack(pack, manifest=manifest)

    result = validate_pack(pack)

    assert result.passed is False
    assert "required evidence missing from zip: evidence/missing.json" in result.errors


def test_cli_evidence_validate_reports_success(tmp_path):
    pack = tmp_path / "valid.zip"
    _write_pack(pack)

    result = CliRunner().invoke(cli, ["evidence", "validate", "--pack", str(pack)])

    assert result.exit_code == 0
    assert "[PASS] Evidence pack validation" in result.output
