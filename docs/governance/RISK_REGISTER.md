# Risk Register

## MiniApp Evidence/Reconnect Update - 2026-06-09

### Active

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp E2E | WeChat DevTools automation endpoint still cannot be reliably recreated after force-clean/reopen attempts | P1 | Latest `python -m cli.main run --project fittrack --profile miniapp_e2e` -> `BLOCKED`: `miniprogram-automator could not connect to ws://localhost:9420`; artifact `reports/fittrack/2026-06-09/miniapp-runtime-probe-login-index.json` | Keep profile opt-in; add dedicated endpoint health check and investigate DevTools CLI/window lifecycle | open |
| 2026-06-09 | MiniApp E2E | Full MiniApp button coverage is still not proven | P2 | `e2e_group.js` verifies routes/data/UI reachability; selector-level tap/input coverage remains incomplete | Build WXML handler coverage from preflight `clickableSummary` | open |

### Mitigated

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp evidence | Page-group result evidence could be lost when profile aborted | P2 | `miniapp-results-*.json` artifacts now exist for completed groups; timeout paths create synthetic result artifacts | `miniapp.results_artifact: true` and wrapper artifact errors | mitigated |
| 2026-06-09 | MiniApp classification | DevTools connection loss after partial page success could be misclassified as app failure | P2 | Regression test `test_miniapp_wrapper_blocks_partial_group_when_only_failures_are_connection_closed` | Connection-loss-only failures become `blocked` | mitigated |

## MiniApp Page-Group Update - 2026-06-09

### Active

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp E2E | Page-group runner can pass early groups but still lose the DevTools automator endpoint before later groups | P1 | `python -m cli.main run --project fittrack --profile miniapp_e2e` -> `login-index` and `tabs` probes passed, then `exercise` probe blocked with `miniprogram-automator could not connect to ws://localhost:9420` | Keep `miniapp_e2e` opt-in; add deterministic relaunch/reconnect between groups; persist group results and probe artifacts | open |
| 2026-06-09 | MiniApp E2E | Page-group script verifies page/data/UI reachability but does not yet prove every button is human-click tested | P2 | `tests/fittrack/miniapp/e2e_group.js` is route/data/UI-count oriented; WXML handler inventory is not yet mapped to tap coverage | Build handler coverage from preflight `clickableSummary` and add real selector-level tap/input probes | open |

### Mitigated

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp wrapper | Single long E2E process hid which page area destabilized the run | P1 | Wrapper now records `script_runs`, annotates results with `group`, and writes per-group runtime probe artifacts | `miniapp.test_scripts` page-group aggregation | mitigated |
| 2026-06-09 | MiniApp evidence | Runtime probe details were only visible in memory/terminal and could be lost after a blocked run | P2 | `reports/fittrack/2026-06-09/miniapp-runtime-probe-*.json` exists for latest run | `runtime_probe_artifact: true` | mitigated |

## MiniApp Runtime Probe Update - 2026-06-09

### Active

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp E2E | Full suite still cannot be a green quality gate because DevTools connection can close during runtime probe | P1 | `python -m cli.main run --project fittrack --profile miniapp_e2e` -> 59s `BLOCKED`: `miniprogram-automator connection closed during runtime probe` | Keep `miniapp_e2e` opt-in; split suite into page groups and reconnect per group | open |

### Mitigated

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp wrapper | WeChat DevTools child processes could keep stdout/stderr pipes open and hang the pipeline | P1 | Prior run exceeded 10-minute command timeout and left `python/node` test processes | `_run_command()` captures output through temp files; latest formal profile returns in 59s | mitigated |
| 2026-06-09 | MiniApp wrapper | Full E2E could start against missing/wrong runtime and produce noisy false failures | P1 | Standalone probe with no valid runtime exits 2 with structured `blocked` | Runtime probe now gates the long E2E script | mitigated |

## MiniApp E2E Runtime Update - 2026-06-09

### Active

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp E2E | Full `miniapp_e2e` profile is not yet stable enough to pass as a release gate | P1 | `python -m cli.main run --project fittrack --profile miniapp_e2e` produced DevTools port drift/blocking in one run and `miniapp test timed out after 300s` in another | Keep profile opt-in; split into smaller page groups; add stronger runtime project identity probe before full run | open |
| 2026-06-09 | MiniApp E2E | DevTools can attach automator to stale runtime (`pages/home/home`) instead of `D:\fitness-manager` | P1 | Direct run returned `env:page=pages/home/home` and route not-found errors before clean restart | Wrapper now detects runtime mismatch and can force clean start; still needs deterministic launcher verification | open |
| 2026-06-09 | MiniApp E2E | Long E2E script can lose connection mid-run after profile-edit timeout | P1 | Direct run reached 58 results with 36 passed, then failed on profile-edit timeout and connection-closed cascade | Shorten/split suites; add per-page process isolation or reconnect strategy | open |
| 2026-06-09 | MiniApp E2E | Current coverage still mixes real page navigation with `setData/callMethod`, not full human-like button tapping | P2 | `e2e_full.js` still uses `setData` for tab/category/plan interactions | Build selector inventory from WXML `bindtap/catchtap`, then add tap/input probes per page | open |

