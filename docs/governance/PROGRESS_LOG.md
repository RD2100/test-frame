# Progress Log

## 2026-06-09 - MiniApp evidence hardening and DevTools reconnect attempts

Module: FitTrack MiniApp E2E

Worker: Codex main controller

Changed paths:
- `cli/wrappers/miniapp.py`
- `config/projects/fittrack.yaml`
- `tests/test_miniapp_integration.py`
- `reports/fittrack/2026-06-09/miniapp-results-*.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-*.json`

Completed:
- Persisted page-group `MINIAPP_RESULTS` as `miniapp-results-<group>.json` when `miniapp.results_artifact: true`.
- Added explicit `artifact_errors` so failed artifact writes are visible instead of silently becoming `None`.
- Added synthetic runtime-probe artifacts for runtime probe timeouts.
- Added synthetic script-result artifacts for page-group script timeouts.
- Added `reopen_between_scripts: true` support and FitTrack config so later page groups can re-run DevTools `open`/`auto` before probing.
- Added one retry for DevTools port drift after `force_clean_start`.
- Added `WeChatAppEx` to the force-clean process list because real stale runtime processes use that process name outside the DevTools install directory.
- Reclassified partial page-group connection-loss failures as `blocked` instead of app `failed`.

Verification:
- `python -m py_compile cli\wrappers\miniapp.py` -> passed.
- `python -m pytest tests\test_miniapp_integration.py -q` -> 23 passed.
- `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` -> 100 passed.
- `python -m pytest -q` -> 435 passed.
- `npm run test:unit:js` -> 26 passed.
- `python -m cli.main run --project fittrack --profile smoke` -> pipeline PASS, gate PASS.
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> controlled `BLOCKED`: latest probe cannot connect to `ws://localhost:9420`; evidence in `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json`.

Risk level: P1 MiniApp gate readiness remains open; evidence quality and failure classification improved.

Next:
- Investigate why WeChat DevTools automation endpoint is not reliably recreated even after `WeChatAppEx` cleanup.
- Add a dedicated DevTools endpoint health probe before spending full profile time.
- Continue button-level tap/input coverage after runtime stability is sufficient.

## 2026-06-09 - MiniApp page-group runner and probe artifacts

Module: FitTrack MiniApp E2E

Worker: Codex main controller

Changed paths:
- `cli/wrappers/miniapp.py`
- `config/projects/fittrack.yaml`
- `tests/fittrack/miniapp/e2e_group.js`
- `tests/test_miniapp_integration.py`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-tabs.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-exercise.json`

Completed:
- Added `miniapp.test_scripts` support to the wrapper while preserving legacy `miniapp.test_script`.
- Added sequential aggregation for page-group scripts, including per-script result annotation and partial result preservation when a later group is blocked.
- Added `tests/fittrack/miniapp/e2e_group.js` with page groups: `login-index`, `tabs`, `exercise`, `profile`, and `workout-plan-admin`.
- Updated FitTrack `miniapp_e2e` config to use those five page groups.
- Persisted runtime probe JSON artifacts when `miniapp.runtime_probe_artifact` is enabled.

Verification:
- `node --check tests\fittrack\miniapp\e2e_group.js` -> passed.
- `python -m py_compile cli\wrappers\miniapp.py` -> passed.
- `python -m pytest tests\test_miniapp_integration.py -q` -> 16 passed.
- `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` -> 93 passed.
- `python -m pytest -q` -> 428 passed after rerun; an earlier full run had one transient admin login failure that passed when replayed directly.
- `npm run test:unit:js` -> 26 oracle checks passed.
- `python -m cli.main run --project fittrack --profile smoke` -> pipeline PASS, gate PASS.
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> controlled `BLOCKED`: runtime probe passed for `login-index` and `tabs`, then `exercise` probe could not connect to `ws://localhost:9420`.

Risk level: P1 MiniApp gate readiness remains open; page-group isolation and probe artifacts are now in place.

Next:
- Persist page-group `MINIAPP_RESULTS` as first-class artifacts, not only probe artifacts.
- Add deterministic DevTools relaunch/reconnect between page groups.
- Build WXML handler coverage from `clickableSummary` and map it to real tap/input probes.

## 2026-06-09 - MiniApp runtime probe and subprocess hang hardening

Module: FitTrack MiniApp E2E / TestFrame wrapper

Worker: Codex main controller

Changed paths:
- `scripts/miniapp_runtime_probe.js`
- `cli/wrappers/miniapp.py`
- `tests/test_miniapp_integration.py`
- `docs/governance/*`

Completed:
- Added a standalone MiniApp runtime identity probe that connects to `ws://localhost:<port>`, verifies the current page or relaunch target belongs to the configured route list, and returns structured `passed/blocked/error` JSON.
- Integrated runtime probe into `cli/wrappers/miniapp.py` after DevTools `open/auto` and before long E2E execution.
- Added a `runtime_probe: false` escape hatch for targeted downstream-output tests only; FitTrack default remains probe-enabled.
- Replaced pipe-based command capture in the wrapper with temp-file capture to avoid Windows child-process pipe inheritance hangs from WeChat DevTools.
- Strengthened force-clean behavior by killing `wechatdevtools` by process name as well as path prefix.

