# Handoff

## Current Delta - 2026-06-09 23:18

Main path:
- `miniapp.results_artifact: true` now writes page-group result files such as `miniapp-results-login-index.json`.
- Runtime probe timeouts and script timeouts now produce synthetic evidence artifacts instead of disappearing.
- `artifact_errors` exposes failed result-artifact writes.
- Partial page-group failures caused only by DevTools `Connection closed` are classified as `blocked`, not app `failed`.
- `reopen_between_scripts: true` lets FitTrack re-run DevTools `open`/`auto` before later page groups.
- Force-clean now includes `WeChatAppEx`, which is the actual stale WMPF runtime process observed on this machine.
- DevTools port-drift gets one force-clean retry.

Important evidence:
- `python -m pytest tests\test_miniapp_integration.py -q` -> 23 passed.
- `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` -> 100 passed.
- `python -m pytest -q` -> 435 passed.
- `npm run test:unit:js` -> 26 passed.
- `python -m cli.main run --project fittrack --profile smoke` -> PASS/gate PASS.
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> controlled `BLOCKED`: `miniprogram-automator could not connect to ws://localhost:9420`.

Current MiniApp state:
- Evidence and classification are much stronger than before.
- Formal MiniApp gate is still not ready. The remaining P1 is deterministic WeChat DevTools automation endpoint recovery.
- Earlier real artifacts showed `login-index`, `tabs`, and `exercise` can pass when the endpoint stays alive; latest run blocked before page scripts.

Next best task:
1. Add a DevTools endpoint health/recovery step before runtime probe.
2. Investigate whether the WeChat DevTools CLI has a reliable close/restart command for the automation server.
3. Once endpoint recovery is stable, continue selector-level button tap/input coverage.

## Current Delta - 2026-06-09 22:45

Main path:
- `cli/wrappers/miniapp.py` now supports ordered `miniapp.test_scripts` while preserving legacy `test_script`.
- FitTrack `miniapp_e2e` now runs five page groups through `tests/fittrack/miniapp/e2e_group.js`: `login-index`, `tabs`, `exercise`, `profile`, and `workout-plan-admin`.
- Runtime probe JSON is persisted when `runtime_probe_artifact: true`, with per-group files under `reports/fittrack/2026-06-09/`.
- Wrapper tests increased to 16 and pass.
- Full Python baseline increased to 428 and passes after rerun.

Important evidence:
- `python -m pytest tests\test_miniapp_integration.py -q` -> 16 passed.
- `python -m pytest tests\test_miniapp_integration.py tests\test_stage_status.py tests\test_gate_semantics.py tests\test_config_loader.py -q` -> 93 passed.
- `python -m pytest -q` -> 428 passed after rerun.
- `npm run test:unit:js` -> 26 passed.
- `python -m cli.main run --project fittrack --profile smoke` -> PASS/gate PASS.
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> controlled `BLOCKED`: `login-index` and `tabs` probes passed, `exercise` probe failed to connect to `ws://localhost:9420`.
- Probe artifacts:
  - `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json`
  - `reports/fittrack/2026-06-09/miniapp-runtime-probe-tabs.json`
  - `reports/fittrack/2026-06-09/miniapp-runtime-probe-exercise.json`

Current MiniApp state:
- Static route preflight remains stable.
- Page-group boundaries are now implemented and observable.
- The DevTools automator endpoint still drops before the full five-group run finishes, so `miniapp_e2e` remains opt-in and not gate-ready.
- Button-level/human-like coverage is still not proven; `e2e_group.js` is a route/data/UI reachability runner.

Next best task:
1. Add deterministic DevTools relaunch/reconnect between page groups.
2. Persist page-group `MINIAPP_RESULTS` as `miniapp-results-<group>.json`.
3. Generate handler coverage from preflight `clickableSummary` and add selector-level tap/input probes.

## Current Delta - 2026-06-09 22:30

Main path:
- Added `scripts/miniapp_runtime_probe.js`.
- `cli/wrappers/miniapp.py` now runs runtime probe before full E2E and uses temp-file command capture to avoid Windows pipe-inheritance hangs.
- MiniApp wrapper tests increased to 13 and pass.
- Full Python baseline increased to 425 tests and passes.
- FitTrack smoke remains green.

Important evidence:
- `python -m pytest -q` -> 425 passed.
- `python -m cli.main run --project fittrack --profile smoke` -> PASS/gate PASS.
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> controlled `BLOCKED` in 59s: `miniprogram-automator connection closed during runtime probe`.

Current MiniApp state:
- Static project route preflight is stable.
- Runtime identity is now checked before full E2E.
- Full E2E is still not stable enough for gate use. This is now a clear P1 blocker, not a hidden failure or hanging command.

Next best task:
1. Split MiniApp E2E into page-group scripts and run each group with fresh runtime probe.
2. Add aggregation for page-group results into wrapper output.
3. Persist runtime probe JSON as report evidence.

## Current Delta - 2026-06-09 22:00

