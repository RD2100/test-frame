# Verify Matrix

## MiniApp Evidence/Reconnect Verification - 2026-06-09

| Date | Module | Command | Result | Evidence | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | MiniApp wrapper syntax | `python -m py_compile cli\wrappers\miniapp.py` | exit 0 | terminal output | PASS |
| 2026-06-09 | MiniApp focused regression | `python -m pytest tests\test_miniapp_integration.py -q` | 23 passed | terminal output | PASS |
| 2026-06-09 | Related regression | `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` | 100 passed | terminal output | PASS |
| 2026-06-09 | Python full baseline | `python -m pytest -q` | 435 passed | terminal output | PASS |
| 2026-06-09 | JS oracle baseline | `npm run test:unit:js` | 26 passed | terminal output | PASS |
| 2026-06-09 | FitTrack smoke | `python -m cli.main run --project fittrack --profile smoke` | pipeline PASS, gate PASS | terminal output | PASS |
| 2026-06-09 | Formal MiniApp profile | `python -m cli.main run --project fittrack --profile miniapp_e2e` | controlled `BLOCKED`: `miniprogram-automator could not connect to ws://localhost:9420` | `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json` | BLOCKED |

## MiniApp Page-Group Verification - 2026-06-09

| Date | Module | Command | Result | Evidence | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | Page-group JS syntax | `node --check tests\fittrack\miniapp\e2e_group.js` | exit 0 | terminal output | PASS |
| 2026-06-09 | MiniApp wrapper syntax | `python -m py_compile cli\wrappers\miniapp.py` | exit 0 | terminal output | PASS |
| 2026-06-09 | MiniApp wrapper/page-group tests | `python -m pytest tests\test_miniapp_integration.py -q` | 16 passed | terminal output | PASS |
| 2026-06-09 | Related regression | `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` | 93 passed | terminal output | PASS |
| 2026-06-09 | Python full baseline | `python -m pytest -q` | 428 passed after rerun | terminal output | PASS |
| 2026-06-09 | JS oracle baseline | `npm run test:unit:js` | 26 passed | terminal output | PASS |
| 2026-06-09 | FitTrack smoke | `python -m cli.main run --project fittrack --profile smoke` | pipeline PASS, gate PASS | terminal output | PASS |
| 2026-06-09 | Formal MiniApp profile | `python -m cli.main run --project fittrack --profile miniapp_e2e` | controlled `BLOCKED`; `login-index` and `tabs` probes passed, `exercise` probe could not connect to `ws://localhost:9420` | `reports/fittrack/2026-06-09/miniapp-runtime-probe-*.json` | BLOCKED |

## MiniApp Runtime Probe Verification - 2026-06-09

| Date | Module | Command | Result | Evidence | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | Runtime probe syntax | `node --check scripts\miniapp_runtime_probe.js` | exit 0 | terminal output | PASS |
| 2026-06-09 | MiniApp wrapper syntax | `python -m py_compile cli\wrappers\miniapp.py` | exit 0 | terminal output | PASS |
| 2026-06-09 | MiniApp wrapper/probe tests | `python -m pytest tests\test_miniapp_integration.py -q` | 13 passed | terminal output | PASS |
| 2026-06-09 | Related regression | `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` | 90 passed | terminal output | PASS |
| 2026-06-09 | JS syntax set | `node --check scripts\miniapp_route_preflight.js; node --check scripts\miniapp_runtime_probe.js; node --check tests\fittrack\miniapp\e2e_full.js; node --check tests\fittrack\miniapp\run_tests.js; node --check scripts\run_miniapp_e2e.js; node --check packages\miniprogram-e2e\helpers.js` | exit 0 | terminal output | PASS |
| 2026-06-09 | Python full baseline | `python -m pytest -q` | 425 passed | terminal output | PASS |
| 2026-06-09 | JS oracle baseline | `npm run test:unit:js` | 26 passed | terminal output | PASS |
| 2026-06-09 | FitTrack smoke | `python -m cli.main run --project fittrack --profile smoke` | PASS, gate PASS | terminal output | PASS |
| 2026-06-09 | Standalone runtime probe without valid runtime | `node scripts\miniapp_runtime_probe.js --port 9420 --required-routes <13 routes>` | exit 2, structured `blocked` | terminal JSON | BLOCKED expected |
| 2026-06-09 | Formal MiniApp profile | `python -m cli.main run --project fittrack --profile miniapp_e2e` | 59s controlled `BLOCKED` at runtime probe | terminal output | BLOCKED |

## MiniApp E2E Verification - 2026-06-09