Verification:
- `node --check scripts\miniapp_runtime_probe.js` -> passed.
- `python -m py_compile cli\wrappers\miniapp.py` -> passed.
- `python -m pytest tests\test_miniapp_integration.py -q` -> 13 passed.
- `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` -> 90 passed.
- `npm run test:unit:js` -> 26 oracle checks passed.
- `node --check scripts\miniapp_route_preflight.js; node --check scripts\miniapp_runtime_probe.js; node --check tests\fittrack\miniapp\e2e_full.js; node --check tests\fittrack\miniapp\run_tests.js; node --check scripts\run_miniapp_e2e.js; node --check packages\miniprogram-e2e\helpers.js` -> passed.
- `python -m pytest -q` -> 425 passed.
- `python -m cli.main run --project fittrack --profile smoke` -> pipeline PASS, gate PASS.
- `node scripts\miniapp_runtime_probe.js --port 9420 --required-routes <13 routes>` when no valid runtime is available -> exit 2, structured `blocked`.
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> 59s controlled `BLOCKED` at runtime probe: `miniprogram-automator connection closed during runtime probe`; no 10-minute hang.

Risk level: P1 MiniApp full E2E remains open; wrapper stability improved.

Next:
- Split full E2E into short page-group probes so each run can reconnect cleanly.
- Persist runtime probe JSON as evidence in the canonical/wrapper result.
- Add handler-level coverage reporting from preflight `clickableSummary`.

## 2026-06-09 - MiniApp E2E profile and runtime preflight hardening

Module: FitTrack MiniApp E2E / TestFrame wrapper

Worker: Codex main controller

Changed paths:
- `scripts/miniapp_route_preflight.js`
- `cli/wrappers/miniapp.py`
- `config/projects/fittrack.yaml`
- `config/profiles/miniapp_e2e.yaml`
- `tests/test_miniapp_integration.py`
- `tests/fittrack/miniapp/e2e_full.js`
- `tests/fittrack/miniapp/run_tests.js`
- `scripts/run_miniapp_e2e.js`
- `packages/miniprogram-e2e/helpers.js`

Completed:
- Fixed MiniApp route preflight path resolution from `route/leaf.wxml` to `route.wxml`.
- Added explicit `miniapp_e2e` profile/stage so MiniApp E2E is opt-in and does not affect FitTrack smoke.
- Updated MiniApp wrapper to run route preflight, open the configured project, enable DevTools automation with `--auto-port`, capture UTF-8 output safely, and return explicit `blocked/error/failed`.
- Added detection for DevTools port drift, automator connection failure, connection-closed cascades, and runtime project mismatch.
- Switched MiniApp automator WebSocket host from `127.0.0.1` to `localhost` because the working DevTools listener is IPv6/localhost while IPv4 can attach to the wrong endpoint.
- Made `e2e_full.js` avoid screenshot calls by default because `mp.screenshot()` can destabilize the DevTools connection; screenshots are now opt-in via `MINIAPP_SCREENSHOTS=1` or `--screenshots`.
- Added `force_clean_start: true` for FitTrack MiniApp so the wrapper can clear stale DevTools processes before opening the target project.

Verification:
- `node scripts\miniapp_route_preflight.js --project D:\fitness-manager --required-routes <13 routes from config>` -> `status=passed`, `totalRoutes=13`, `missingRoutes=[]`, `missingFiles=[]`.
- `python -m pytest tests\test_miniapp_integration.py -q` -> 11 passed.
- `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` -> 87 passed.
- `python -m pytest -q` -> 423 passed.
- `npm run test:unit:js` -> 26 oracle checks passed.
- `node --check tests\fittrack\miniapp\e2e_full.js; node --check tests\fittrack\miniapp\run_tests.js; node --check scripts\run_miniapp_e2e.js; node --check packages\miniprogram-e2e\helpers.js` -> passed.
- `python -m cli.main run --project fittrack --profile smoke` -> pipeline PASS, gate PASS.
- Direct MiniApp probe after clean open/auto: `node tests\fittrack\miniapp\e2e_full.js --port 9420` -> reached real FitTrack runtime, 58 results, 36 passed, 9 failed, 13 skipped; login/index/exercise/profile checks executed; failures include training redirect to login and profile-edit timeout followed by connection close.
- Formal wrapper run is not yet stable: `python -m cli.main run --project fittrack --profile miniapp_e2e` reproduced `blocked` port drift in one run and `error` test timeout in another run.

Risk level: P1 for complete MiniApp E2E readiness remains open; P2 wrapper/reporting false-classification risks mitigated.

Next:
- Add a runtime launcher/probe that proves the active DevTools window path belongs to `D:\fitness-manager` before running the full suite.
- Split the 13-page E2E into smaller page groups so one DevTools connection failure does not erase the whole run.
- Replace remaining `setData`-heavy checks with selector-level tap/input probes for true button coverage.

## 2026-06-09 - Shared stage result filtering hardening

Module: TestFrame orchestrator / aggregator / regression report

