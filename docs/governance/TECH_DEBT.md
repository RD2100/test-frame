# Technical Debt

## 2026-06-10 - FitTrack MiniApp local path configuration TODO

### TD-2026-06-10-001 - Move MiniApp local paths to environment/local override before release

Module: `config/projects/fittrack.yaml`

Level: P2

Description: The current FitTrack MiniApp configuration contains machine-local paths for WeChat DevTools and the FitTrack project (`devtool_path`, `project_path`). This is acceptable for local iteration but should not be treated as portable release configuration.

Evidence:
- `config/projects/fittrack.yaml` currently sets `miniapp.devtool_path` and `miniapp.project_path` to local Windows paths.

Recommendation: Before release/PR finalization, move these values to environment variables or a non-committed local override, e.g. `WECHAT_DEVTOOLS_CLI` and `FITTRACK_PATH`.

Status: open

## Evidence/Reconnect Update - 2026-06-09

### TD-2026-06-09-011 - DevTools automation endpoint needs deterministic health recovery

Module: FitTrack MiniApp E2E

Level: P1

Description: The wrapper now force-cleans `WeChatAppEx`, retries port drift, and can reopen DevTools between page groups. Even so, the formal `miniapp_e2e` profile can still end with `miniprogram-automator could not connect to ws://localhost:9420`.

Evidence:
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> controlled `BLOCKED` at runtime probe.
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json` records the unavailable endpoint.

Recommendation: Add a dedicated DevTools endpoint health/recovery step that verifies the WebSocket listener before running runtime probe, and investigate whether DevTools CLI exposes a more reliable close/restart command than process cleanup.

## Page-Group Update - 2026-06-09

### TD-2026-06-09-010 - Page-group MiniApp results are not persisted as first-class artifacts

Module: MiniApp wrapper / reporting

Level: P2

Description: Runtime probe JSON is now persisted per page group, but the page-group `MINIAPP_RESULTS` payloads are still only present in wrapper memory and terminal-derived classification.

Evidence:
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-tabs.json`
- `reports/fittrack/2026-06-09/miniapp-runtime-probe-exercise.json`
- No equivalent `miniapp-results-<group>.json` artifact exists yet.

Recommendation: Save each script result payload to `reports/fittrack/<date>/miniapp-results-<group>.json` and later map those files into Canonical evidence.

Status: resolved for completed and timeout script paths. FitTrack now enables `results_artifact: true`, wrapper writes `miniapp-results-<group>.json`, and artifact write failures are exposed through `artifact_errors`.

## Runtime Probe Update - 2026-06-09

### TD-2026-06-09-008 - MiniApp full suite needs page-group isolation

Module: FitTrack MiniApp E2E

Level: P1

Description: Runtime probe prevents false starts, but the full suite remains too large for the current unstable DevTools connection. One connection loss blocks or invalidates the entire run.

Evidence:
- Runtime probe can fail before full E2E: `miniprogram-automator connection closed during runtime probe`.
- Previous direct full run reached 58 results before connection loss.

Recommendation: Split `e2e_full.js` into small scripts by page group: login/index, tab pages, profile subpages, workout/plan/admin. Run each group with a fresh open/auto/probe cycle and aggregate results.

Status: partially resolved. `miniapp.test_scripts` and `tests/fittrack/miniapp/e2e_group.js` now provide page-group execution and aggregation; deterministic DevTools relaunch/reconnect between groups remains open.

### TD-2026-06-09-009 - Runtime probe evidence is not yet persisted as first-class artifact

Module: MiniApp wrapper / reporting

Level: P2

Description: The wrapper returns `runtime_probe` in memory for passed runs and includes failed probe details, but there is no dedicated JSON artifact under `reports/` for probe history.

Evidence:
- `scripts/miniapp_runtime_probe.js` emits structured JSON, but wrapper does not save it to disk.

Recommendation: Save runtime probe JSON to `reports/fittrack/<date>/miniapp-runtime-probe.json` and include it in Canonical evidence once the canonical path becomes the main report input.

Status: resolved for probe JSON. FitTrack now enables `runtime_probe_artifact: true` and writes per-group files under `reports/fittrack/<date>/`.

## Latest MiniApp Update - 2026-06-09

### TD-2026-06-09-005 - MiniApp E2E needs deterministic DevTools runtime launcher

