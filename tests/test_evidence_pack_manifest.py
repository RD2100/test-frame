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


def _write_pack(path, omit=(), manifest=None, evidence_status="BLOCKED", extra_entries=None):
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
    entries.update(extra_entries or {})
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
    assert "evidence/tgm-miniapp-positive-pilot-prereq.json" in result.scanned_files
    assert result.violations == []


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


def test_pack_with_windows_absolute_path_fails_sensitive_scan(tmp_path):
    pack = tmp_path / "local-path.zip"
    slash = chr(92)
    local_path = "D:" + slash + "devframe-system" + slash + "test-frame"
    _write_pack(pack, extra_entries={"commands/preflight.txt": f"path={local_path}\n"})

    result = validate_pack(pack)

    assert result.passed is False
    assert result.violations[0].rule == "windows_absolute_path"
    assert result.violations[0].file == "commands/preflight.txt"
    assert "[REDACTED_PATH]" in result.violations[0].excerpt_redacted
    assert local_path not in result.violations[0].excerpt_redacted


def test_pack_with_windows_forward_slash_absolute_path_fails_sensitive_scan(tmp_path):
    pack = tmp_path / "local-forward-path.zip"
    slash = "/"
    local_path = "D:" + slash + "devframe-system" + slash + "test-frame"
    _write_pack(pack, extra_entries={"git/show.patch": f"+path={local_path}\n"})

    result = validate_pack(pack)

    assert result.passed is False
    assert result.violations[0].rule == "windows_absolute_path"
    assert result.violations[0].file == "git/show.patch"
    assert "[REDACTED_PATH]" in result.violations[0].excerpt_redacted
    assert local_path not in result.violations[0].excerpt_redacted


def test_pack_with_windows_runtime_marker_path_fails_sensitive_scan(tmp_path):
    pack = tmp_path / "runtime-path.zip"
    slash = chr(92)
    runtime_path = "WindowsApp" + slash + "nodejs" + slash + "npx.cmd"
    _write_pack(pack, extra_entries={"evidence/tooling.json": json.dumps({"path": runtime_path})})

    result = validate_pack(pack)

    assert result.passed is False
    assert any(violation.rule == "windows_user_or_runtime_path" for violation in result.violations)


def test_pack_with_fake_secret_value_fails_sensitive_scan(tmp_path):
    pack = tmp_path / "secret.zip"
    secret_line = "token" + "=" + "fake-raw-value"
    bearer_line = "Authorization" + ": " + "Bearer " + "fake-raw-bearer"
    _write_pack(pack, extra_entries={"evidence/stdout.log": f"{secret_line}\n{bearer_line}\n"})

    result = validate_pack(pack)

    assert result.passed is False
    assert {violation.rule for violation in result.violations} >= {
        "secret_value",
        "authorization_bearer_secret",
    }
    assert "fake-raw-value" not in result.violations[0].excerpt_redacted


def test_pack_allows_env_names_and_redacted_values(tmp_path):
    pack = tmp_path / "allowed.zip"
    redacted_secret = "token" + "=" + "[REDACTED]"
    _write_pack(
        pack,
        extra_entries={
            "commands/verification-summary.txt": (
                "env names: CLOUD_DEVICE_TOKEN H5_AUTH_PASSWORD METERSPHERE_TOKEN\n"
                f"{redacted_secret}\n"
                "path: artifacts/tgm-miniapp-positive-pilot-prereq.json\n"
            )
        },
    )

    result = validate_pack(pack)

    assert result.passed is True
    assert result.violations == []


def test_cli_evidence_validate_reports_success(tmp_path):
    pack = tmp_path / "valid.zip"
    _write_pack(pack)

    result = CliRunner().invoke(cli, ["evidence", "validate", "--pack", str(pack)])

    assert result.exit_code == 0
    assert "[PASS] Evidence pack validation" in result.output


def test_cli_evidence_validate_reports_sensitive_scan_failure(tmp_path):
    pack = tmp_path / "secret.zip"
    secret_line = "password" + "=" + "fake-raw-value"
    _write_pack(pack, extra_entries={"evidence/stdout.log": secret_line})

    result = CliRunner().invoke(cli, ["evidence", "validate", "--pack", str(pack)])

    assert result.exit_code == 1
    assert "[FAILED] Evidence pack validation" in result.output
    assert "Sensitive/local-path violations:" in result.output
    assert "secret_value" in result.output
    assert "fake-raw-value" not in result.output
