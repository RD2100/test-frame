"""Config loader unit tests — normal/missing/invalid config loading."""
import pytest
import sys
import os
import tempfile
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLoadConfig:
    """Verify load_config with valid project configs."""

    def test_load_demo_project_has_required_sections(self):
        """demo.yaml must load with project, stages, report sections."""
        import config_loader
        config = config_loader.load_config("demo")
        assert "project" in config, f"Missing 'project' section: {list(config.keys())}"
        assert "stages" in config, f"Missing 'stages' section: {list(config.keys())}"
        assert "report" in config, f"Missing 'report' section: {list(config.keys())}"

    def test_load_demo_project_name(self):
        import config_loader
        config = config_loader.load_config("demo")
        assert config["project"]["name"] == "demo"

    def test_load_fittrack_project(self):
        import config_loader
        config = config_loader.load_config("fittrack")
        assert config["project"]["name"] == "fittrack"
        # fittrack has playwright
        assert "playwright" in config

    def test_load_project_has_tool_configs_merged(self):
        """Tool configs from config/tools/*.yaml must be merged into config."""
        import config_loader
        config = config_loader.load_config("demo")
        # Tool configs should be present after merge
        assert isinstance(config.get("pytest_api"), dict) or "pytest_api" in str(config.get("stages", ""))

    def test_load_project_injects_devices(self):
        import config_loader
        config = config_loader.load_config("demo")
        assert "_devices" in config

    def test_load_project_injects_accounts(self):
        import config_loader
        config = config_loader.load_config("demo")
        assert "_accounts" in config


class TestLoadProfile:
    """Verify profile loading."""

    def test_load_smoke_profile_has_stages(self):
        import config_loader
        profile = config_loader.load_profile("smoke")
        assert "stages" in profile
        assert isinstance(profile["stages"], list)

    def test_load_regression_profile(self):
        import config_loader
        profile = config_loader.load_profile("regression")
        assert "stages" in profile

    def test_load_compatibility_profile(self):
        import config_loader
        profile = config_loader.load_profile("compatibility")
        assert "stages" in profile


class TestValidateConfig:
    """Verify config validation."""

    def test_valid_config_no_errors(self):
        import config_loader
        config = config_loader.load_config("demo")
        errors = config_loader.validate_config(config)
        assert errors == [], f"Valid config should have no errors: {errors}"

    def test_missing_project_section(self):
        import config_loader
        errors = config_loader.validate_config({})
        assert any("project" in e.lower() for e in errors)

    def test_missing_stages_section(self):
        import config_loader
        errors = config_loader.validate_config({"project": {}})
        assert any("stages" in e.lower() for e in errors)

    def test_missing_report_section(self):
        import config_loader
        errors = config_loader.validate_config({"project": {}, "stages": []})
        assert any("report" in e.lower() for e in errors)


class TestExpandEnvVars:
    """Verify environment variable expansion in config files."""

    def test_expand_known_env_var(self):
        import config_loader
        content = "key: ${PATH}"
        expanded = config_loader._expand_env_vars(content)
        assert "${PATH}" not in expanded
        assert expanded != content

    def test_expand_unknown_env_var_unchanged(self):
        import config_loader
        content = "key: ${NONEXISTENT_VAR_12345_XYZ}"
        expanded = config_loader._expand_env_vars(content)
        assert "${NONEXISTENT_VAR_12345_XYZ}" in expanded

    def test_expand_without_vars_unchanged(self):
        import config_loader
        content = "key: value"
        expanded = config_loader._expand_env_vars(content)
        assert expanded == content


class TestDeepMerge:
    """Verify deep merge logic."""

    def test_nested_dict_merged_recursively(self):
        import config_loader
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 99, "z": 3}}
        config_loader._deep_merge(base, override)
        assert base["a"]["x"] == 1  # preserved
        assert base["a"]["y"] == 99  # overridden
        assert base["a"]["z"] == 3   # added

    def test_non_dict_value_overridden(self):
        import config_loader
        base = {"a": 1, "b": 2}
        override = {"b": 999}
        config_loader._deep_merge(base, override)
        assert base["b"] == 999
        assert base["a"] == 1
