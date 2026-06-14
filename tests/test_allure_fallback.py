import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from aggregator.allure_generator import generate_allure_report
from cli.main import cli


def test_allure_cli_missing_writes_blocked_manifest(tmp_path):
    result = generate_allure_report(
        tmp_path / "allure-results",
        tmp_path / "allure-report",
        summary_path=tmp_path / "summary.json",
        path_resolver=lambda name: None,
        project_root=tmp_path,
    )

    assert result.status == "BLOCKED"
    assert Path(result.manifest_path).exists()
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["status"] == "BLOCKED"
    assert manifest["summary_path"] == str(tmp_path / "summary.json")


def test_allure_generate_nonzero_is_failed(tmp_path):
    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, stdout="ok", stderr="token=secret boom")

    result = generate_allure_report(
        tmp_path / "allure-results",
        tmp_path / "allure-report",
        path_resolver=lambda name: "allure",
        runner=fake_runner,
    )

    assert result.status == "FAILED"
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["exit_code"] == 2
    assert "secret" not in manifest["stderr"]
    assert "[REDACTED]" in manifest["stderr"]


def test_allure_exit_zero_without_index_is_failed(tmp_path):
    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="generated", stderr="")

    result = generate_allure_report(
        tmp_path / "allure-results",
        tmp_path / "allure-report",
        path_resolver=lambda name: "allure",
        runner=fake_runner,
    )

    assert result.status == "FAILED"
    assert "index.html" in result.reason


def test_allure_exit_zero_with_index_is_pass(tmp_path):
    def fake_runner(command, **kwargs):
        report_dir = Path(command[command.index("-o") + 1])
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="generated", stderr="")

    result = generate_allure_report(
        tmp_path / "allure-results",
        tmp_path / "allure-report",
        path_resolver=lambda name: "allure",
        runner=fake_runner,
    )

    assert result.status == "PASS"
    assert result.html_path.endswith("index.html")


def test_report_cli_does_not_claim_html_generated_when_allure_is_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("aggregator.collector.collect_all_results", lambda project_config: [])
    monkeypatch.setattr(
        "aggregator.collector.generate_allure_report",
        lambda results_dir, report_dir, summary_path=None: generate_allure_report(
            results_dir,
            report_dir,
            summary_path=summary_path,
            path_resolver=lambda name: None,
            project_root=tmp_path,
        ),
    )

    result = CliRunner().invoke(cli, ["report", "--project", "app-h5", "--output", str(tmp_path / "reports")])

    assert result.exit_code == 0
    assert "[BLOCKED] Allure HTML not generated" in result.output
    assert "[OK] Report generated" not in result.output
    assert "Allure HTML generated" not in result.output
