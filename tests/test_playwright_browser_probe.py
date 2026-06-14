from capability.command import CommandEvidence
from capability.probe import PROVIDERS, required_gate_failed
from capability.providers import playwright


def test_playwright_browser_chromium_provider_is_registered():
    assert "playwright.browser.chromium" in PROVIDERS


def test_chromium_browser_probe_blocks_when_browser_binary_is_missing(monkeypatch):
    monkeypatch.setattr(playwright, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        playwright,
        "run_command",
        lambda command, timeout=30: CommandEvidence(
            command,
            1,
            "",
            "Executable doesn't exist. Please run the following command: npx playwright install chromium",
        ),
    )

    result = playwright.probe_chromium(required=True)

    assert result.status == "BLOCKED"
    assert "npx playwright install chromium" in result.reason
    assert required_gate_failed([result]) is True


def test_chromium_browser_probe_passes_after_real_launch(monkeypatch):
    monkeypatch.setattr(playwright, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        playwright,
        "run_command",
        lambda command, timeout=30: CommandEvidence(
            command,
            0,
            '{"browser":"chromium","launched":true}',
            "",
        ),
    )

    result = playwright.probe_chromium(required=True)

    assert result.status == "PASS"
    assert result.blocks_required_gate is False


def test_chromium_browser_probe_fails_non_install_launch_errors(monkeypatch):
    monkeypatch.setattr(playwright, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        playwright,
        "run_command",
        lambda command, timeout=30: CommandEvidence(command, 1, "", "segmentation fault"),
    )

    result = playwright.probe_chromium()

    assert result.status == "FAILED"
    assert result.reason == "Chromium launch probe failed"
