# Decision Log

## 2026-06-09 - Persist page-group results and timeout evidence

Module: MiniApp wrapper / evidence

Decision: Save each page-group `MINIAPP_RESULTS` payload to `reports/<project>/<date>/miniapp-results-<group>.json` when `miniapp.results_artifact` is enabled. Also write synthetic artifacts for runtime-probe timeout and script timeout paths.

Reason: A blocked or timed-out MiniApp run must still leave reviewable evidence. Without result artifacts, reviewers cannot tell which page groups passed, failed, timed out, or never ran.

Evidence:
- `tests/test_miniapp_integration.py::test_miniapp_wrapper_persists_script_timeout_result`
- `tests/test_miniapp_integration.py::test_miniapp_wrapper_persists_runtime_probe_timeout`
- `reports/fittrack/2026-06-09/miniapp-results-login-index.json`

Status: accepted

## 2026-06-09 - Treat DevTools connection loss as environment blocked

Module: MiniApp wrapper status classification

Decision: If all failed records in a page group are DevTools connection-loss errors, classify the wrapper result as `blocked` with `RESOURCE_UNAVAILABLE`, even if earlier checks in the same group passed.

Reason: Partial success followed by `Connection closed` indicates the automation environment became unavailable. Treating it as app failure would create false red product defects.

Evidence:
- `tests/test_miniapp_integration.py::test_miniapp_wrapper_blocks_partial_group_when_only_failures_are_connection_closed`

Status: accepted

## 2026-06-09 - Force clean includes WeChatAppEx runtime

Module: MiniApp DevTools process cleanup

Decision: Include `WeChatAppEx` in the force-clean process-name list for MiniApp E2E.

Reason: Real process inspection showed stale MiniApp runtime processes named `WeChatAppEx.exe` under Tencent WMPF runtime paths, not under the WeChat DevTools install directory. The previous path-prefix cleanup could miss them and leave the automation port drifting.

Evidence:
- `Get-Process ...` showed multiple `WeChatAppEx` processes.
- `tests/test_miniapp_integration.py::test_miniapp_wrapper_force_clean_start_runs_before_open` asserts the cleanup script includes `WeChatAppEx`.

Status: accepted

## 2026-06-09 - Run MiniApp E2E as page groups

Module: MiniApp automation wrapper

Decision: Support `miniapp.test_scripts` as an ordered list of page-group scripts. The wrapper runs a runtime probe before each group, aggregates `MINIAPP_RESULTS`, and preserves partial results if a later group becomes `blocked`.

Reason: A single long MiniApp E2E process is too fragile against WeChat DevTools connection loss. Page groups reduce the failure blast radius and make the blocked boundary reviewable.

Evidence:
- `tests/test_miniapp_integration.py::test_miniapp_wrapper_runs_multiple_test_scripts`
- `tests/test_miniapp_integration.py::test_miniapp_wrapper_blocks_when_later_test_script_connection_closes`
- `python -m pytest tests\test_miniapp_integration.py -q` -> 16 passed.
- Real run generated probe artifacts for `login-index`, `tabs`, and `exercise`.

Status: accepted

## 2026-06-09 - Persist MiniApp runtime probes as report artifacts

Module: MiniApp wrapper / reports

Decision: When `miniapp.runtime_probe_artifact` is enabled, write runtime probe JSON to `reports/<project>/<date>/miniapp-runtime-probe-<group>.json`.

Reason: CLI stage output intentionally stays concise, but MiniApp environment failures need structured evidence for endpoint, current page, expected routes, and error type.

Evidence:
- `tests/test_miniapp_integration.py::test_runtime_probe_artifact_path_is_attached_when_enabled`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-tabs.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-exercise.json`

Status: accepted

## 2026-06-09 - Runtime probe gates MiniApp E2E before full suite

Module: FitTrack MiniApp E2E

Decision: Run `scripts/miniapp_runtime_probe.js` after DevTools `open/auto` and before the long MiniApp E2E script. If the probe cannot connect, sees a stale runtime, or loses connection, the wrapper returns `blocked` instead of executing the full suite.

Reason: Prior runs showed DevTools can attach to stale windows, wrong ports, or a closing connection. Running the full 13-page E2E in that state produces noisy false failures and can hang the pipeline. A short runtime identity probe is a stronger precondition.

Evidence:
- `python -m cli.main run --project fittrack --profile miniapp_e2e` now fails fast in 59s at runtime probe instead of hanging for 10 minutes.
- `tests/test_miniapp_integration.py` covers runtime probe blocked behavior and confirms full E2E is not invoked when probe fails.

Status: accepted

## 2026-06-09 - Use temp-file capture for DevTools wrapper commands

Module: MiniApp wrapper process execution

Decision: `cli/wrappers/miniapp.py` uses `_run_command()` with stdout/stderr redirected to temporary files instead of `capture_output=True`.

Reason: On Windows, WeChat DevTools CLI spawns long-lived child processes that can inherit stdout/stderr pipes. Pipe inheritance can keep `subprocess.run(..., capture_output=True)` waiting even after the CLI action should have concluded. File redirection lets the wrapper wait on the direct command and still collect output.

Evidence:
- A previous `miniapp_e2e` run exceeded the 10-minute tool timeout and left a `python -m cli.main run --project fittrack --profile miniapp_e2e` process plus child Node processes.
- After the change, `miniapp_e2e` returned a controlled runtime-probe `BLOCKED` result in 59s.

Status: accepted

## 2026-06-09 - MiniApp E2E is opt-in and environment failures are explicit

Module: FitTrack MiniApp E2E

Decision: Add a dedicated `miniapp_e2e` profile and keep FitTrack smoke on `pytest_api` only. MiniApp prerequisites and runtime mismatches return `blocked` or `error`; real page assertion failures return `failed`.

Reason: WeChat DevTools automation is stateful and can attach to stale project windows or wrong ports. Folding this into default smoke would create noisy failures and false confidence. An explicit profile lets the team iterate on real MiniApp coverage while preserving the stable API smoke gate.

Evidence:
- `config/profiles/miniapp_e2e.yaml` contains only `miniapp_e2e`, evidence/report/attribution/gate stages.
- `python -m cli.main run --project fittrack --profile smoke` -> PASS/gate PASS after MiniApp changes.
- `tests/test_miniapp_integration.py::test_fittrack_miniapp_profile_is_explicit_opt_in` verifies smoke is not polluted.

Status: accepted

## 2026-06-09 - Use `localhost` and `--auto-port` for WeChat automator

Module: MiniApp automation wrapper/scripts

Decision: Start DevTools automation with `cli.bat auto --auto-port <port>` and connect `miniprogram-automator` to `ws://localhost:<port>`.