Module: FitTrack MiniApp E2E

Level: P1

Description: The wrapper can preflight files and open DevTools, but the DevTools runtime can still drift between ports or attach to stale cached project state. Current mitigation detects and reports this, but does not yet guarantee a stable full run.

Evidence:
- `python -m cli.main run --project fittrack --profile miniapp_e2e` -> blocked on port drift in one run; timed out after entering test script in another.
- Direct clean run can reach real FitTrack pages and produce 58 results, but later loses connection.

Recommendation: Add a dedicated runtime probe script that checks active page membership in the configured route list, verifies automator command responsiveness, and only then starts a page-group suite. Consider running each page group in a fresh DevTools session.

### TD-2026-06-09-006 - Full button coverage is not yet proven

Module: FitTrack MiniApp E2E

Level: P2

Description: Route inventory now exposes WXML tap handlers, but the E2E script still validates many interactions by reading data or using `setData/callMethod`. This proves some runtime behavior but not every visible button as a human would operate it.

Evidence:
- Preflight clickable summary lists tap handlers such as `wechatLogin`, `goProfile`, `goCreatePlan`, `selectCategory`, `savePlan`, and `submitMetric`.
- `tests/fittrack/miniapp/e2e_full.js` still contains several `setData` paths.

Recommendation: Generate a per-page WXML interaction inventory and create selector-level probes for `tap`, input, picker, modal, and navigation outcomes. Track coverage by route and handler name.

### TD-2026-06-09-007 - Screenshots disabled by default due DevTools instability

Module: FitTrack MiniApp E2E artifacts

Level: P2

Description: `mp.screenshot()` caused or correlated with automator connection loss during real runs. The script now skips screenshots unless `MINIAPP_SCREENSHOTS=1` or `--screenshots` is provided.

Evidence:
- Direct run with screenshots reached login then connection closed after `login:screenshot`.
- Direct run without screenshots reached 58 results and exercised multiple pages.

Recommendation: Re-enable screenshots only after isolating them into a separate artifact pass or after confirming DevTools version stability.

## Latest Update - 2026-06-09

### TD-2026-06-09-004 - MiniApp E2E needs route discovery before full button coverage

Module: FitTrack MiniApp E2E

Level: P2

Description: WeChat DevTools automator is reachable on port 9420, but `tests/fittrack/miniapp/e2e_full.js` contains stale route assumptions. The script can connect and execute, but fails on missing pages such as `pages/login/login`, `pages/training/training`, and `pages/exercise/exercise`.

Why deferred: This turn focused on report/gate consistency and shared sidecar filtering. Updating full MiniApp E2E requires reading the current miniapp `app.json`, generating a route/page inventory, and replacing stale page assumptions with current selectors.

Recommendation: Add a preflight route inventory step and generate page/button coverage from current project files. Only then claim full UI/button coverage.

## Open

### TD-2026-06-09-001 - CanonicalTestResult 仍是旁路，不是 report/gate 主输入

模块：normalizers/orchestrator/report/gate

等级：P2

说明：
当前修复让 report/gate 使用同一份 orchestrator stage results，解决了 P1 不一致问题。但 CanonicalTestResult 仍主要作为 `*_canonical` sidecar 存在，没有成为 report/gate 的主数据契约。

原因：
本轮目标是修复现有质量断点，不扩大为架构迁移。

后续建议：
新增 `_canonical_results` 聚合字段，report/gate 优先消费 CanonicalTestResult；legacy stage results 仅保留兼容 fallback。

### TD-2026-06-09-002 - FitTrack 小程序 UI E2E 未进入标准 project profile

模块：FitTrack test profiles

等级：P2

说明：
`tests/fittrack/miniapp/e2e_full.js` 存在，但 `config/projects/fittrack.yaml` smoke/regression 当前只跑 `pytest_api`。

后续建议：
新增明确的 `miniapp_e2e` stage/profile，要求 WeChat DevTools automator 端口可用时执行；不可用时返回 blocked/error，不允许假绿。

### TD-2026-06-09-003 - Allure CLI 未安装

模块：reporting

等级：P2

说明：
Allure JSON/Markdown report 可生成，但 HTML Allure report 被跳过。

后续建议：
在环境检查中明确 Allure CLI 缺失的状态，必要时提供安装脚本或降级说明。
