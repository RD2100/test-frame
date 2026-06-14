import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_h5_smoke_script_targets_chromium_only():
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    script = package_json["scripts"]["test:h5:smoke"]

    assert "tests/h5/smoke.spec.js" in script
    assert "--project=chromium" in script
    assert "firefox" not in script
    assert "webkit" not in script


def test_h5_smoke_fixture_is_repo_local_and_offline():
    fixture = ROOT / "examples" / "app-h5" / "index.html"
    content = fixture.read_text(encoding="utf-8")

    assert fixture.exists()
    assert "http://" not in content
    assert "https://" not in content
    assert 'data-testid="increment"' in content
    assert 'data-testid="status"' in content


def test_h5_smoke_spec_uses_file_url_and_interaction_assertion():
    spec = (ROOT / "tests" / "h5" / "smoke.spec.js").read_text(encoding="utf-8")

    assert "pathToFileURL" in spec
    assert "examples/app-h5/index.html" in spec
    assert "testInfo.project.name" in spec
    assert "toHaveText('clicked:1')" in spec