Reason: Local probes showed `127.0.0.1:9420` can fail or hit the wrong listener while `localhost:9420` and `[::1]:9420` connected to the target runtime. The installed `miniprogram-automator@0.12.1` launcher source also uses `--auto-port`, not `--port`, for the automator WebSocket.

Evidence:
- `npm view miniprogram-automator version` -> `0.12.1`; no newer package is available.
- Local probe: `ws://localhost:9420` connected to `pages/login/login`; `ws://127.0.0.1:9420` failed or reached stale state.
- `python -m pytest tests\test_miniapp_integration.py -q` -> 11 passed, including `--auto-port` assertion.

Status: accepted

## 2026-06-09 - Stage result sidecar filtering has one shared source

Module: orchestrator / aggregator / report

Decision: Use `schema.stage_results` as the single helper for identifying and iterating public stage tool results. Sidecar keys ending in `_status`, `_detail`, `_canonical`, and `_canonical_error` are internal and must not be treated as tools by gate, report, blocker, or environment block code.

Reason: The same filtering rule had already been duplicated in multiple modules, and `aggregator.report` only filtered `_status`. That left a P2 class of false report/blocker noise where `_detail` or `_canonical_error` could appear as tool names.

Evidence:
- `python -m pytest tests\test_stage_results_schema.py tests\test_aggregator_collector.py tests\test_regression_report.py tests\test_gate_semantics.py tests\test_orchestrator_engine.py tests\test_stage_status.py -q` -> 109 passed.
- FitTrack generated Markdown contains no `_detail`, `_canonical`, or `canonical_error` matches.

Status: accepted

## 2026-06-09 - Preserve canonical status while mapping Allure status

Module: aggregator collector / Allure writer

Decision: Internal statuses remain six-state canonical values, but Allure JSON output maps `blocked`, `error`, and `cancelled` to Allure `broken`. The original internal value is preserved in a `canonical_status` label.

Reason: Allure consumers expect a smaller status vocabulary. Writing internal statuses directly risks invalid or misleading report rendering, while losing the internal status would make later debugging harder.

Evidence:
- `tests/test_aggregator_collector.py::TestAllureStatusMapping` verifies the mapping and label preservation.

Status: accepted

## 2026-06-09 - Report/Gate 使用 orchestrator stage results 作为当前流水线单一数据源

模块名称：aggregator/report/gate pipeline

Worker：Codex 主控

决策：
当 `collect_and_generate()` 收到 `stage_results` 时，report 结果由当前 orchestrator stage/tool 状态转换而来；只有旧 `tf report` 入口没有运行上下文时，才 fallback 到 adapters 收集历史结果。

决策原因：
独立回归验证发现 `fittrack smoke` pipeline 和 gate 通过，但 regression report 混入历史 adapter 失败，形成 P1 级报告/门禁不一致。质量门禁和报告必须同源，否则会产生假红或误导决策。

影响路径：
- `aggregator/collector.py`
- `orchestrator/stage.py`
- `orchestrator/engine.py`

验证命令：
- `python -m cli.main run --project fittrack --profile smoke`
- 读取 `reports/fittrack/2026-06-09/regression-summary.json`

验证结果：
pipeline PASS，gate PASS，regression summary 显示 `status=passed`，`passed=1`，`failed=0`。

风险等级：P1 fixed

后续建议：
统一引入 CanonicalTestResult 作为 report/gate 的主输入，避免 legacy result 与 canonical result 长期双轨。

## 2026-06-09 - 默认 pytest 覆盖整个 tests 目录

模块名称：test baseline

Worker：Codex 主控

决策：
将 `pytest.ini` 的 `testpaths` 从局部目录改为 `tests`。

决策原因：
原默认 `python -m pytest -q` 收集 0 个测试，不能作为质量基线。显式 `python -m pytest tests -q` 能跑核心测试，因此默认入口应覆盖真实回归网。

验证结果：
`python -m pytest -q` -> 406 passed。

风险等级：P1 fixed