### Mitigated

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp preflight | Existing route preflight misclassified all real pages as missing files | P2 | Before fix it checked `pages/login/login/login.wxml`; after fix config-driven preflight returns `missingFiles=[]` | Resolve page files as `<miniappRoot>/<route>.wxml` and `<route>.js`; added regression tests | mitigated |
| 2026-06-09 | MiniApp wrapper | DevTools/automator failures could be reported as testcase `failed` instead of environment `blocked` | P2 | Unit tests cover invalid JSON, port drift, connection failure, connection-closed cascade, runtime mismatch | Explicit blocked/error classification in `cli/wrappers/miniapp.py` | mitigated |

## Latest Updates - 2026-06-09

### Active

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | MiniApp E2E | WeChat automator is reachable on port 9420, but current deep E2E script targets stale page routes | P2 | `node tests\fittrack\miniapp\e2e_full.js --port 9420` connects, then fails with missing routes such as `pages/login/login` and `pages/training/training` | Add route discovery/page inventory and regenerate E2E coverage from current `app.json` before claiming full button coverage | open |

### Fixed

| Date | Module | Risk | Level | Evidence | Fix | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | report rendering | Internal sidecars could leak into Markdown Stage Results, blockers, or environment blocks | P2 | Added regression tests with `_detail`, `_canonical`, and `_canonical_error` sidecars | Shared `schema.stage_results.iter_public_tool_results()` across report/collector/stage/engine | fixed |
| 2026-06-09 | Allure writer | Allure result JSON could expose unsupported internal statuses | P2 | `TestAllureStatusMapping` covers `blocked/error/cancelled` | Map to `broken` and preserve original value as `canonical_status` label | fixed |

## Active Risks

| Date | Module | Risk | Level | Evidence | Mitigation | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | Allure report | Allure CLI 未安装，HTML report 生成跳过 | P2 | `python -m cli.main run --project fittrack --profile smoke` 输出 `[WARN] Allure CLI not installed` | 不阻断 JSON/Markdown regression report；后续安装或配置 Allure CLI | open |
| 2026-06-09 | MiniApp E2E | 当前 FitTrack 标准 pipeline 不运行完整小程序 UI E2E | P2 | `config/projects/fittrack.yaml` smoke/regression tools 仅含 `pytest_api` | 后续把 miniapp E2E 纳入明确 profile 或独立 project/stage | open |
| 2026-06-09 | MiniApp E2E | 页面按钮真实点击覆盖不足，部分测试使用 `setData/callMethod` | P2 | `tests/fittrack/miniapp/e2e_full.js` 中存在多处 `setData` | 建立页面按钮清单，补 selector 级 tap/input probe | open |

## Fixed Risks

| Date | Module | Risk | Level | Evidence | Fix | Status |
|---|---|---|---|---|---|---|
| 2026-06-09 | report stage | `collect_and_generate()` 不接受 `stage_results/profile/base_url` 导致 report stage 失败 | P1 | 旧 `fittrack smoke` 输出 `unexpected keyword argument 'stage_results'` | 扩展函数签名并补真实路径测试 | fixed |
| 2026-06-09 | gate/report | `*_canonical` sidecar 被当作工具结果进入 gate | P1 | 旧 gate metrics `total=3`，当前 smoke 只有 1 个工具 | 过滤 internal stage result keys 和非字符串值 | fixed |
| 2026-06-09 | report | regression report 混入 adapters 历史失败，与 gate 当前结果不一致 | P1 | 独立 Verifier/主控均复现 report FAIL + gate PASS | 有 `stage_results` 时 report 使用当前 stage results | fixed |
| 2026-06-09 | pytest baseline | 默认 pytest 收集 0 个测试 | P1 | `python -m pytest -q` 旧输出 `collected 0 items` | `pytest.ini` testpaths 改为 `tests` | fixed |
| 2026-06-09 | MiniApp E2E | fatal 失败仍 exit 0，可能假绿 | P1 | `node tests\fittrack\miniapp\e2e_full.js --port 19541` 旧输出 failed JSON 但 exit 0 | fatal 和 failed result 设置 `process.exitCode=1` | fixed |