| Date | Module | Command | Result | Evidence | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | MiniApp route preflight | `node scripts\miniapp_route_preflight.js --project D:\fitness-manager --required-routes <13 config routes>` | `status=passed`, `totalRoutes=13`, `missingRoutes=[]`, `missingFiles=[]` | terminal JSON summary | PASS |
| 2026-06-09 | MiniApp wrapper tests | `python -m pytest tests\test_miniapp_integration.py -q` | 11 passed | terminal output | PASS |
| 2026-06-09 | MiniApp related regression | `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` | 87 passed | terminal output | PASS |
| 2026-06-09 | Full Python baseline | `python -m pytest -q` | 423 passed | terminal output | PASS |
| 2026-06-09 | JS oracle baseline | `npm run test:unit:js` | 26 passed, 0 failed | terminal output | PASS |
| 2026-06-09 | MiniApp JS syntax | `node --check tests\fittrack\miniapp\e2e_full.js; node --check tests\fittrack\miniapp\run_tests.js; node --check scripts\run_miniapp_e2e.js; node --check packages\miniprogram-e2e\helpers.js` | exit 0 | terminal output | PASS |
| 2026-06-09 | FitTrack smoke pipeline | `python -m cli.main run --project fittrack --profile smoke` | pipeline PASS, gate PASS | terminal output | PASS |
| 2026-06-09 | Direct MiniApp clean run | `node tests\fittrack\miniapp\e2e_full.js --port 9420` after clean open/auto | 58 results: 36 passed, 9 failed, 13 skipped | terminal `MINIAPP_RESULTS` | FAILED: real runtime reached but not stable |
| 2026-06-09 | Formal MiniApp profile | `python -m cli.main run --project fittrack --profile miniapp_e2e` | blocked on port drift in one run; later timed out after entering script | terminal output | BLOCKED/FAILED |

## Latest Verification - 2026-06-09

| Date | Module | Command | Result | Evidence | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | Python syntax gate | `python -m py_compile aggregator\collector.py orchestrator\stage.py orchestrator\engine.py aggregator\report.py schema\stage_results.py` | exit 0 | terminal output | PASS |
| 2026-06-09 | Sidecar/report targeted regression | `python -m pytest tests\test_stage_results_schema.py tests\test_aggregator_collector.py tests\test_regression_report.py tests\test_gate_semantics.py tests\test_orchestrator_engine.py tests\test_stage_status.py -q` | 109 passed | terminal output | PASS |
| 2026-06-09 | Python full baseline | `python -m pytest -q` | 412 passed | terminal output | PASS |
| 2026-06-09 | JS oracle direct runner | `npm run test:unit:js` | 26 passed, 0 failed | terminal output | PASS |
| 2026-06-09 | JS Jest wrapper | `npm run test:miniapp -- --runInBand` | 1 suite passed, 1 test passed | terminal output | PASS |
| 2026-06-09 | FitTrack smoke pipeline | `python -m cli.main run --project fittrack --profile smoke` | pipeline PASS, gate PASS | terminal output | PASS |
| 2026-06-09 | FitTrack summary artifact | read `reports/fittrack/2026-06-09/regression-summary.json` | `status=passed`, `passed=1`, `failed=0`, `top_failures=[]`, `environmentBlocks=[]`, `blockers=[]` | JSON file | PASS |
| 2026-06-09 | FitTrack markdown sidecar check | `Select-String reports\fittrack\2026-06-09\regression-report.md "_detail|_canonical|canonical_error"` | no sidecar matches; Stage Results only shows `pytest_api` | Markdown file | PASS |
| 2026-06-09 | MiniApp automator stale port probe | `node tests\fittrack\miniapp\e2e_full.js --port 19541` | exit 1, connection refused | terminal output | PASS: failure semantics; BLOCKED env |
| 2026-06-09 | MiniApp automator active port probe | `node tests\fittrack\miniapp\e2e_full.js --port 9420` | connected and executed; failed on stale page routes | terminal output | BLOCKED: script/project route mismatch |
| 2026-06-09 | MiniApp short smoke script | `node tests\fittrack\miniapp\run_tests.js` | skipped; `WECHAT_DEVTOOLS_CLI` and `FITTRACK_PATH` unset | terminal output | BLOCKED: env vars unset |
| 2026-06-09 | Legacy report CLI | `python -m cli.main report --project fittrack` | exit 0; generated `reports\fittrack\2026-06-09\allure-report` path | terminal output | PASS |

| Date | Module | Command | Result | Evidence | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | Python targeted regression | `python -m pytest tests\test_aggregator_collector.py tests\test_stage_status.py tests\test_orchestrator_engine.py tests\test_gate_semantics.py -q` | 78 passed | terminal output | PASS |
| 2026-06-09 | Python full baseline | `python -m pytest -q` | 406 passed | terminal output | PASS |
| 2026-06-09 | JS oracle direct runner | `npm run test:unit:js` | 26 passed, 0 failed | terminal output | PASS |
| 2026-06-09 | JS Jest wrapper | `npm run test:miniapp -- --runInBand` | 1 suite passed, 1 test passed | terminal output | PASS |
| 2026-06-09 | FitTrack smoke pipeline | `python -m cli.main run --project fittrack --profile smoke` | pipeline PASS, gate PASS | terminal output | PASS |
| 2026-06-09 | FitTrack regression summary | read `reports/fittrack/2026-06-09/regression-summary.json` | `profile=smoke`, `status=passed`, `passed=1`, `failed=0`, `top_failures=[]` | JSON file | PASS |
| 2026-06-09 | MiniApp failure semantics | `node tests\fittrack\miniapp\e2e_full.js --port 19541` without IDE | exit 1, failed JSON | terminal output | PASS |
| 2026-06-09 | Legacy report CLI | `python -m cli.main report --project fittrack` | exit 0, old report path preserved | terminal output | PASS |

## Pending Independent Verification

| Worker | Scope | Status |
|---|---|---|
| Architecture-Reviewer | Architecture consistency of report/gate data source and sidecar filtering | running |
| Quality-Reviewer | Quality review for false green/false red, tests, exit semantics | running |
| Verifier | Post-fix command replay and artifact inspection | running |
