# Tool Contract v1 tests
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pytest
import yaml
from contracts.tool_contract import (
    ToolContract, CliExecution, ApiLifecycle, ApiLifecycleStep,
    NormalizationConfig, ArtifactDecl, cli_contract, api_async_contract,
)
from contracts.loader import load_contract
from contracts.validation import validate_contract


# Sample YAML for tests
PW_YAML = '''
schema_version: test-frame.tool-contract.v1
tool: playwright
display_name: Playwright
stages: [smoke, regression]
adapter:
  type: cli_json
timeout:
  total_seconds: 1800
execution:
  command:
    executable: npx
    args: [playwright, test, --reporter=json]
  stdout:
    capture: true
normalization:
  format: playwright_json
  normalizer: playwright_json_v1
  suite_name: web-e2e
  suite_type: e2e
'''

WETEST_YAML = '''
schema_version: test-frame.tool-contract.v1
tool: wetest
display_name: WeTest
stages: [regression, compatibility]
adapter:
  type: api_async_job
timeout:
  total_seconds: 7200
env:
  WETEST_API_TOKEN: ${WETEST_API_TOKEN}
auth:
  type: bearer_token
  token_env: WETEST_API_TOKEN
lifecycle:
  submit:
    method: POST
    url: https://api.wetest.example.com/v1/projects/p1/jobs
    response:
      job_id_path: $.data.jobId
      accepted_status_codes: [200, 201]
  poll:
    method: GET
    url: https://api.wetest.example.com/v1/jobs/${job_id}
    interval_seconds: 30
    max_attempts: 240
    status_path: $.data.status
    terminal_statuses:
      success: [FINISHED, PASSED]
      failed: [FAILED]
  download:
    method: GET
    url: https://api.wetest.example.com/v1/jobs/${job_id}/report
    save_as: artifacts/wetest/report.json
  parse:
    format: wetest_json
    normalizer: wetest_json_v1
normalization:
  format: wetest_json
  normalizer: wetest_json_v1
  suite_name: wetest-compat
  suite_type: mobile
'''


class TestLoadContract:
    def test_load_playwright_cli_contract(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(PW_YAML)
            f.flush()
            tc = load_contract(f.name)
        os.unlink(f.name)
        assert tc.tool == "playwright"
        assert tc.adapter_type == "cli_json"
        assert tc.timeout_seconds == 1800
        assert tc.execution.executable == "npx"
        assert tc.execution.args == ["playwright", "test", "--reporter=json"]
        assert tc.normalization.format == "playwright_json"
        assert tc.normalization.suite_name == "web-e2e"

    def test_load_wetest_async_contract(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(WETEST_YAML)
            f.flush()
            tc = load_contract(f.name)
        os.unlink(f.name)
        assert tc.tool == "wetest"
        assert tc.adapter_type == "api_async_job"
        assert tc.timeout_seconds == 7200
        assert tc.lifecycle is not None
        assert tc.lifecycle.submit.method == "POST"
        assert tc.lifecycle.submit.job_id_path == "$.data.jobId"
        assert tc.lifecycle.poll.interval_seconds == 30
        assert tc.lifecycle.poll.terminal_statuses["success"] == ["FINISHED", "PASSED"]
        assert tc.normalization.suite_type == "mobile"

    def test_load_file_contract(self):
        tc = load_contract(os.path.join(os.path.dirname(__file__), 'playwright.contract.yaml'))
        assert tc.tool == "playwright"
        assert len(tc.stages) == 2
        assert tc.artifacts[0].type == "html_report"
        assert tc.quality_signals[0].name == "regression_pass_rate"

    def test_missing_schema_version_raises(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("tool: foo")
            f.flush()
            with pytest.raises(ValueError, match='schema_version'):
                load_contract(f.name)
        os.unlink(f.name)


class TestValidateContract:
    def test_valid_cli_contract(self):
        tc = cli_contract('playwright', 'npx', ['playwright', 'test'])
        errors = validate_contract(tc)
        assert errors == []

    def test_missing_tool_name(self):
        tc = cli_contract('', 'npx', [])
        errors = validate_contract(tc)
        assert any('tool name' in e for e in errors)

    def test_missing_executable_for_cli(self):
        tc = ToolContract(tool='pw', adapter_type='cli_json')
        errors = validate_contract(tc)
        assert any('execution' in e for e in errors)

    def test_missing_submit_url_for_async(self):
        tc = api_async_contract('wetest')
        errors = validate_contract(tc)
        assert any('lifecycle.submit.url' in e or 'lifecycle' in e for e in errors)

    def test_valid_async_contract(self):
        tc = api_async_contract('wetest', adapter_type='api_async_job')
        tc.lifecycle.submit.url = 'https://api.example.com/jobs'
        tc.lifecycle.submit.job_id_path = '$.data.jobId'
        tc.normalization.format = 'wetest_json'
        tc.normalization.normalizer = 'wetest_json_v1'
        errors = validate_contract(tc)
        assert errors == []


class TestCliContractBuilder:
    def test_minimal_cli_contract(self):
        tc = cli_contract('pytest', 'python', ['-m', 'pytest'], stages=['smoke'])
        assert tc.tool == "pytest"
        assert tc.execution.executable == "python"
        assert len(tc.stages) == 1


class TestApiAsyncContractBuilder:
    def test_minimal_async_contract(self):
        tc = api_async_contract('metersphere', stages=['regression'])
        assert tc.tool == "metersphere"
        assert tc.adapter_type == "api_async_job"
        assert tc.timeout_seconds == 7200