Worker: Codex main controller

Changed paths:
- `schema/stage_results.py`
- `aggregator/collector.py`
- `aggregator/report.py`
- `orchestrator/stage.py`
- `orchestrator/engine.py`
- `tests/test_stage_results_schema.py`
- `tests/test_aggregator_collector.py`
- `tests/test_regression_report.py`

Completed:
- Centralized stage result sidecar filtering in `schema.stage_results`.
- Replaced duplicated `_status/_detail/_canonical/_canonical_error` filtering in stage, engine, collector, and regression report.
- Prevented raw sidecars from leaking into Markdown Stage Results, blockers, and environment block detection.
- Mapped internal `blocked/error/cancelled` statuses to Allure-compatible `broken`, while preserving the original value as `canonical_status`.
- Extended collector summary counts for `error` and `cancelled`.

Verification:
- `python -m py_compile aggregator\collector.py orchestrator\stage.py orchestrator\engine.py aggregator\report.py schema\stage_results.py` -> passed.
- `python -m pytest tests\test_stage_results_schema.py tests\test_aggregator_collector.py tests\test_regression_report.py tests\test_gate_semantics.py tests\test_orchestrator_engine.py tests\test_stage_status.py -q` -> 109 passed.
- `python -m pytest -q` -> 412 passed.
- `npm run test:unit:js` -> 26 oracle checks passed.
- `npm run test:miniapp -- --runInBand` -> 1 suite passed, 1 test passed.
- `python -m cli.main run --project fittrack --profile smoke` -> pipeline PASS, gate PASS.
- `reports/fittrack/2026-06-09/regression-summary.json` -> `status=passed`, `passed=1`, `failed=0`, `top_failures=[]`, `environmentBlocks=[]`, `blockers=[]`.
- `Select-String reports\fittrack\2026-06-09\regression-report.md "_detail|_canonical|canonical_error"` -> no sidecar matches; Stage Results only shows `pytest_api`.

MiniApp probe:
- `node tests\fittrack\miniapp\e2e_full.js --port 19541` -> failed to connect; no listener on that port.
- `node tests\fittrack\miniapp\e2e_full.js --port 9420` -> connected to WeChat DevTools automator and executed, but failed because the script expects stale routes such as `pages/login/login` and `pages/training/training`.

Risk level: P2 architecture findings mitigated; MiniApp route coverage remains open.

Next:
- Build route discovery / page inventory before claiming full MiniApp button coverage.
- Decide whether to add a `miniapp_e2e` profile separate from default FitTrack smoke.

## 2026-06-09 - Report/Gate 主流程质量收口

模块名称：TestFrame orchestrator report/gate pipeline

Worker：Codex 主控

变更路径：
- `aggregator/collector.py`
- `orchestrator/stage.py`
- `orchestrator/engine.py`
- `pytest.ini`
- `tests/test_aggregator_collector.py`
- `tests/test_orchestrator_engine.py`
- `tests/test_gate_semantics.py`
- `tests/test_stage_status.py`
- `tests/h5/support/__tests__/oracles.test.js`
- `tests/fittrack/miniapp/e2e_full.js`
- `scripts/run_miniapp_e2e.js`

完成内容：
- 修复 `Stage._run_report()` 调用 `collect_and_generate(..., stage_results=..., profile=..., base_url=...)` 时的接口不匹配。
- 修复 gate/report 把 `*_canonical` 旁路对象当作工具结果的问题。
- 修复 report stage 重新从 adapters 收集历史结果，导致 pipeline/gate 通过但 regression report 显示历史失败的问题。
- 修复默认 `python -m pytest -q` 收集 0 个用例的问题。
- 修复 JS oracle 在 Jest 下无 `test()` 导致 npm 脚本失败的问题。
- 修复小程序 E2E 脚本 fatal 失败仍 exit 0 的假绿问题。

验证命令与结果：
- `python -m pytest tests\test_aggregator_collector.py tests\test_stage_status.py tests\test_orchestrator_engine.py tests\test_gate_semantics.py -q` -> 78 passed。
- `python -m pytest -q` -> 406 passed。
- `npm run test:unit:js` -> 26 oracle checks passed。
- `npm run test:miniapp -- --runInBand` -> 1 suite passed, 1 test passed。
- `python -m cli.main run --project fittrack --profile smoke` -> pipeline PASS, gate PASS。
- `reports/fittrack/2026-06-09/regression-summary.json` -> `profile=smoke`, `status=passed`, `passed=1`, `failed=0`, `top_failures=[]`。
- `node tests\fittrack\miniapp\e2e_full.js --port 19541` with IDE not connected -> exit 1, expected failure semantics。

风险等级：P1 fixed

剩余缺口：
- Allure CLI 未安装，HTML Allure 报告跳过。
- 当前标准 FitTrack pipeline 只覆盖 `pytest_api`，不等于完整小程序 UI 按钮覆盖。

后续建议：
- 下一波将 CanonicalTestResult 从旁路推进为 report/gate 主数据源。
- 为小程序 E2E 建立页面按钮清单和 selector 级真实 tap/input 覆盖。
