# Capability Inventory -- test-frame

> Bootstrap: 2026-06-14 | Template v1.0
> 10 universal capabilities pre-registered. Add project-specific (#11+) with Status: proposed.
> All: auto_use_allowed=false, execution_allowed=false, mutation_allowed=false.

## Registration Procedure

1. **Propose**: Add entry with Status: proposed + all required fields
2. **Review**: Submit to human reviewer
3. **Approve**: Reviewer changes Status: proposed -> Status: approved
4. **Enable**: Enable on target platform (codex plugin add / register-hooks.ps1)
5. **Verify**: Confirm via codex plugin list (Codex) or settings.json (Claude)
6. **Report**: Include in batch ExecutionReport

Rule reference: rules/core.md core-007. Status: proposed = NOT usable until approved.

## Platform Key

| Label | Meaning |
|-------|---------|
| Both | Available on Claude Code and Codex |
| Claude | Claude Code only |
| Codex | Codex only |

---

## 1. CodeGraph
- **Platform**: Both
- **Type**: code_intelligence | **Access**: read_only | **Risk**: high
- **Preferred for**: structural code understanding, symbol lookup, caller/callee analysis
- **Forbidden for**: literal string search, current fact without freshness check
- **Fallback**: rg, Read, Grep
- **Human gate**: yes (reindex) | **Must explain if skipped**: yes
- **Evidence**: codegraph_status output, index_freshness

## 2. rg / Grep / Read
- **Platform**: Both
- **Type**: search | **Access**: read_only | **Risk**: low
- **Preferred for**: literal string search, pattern matching, file content reading
- **Forbidden for**: structural code understanding (use CodeGraph first), secret file reading
- **Fallback**: Select-String (PowerShell)
- **Human gate**: no | **Must explain if skipped**: no
- **Evidence**: command output

## 3. Shell (read-only)
- **Platform**: Both
- **Type**: shell | **Access**: read_only | **Risk**: medium
- **Preferred for**: Test-Path, Get-Content, Get-FileHash, Measure-Object, Get-ChildItem
- **Forbidden for**: Set-Content, Remove-Item, Invoke-WebRequest, Start-Process, script execution
- **Fallback**: bash test/ls/wc
- **Human gate**: yes (any write) | **Must explain if skipped**: no
- **Evidence**: command output

## 4. JSON Schema Validation
- **Platform**: Both
- **Type**: validation | **Access**: read_only | **Risk**: low
- **Preferred for**: schema parse audit, JSON structure validation
- **Forbidden for**: schema modification without approval
- **Fallback**: manual review
- **Human gate**: no | **Must explain if skipped**: no
- **Evidence**: ConvertFrom-Json output

## 5. Runtime Docs
- **Platform**: Both
- **Type**: documentation | **Access**: read_only | **Risk**: low
- **Preferred for**: policy lookup, contract reference, gate definition
- **Forbidden for**: current fact without cross-reference
- **Fallback**: direct file read
- **Human gate**: no | **Must explain if skipped**: no
- **Evidence**: doc path + section reference

## 6. Runtime Rules
- **Platform**: Both
- **Type**: rules | **Access**: read_only | **Risk**: low
- **Preferred for**: rule violation check, coding standard, security hard stop
- **Forbidden for**: overriding reviewer decision, auto-approving gates
- **Fallback**: docs search
- **Human gate**: no | **Must explain if skipped**: no
- **Evidence**: rule ID + file reference

## 7. Negative Tests
- **Platform**: Both
- **Type**: testing | **Access**: reference_only | **Risk**: low
- **Preferred for**: validating reviewer checklists, gate enforcement testing
- **Forbidden for**: execution, substituting for actual tests
- **Fallback**: N/A
- **Human gate**: no | **Must explain if skipped**: no
- **Evidence**: test ID + expected_gate_decision

## 8. Reviewer Playbooks
- **Platform**: Both
- **Type**: review | **Access**: reference_only | **Risk**: low
- **Preferred for**: reviewer decision-making, gate evaluation
- **Forbidden for**: auto-approving gates, skipping reviewer
- **Fallback**: verification-gates.md
- **Human gate**: no | **Must explain if skipped**: no
- **Evidence**: playbook reference + decision path

## 9. Governance Hooks (Draft)
- **Platform**: Claude
- **Type**: hook | **Access**: reference_only (audit-only draft) | **Risk**: medium
- **Preferred for**: audit draft reference
- **Forbidden for**: registration without human gate, blocking without reviewer approval
- **Fallback**: N/A
- **Human gate**: yes (registration/activation) | **Must explain if skipped**: no
- **Evidence**: AUDIT-ONLY DRAFT header

## 10. Phase 6 SourceLock / Quarantine
- **Platform**: Both
- **Type**: source_lock | **Access**: reference_only (design only) | **Risk**: critical
- **Preferred for**: external code intake planning
- **Forbidden for**: clone, install, execute, enable MCP without human gate
- **Fallback**: N/A
- **Human gate**: yes (clone, any Phase 6C action) | **Must explain if skipped**: no
- **Evidence**: Phase 6 design docs

---

<!-- Add project-specific capabilities (#11+) below. Set Status: proposed. Reviewer changes to approved. -->

## 11. TestFrame Capability Probe Matrix
- **Platform**: Both
- **Type**: validation | **Access**: local_command_probe | **Risk**: medium
- **Preferred for**: recording whether local external test tools are PASS, FAILED, BLOCKED, UNSUPPORTED, or NOT_REQUIRED
- **Forbidden for**: treating missing tools, missing credentials, or missing devices as PASS
- **Fallback**: documented manual command audit in `docs/governance/DOC_COMMAND_AUDIT.md`
- **Human gate**: yes (making a capability required in CI) | **Must explain if skipped**: yes
- **Evidence**: `artifacts/capabilities.local.json` or equivalent `--evidence` output
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14; making optional probes required in CI still needs a separate human gate.
- **Approval scope**: probe framework only; individual external capabilities are not approved as real execution gates until their own required profile and evidence are reviewed.

## 12. H5 Chromium Smoke and Allure Report Gate
- **Platform**: Both
- **Type**: validation | **Access**: local_browser_probe/report_generation | **Risk**: medium
- **Preferred for**: proving Chromium browser launch, repo-local H5 smoke execution, and non-fake Allure HTML/fallback report status
- **Forbidden for**: treating `playwright.cli` as browser/E2E proof, treating missing Allure CLI as HTML PASS, or using external websites/accounts/services as the H5 smoke target
- **Fallback**: `allure-generation.json` with status `BLOCKED` or `FAILED`; Playwright browser probe evidence under `--evidence`
- **Human gate**: yes (making browser smoke or Allure HTML required in shared CI) | **Must explain if skipped**: yes
- **Evidence**: `npm run test:h5:smoke`, `python -m cli.main check --capability playwright.browser.chromium ...`, `python -m cli.main report --require-html ...`, `allure-generation.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-H5-REAL-BROWSER-ALLURE-A1`; GPT/reviewer acceptance is still required before promoting this to a shared CI required gate.
- **Boundary note**: `playwright.browser.chromium` proves browser launch only; `h5.smoke` proves the repo-local fixture only; `allure.html` requires zero exit and `index.html`; default `allure.fallback` is evidence preservation, not HTML success; `--require-html` makes BLOCKED/FAILED report generation exit non-zero.

## 13. Android ADB and Maestro Probe Layers
- **Platform**: Both
- **Type**: validation | **Access**: local_command_probe/device_probe | **Risk**: medium
- **Preferred for**: distinguishing adb CLI availability, Android device availability, Maestro CLI availability, and minimal Maestro flow execution
- **Forbidden for**: treating `android.adb.cli` as device/E2E proof, treating `maestro.cli` as flow proof, or requiring a real device in baseline preflight
- **Fallback**: capability evidence JSON with `BLOCKED` for missing adb, missing device, missing Maestro, or missing flow preconditions
- **Human gate**: yes (making Android device or Maestro flow required in shared CI) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --capability android.adb.cli,android.adb.devices,maestro.cli ...`, `artifacts/android.probe.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-ANDROID-ADB-MAESTRO-PROBE-A1`; real-device CI promotion still needs separate review.
- **Boundary note**: `android.adb.cli` proves only adb executable availability; `android.adb.devices` proves at least one device-state target; `maestro.cli` proves only CLI availability; `maestro.flow.contract` is the first Maestro execution gate.

## 14. MiniApp DevTools and Automator Probe Layers
- **Platform**: Both
- **Type**: validation | **Access**: local_command_probe/runtime_endpoint_probe | **Risk**: medium
- **Preferred for**: distinguishing WeChat DevTools path configuration, DevTools CLI execution, automator SDK availability, and automator endpoint reachability
- **Forbidden for**: treating `miniapp.devtools.path` or `miniapp.automator.sdk` as MiniApp UI E2E proof, or requiring a real endpoint in baseline preflight
- **Fallback**: capability evidence JSON with `BLOCKED` for missing DevTools path/CLI, missing SDK, missing endpoint, or unavailable endpoint
- **Human gate**: yes (making MiniApp endpoint or UI E2E required in shared CI) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --capability miniapp.devtools.path,miniapp.devtools.cli,miniapp.automator.sdk,miniapp.automator.endpoint ...`, `artifacts/miniapp.probe.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-MINIAPP-DEVTOOLS-AUTOMATOR-PROBE-A1`; full MiniApp UI E2E promotion still needs separate review.
- **Boundary note**: `miniapp.devtools.path` proves only path existence; `miniapp.devtools.cli` proves only lightweight CLI invocation; `miniapp.automator.sdk` proves only package resolution; `miniapp.automator.endpoint` is the first runtime endpoint handshake gate.

## 15. MeterSphere Adapter Contract and Real Auth Probe
- **Platform**: Both
- **Type**: validation | **Access**: local_fake_contract/optional_network_auth | **Risk**: medium
- **Preferred for**: proving local MeterSphere adapter status mapping, env readiness, and explicitly enabled real auth reachability
- **Forbidden for**: treating `metersphere.env` or `metersphere.fake.contract` as real MeterSphere platform integration, storing tokens in code/evidence, or calling a real service without explicit enablement
- **Fallback**: capability evidence JSON with `BLOCKED` for missing env, unreachable service, or real auth not enabled
- **Human gate**: yes (real service auth/test-plan execution in shared CI) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --capability metersphere.env,metersphere.fake.contract ...`, `artifacts/metersphere.probe.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-METERSPHERE-ADAPTER-CONTRACT-A1`; real test-plan execution still needs separate review.
- **Boundary note**: `metersphere.env` proves only required env presence; `metersphere.fake.contract` proves local fake response normalization; `metersphere.real.auth` is optional and proves authentication reachability only, not test execution.

---

## Summary

| # | Capability | Platform | Type | Risk | Status | Phase 0-5 |
|---|-----------|:---:|------|:---:|:---:|:---:|
| 1 | CodeGraph | Both | code_intelligence | high | approved | read-only |
| 2 | rg/Grep/Read | Both | search | low | approved | read-only |
| 3 | Shell | Both | shell | medium | approved | read-only |
| 4 | JSON Validation | Both | validation | low | approved | read-only |
| 5 | Runtime Docs | Both | docs | low | approved | read-only |
| 6 | Runtime Rules | Both | rules | low | approved | read-only |
| 7 | Negative Tests | Both | testing | low | approved | reference |
| 8 | Reviewer Playbooks | Both | review | low | approved | reference |
| 9 | Hooks (Draft) | Claude | hook | medium | approved | audit-only |
| 10 | Phase 6 SourceLock | Both | source_lock | critical | approved | design_only |
| 11 | TestFrame Capability Probe Matrix | Both | validation | medium | approved | local_probe |
| 12 | H5 Chromium Smoke and Allure Report Gate | Both | validation | medium | approved | local_probe |
| 13 | Android ADB and Maestro Probe Layers | Both | validation | medium | approved | local_probe |
| 14 | MiniApp DevTools and Automator Probe Layers | Both | validation | medium | approved | local_probe |
| 15 | MeterSphere Adapter Contract and Real Auth Probe | Both | validation | medium | approved | local_probe |

### Status Legend

| Status | Meaning |
|--------|---------|
| approved | Reviewer-approved, enabled |
| proposed | Awaiting approval; NOT usable |
| disabled | Previously approved, now off |
| rejected | Proposal rejected; do not use |