Main path:
- FitTrack smoke remains stable and green after MiniApp changes.
- MiniApp route preflight now correctly validates the real `D:\fitness-manager` app: 13 routes, no missing route/file.
- `miniapp_e2e` is now an explicit profile and does not pollute default smoke.
- MiniApp wrapper now distinguishes `blocked`, `error`, and real `failed` cases for DevTools CLI, route preflight, automator connection, runtime project mismatch, and test timeout.
- `miniprogram-automator` package cannot be upgraded through npm right now: `npm view miniprogram-automator version` returns `0.12.1`, matching installed version.

Verification state:
- `python -m pytest -q` -> 423 passed.
- `npm run test:unit:js` -> 26 passed.
- `python -m cli.main run --project fittrack --profile smoke` -> PASS/gate PASS.
- `python -m pytest tests\test_miniapp_integration.py -q` -> 11 passed.
- MiniApp direct clean run reached real FitTrack pages and produced 58 results: 36 passed, 9 failed, 13 skipped.

MiniApp current capability:
- Can statically verify all 13 configured app routes and collect WXML tap handler inventory.
- Can connect to WeChat DevTools when the runtime is clean and `localhost:9420` is used.
- Can execute real checks on login, index, exercise, and profile pages.
- Cannot yet claim all buttons/pages are fully tested. The suite is unstable after profile-edit and can lose DevTools connection.

Known blockers:
- DevTools runtime can drift to stale/cached app state or a random IDE server port.
- Formal `miniapp_e2e` profile is still not a reliable green gate.
- Screenshot capture is disabled by default because it can destabilize the automator connection.

Next best work:
1. Create a small runtime identity probe: connect, read current page, verify route membership, optionally reLaunch login/index, then exit quickly.
2. Split `e2e_full.js` into page-group scripts: auth/login, tab pages, profile subpages, workout/plan/admin. Run each with fresh DevTools or reconnect.
3. Build selector-level button coverage from preflight `clickableSummary`, then report coverage per route/handler.
4. Only after the page-group probes are stable, wire `miniapp_e2e` into a broader regression gate.

## Current Delta - 2026-06-09 20:20

Main path:
- Shared stage result filtering is now centralized in `schema/stage_results.py`.
- `aggregator/collector.py`, `aggregator/report.py`, `orchestrator/stage.py`, and `orchestrator/engine.py` use the shared helper or shared predicate.
- Regression Markdown/report blocker/environment-block views no longer expose `_detail`, `_canonical`, or `_canonical_error` sidecars.
- Allure writer maps internal `blocked/error/cancelled` statuses to `broken` and preserves the original value as `canonical_status`.

Verification state:
- Syntax gate passed.
- Targeted Python regression: 109 passed.
- Full Python baseline: 412 passed.
- JS oracle direct runner: 26 passed.
- Jest wrapper: 1 suite passed.
- FitTrack smoke pipeline: PASS, gate PASS.
- `reports/fittrack/2026-06-09/regression-summary.json`: `status=passed`, `passed=1`, `failed=0`, `top_failures=[]`, `environmentBlocks=[]`, `blockers=[]`.

MiniApp state:
- `node tests\fittrack\miniapp\e2e_full.js --port 19541`: fails to connect, as expected when that port is not listening.
- `node tests\fittrack\miniapp\e2e_full.js --port 9420`: connects to WeChat DevTools automator and executes, but fails due to stale route assumptions in the script.
- `node tests\fittrack\miniapp\run_tests.js`: currently skips because `WECHAT_DEVTOOLS_CLI` and `FITTRACK_PATH` are unset.

Next best work:
1. Build a current MiniApp route inventory from the real target project before claiming all pages/buttons are covered.
2. Add a `miniapp_e2e` profile/stage that returns `blocked` when DevTools/env vars are missing, not fake green.
3. Continue CanonicalTestResult main-path migration after the report/gate sidecar cleanup is stable.

## Current State - 2026-06-09

主流程状态：
- FitTrack smoke pipeline 当前通过。
- Gate 当前通过。
- Regression JSON/Markdown report 当前与 gate 同源，显示本次 smoke 结果通过。

关键修复：
- `aggregator.collector.collect_and_generate()` 接受 orchestrator report stage 上下文。
- 有 `stage_results` 时 report 使用当前 stage/tool 状态，不再从 adapters 重新收集历史结果。
- Orchestrator 和 gate adapter 过滤 internal sidecar keys，包括 `*_detail`、`*_status`、`*_canonical`、`*_canonical_error`。
- 默认 pytest 入口覆盖 `tests`。
- JS oracle 可被 Node 和 Jest 双入口运行。
- MiniApp E2E fatal/failed 会返回非零退出码。

建议下一步：
1. 等待 Architecture-Reviewer、Quality-Reviewer、Verifier 三个只读智能体完成。
2. 如有 P0/P1 发现，优先修复并重跑总验证。
3. 若无阻断项，下一波并行任务可拆为：
   - CanonicalTestResult 主路径迁移设计与实现。
   - MiniApp E2E 标准 profile 接入。
   - Allure CLI 环境检查/安装说明。
   - CLI-Anything 可执行性修复与 tool contract 设计。

人工决策点：
- 是否把小程序完整 E2E 纳入 FitTrack 默认 regression profile。
- 是否安装 Allure CLI，或接受 Markdown/JSON 作为主报告。
- 是否将 CLI-Anything 作为正式 test-frame tool 接入。
