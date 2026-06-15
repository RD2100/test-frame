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

## 16. Android Maestro Real Profile Gate Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile | **Risk**: medium
- **Preferred for**: explicitly requiring adb CLI, adb device, Maestro CLI, and minimal Maestro flow contract in a real-device profile
- **Forbidden for**: treating optional baseline Android/Maestro BLOCKED results as failures, installing Android SDK, connecting cloud devices, or claiming full Android app regression
- **Fallback**: `android.maestro.real` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (promoting `android.maestro.real` to shared CI required gate) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile android.maestro.real --evidence artifacts/android.maestro.real.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-ANDROID-MAESTRO-REAL-PROFILE-A1`; real-device availability still needs environment-specific review.
- **Boundary note**: profile PASS proves only the four required capability probes pass together; it does not prove a full Android app regression suite.

## 17. MiniApp Automator Real Profile Gate Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile | **Risk**: medium
- **Preferred for**: explicitly requiring WeChat DevTools path, DevTools CLI, automator SDK resolution, and automator endpoint handshake in a MiniApp runtime profile
- **Forbidden for**: treating optional baseline MiniApp `BLOCKED` results as failures, requiring real WeChat login/AppID/project in baseline, or claiming full MiniApp UI E2E coverage
- **Fallback**: `miniapp.automator.real` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (promoting `miniapp.automator.real` to shared CI required gate) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile miniapp.automator.real --evidence artifacts/miniapp.automator.real.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-MINIAPP-AUTOMATOR-REAL-PROFILE-A1`; real endpoint availability still needs environment-specific review.
- **Boundary note**: profile PASS proves only the four required capability probes pass together; it does not prove full MiniApp UI E2E, login, route coverage, selector assertions, or production service readiness.

## 18. MeterSphere Test-Plan Real Profile Gate Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/env_probe/optional_network_auth | **Risk**: medium
- **Preferred for**: explicitly requiring MeterSphere env readiness, opt-in real auth readiness, and test plan id presence before any real test-plan execution work
- **Forbidden for**: calling a real test-plan API, triggering a real test run, storing tokens/project ids/test plan ids in evidence, or claiming API regression success
- **Fallback**: `metersphere.testplan.real` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (promoting `metersphere.testplan.real` or real test-plan execution to shared CI) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile metersphere.testplan.real --evidence artifacts/metersphere.testplan.real.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-METERSPHERE-TESTPLAN-REAL-PROFILE-A1`; real test-plan execution still needs separate review.
- **Boundary note**: profile PASS proves only the required readiness probes pass together; it does not prove test plan existence, execution, report polling, API regression success, or business API correctness.

## 19. H5 Auth Staging Profile Gate Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/env_probe/storage_state_probe | **Risk**: medium
- **Preferred for**: explicitly requiring Playwright browser readiness, H5 staging URL env, credential env, and a structurally valid Playwright storageState file before real H5 auth/E2E work
- **Forbidden for**: visiting production or staging sites, submitting credentials, storing passwords/cookies/localStorage values in evidence, or claiming login/business E2E success
- **Fallback**: `h5.auth.staging` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (promoting `h5.auth.staging` or real H5 auth/E2E execution to shared CI) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile h5.auth.staging --evidence artifacts/h5.auth.staging.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-H5-AUTH-STAGING-PROFILE-A1`; real H5 auth/login execution still needs separate review.
- **Boundary note**: profile PASS proves only browser tooling readiness, staging URL shape, credential env presence, and storageState JSON shape; it does not prove site reachability, login success, session validity, business E2E, or full regression coverage.

## 20. Cloud Device Matrix Contract Gate Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/local_fake_contract/env_probe | **Risk**: medium
- **Preferred for**: validating a local cloud-device compatibility matrix contract and readiness env before any real cloud-device provider work
- **Forbidden for**: calling BrowserStack, Firebase Test Lab, Maestro Cloud, or any real provider; uploading APK/IPA/test packages; consuming quota; storing provider tokens/project ids in evidence; or claiming real compatibility coverage
- **Fallback**: `cloud.device.matrix.real` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (real provider execution, app upload, quota-consuming runs, or shared CI promotion) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile cloud.device.matrix.real --evidence artifacts/cloud.device.matrix.real.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-CLOUD-DEVICE-MATRIX-CONTRACT-A1`; real cloud-device execution still needs separate review.
- **Boundary note**: profile PASS proves only cloud-device env presence and local matrix contract validity; it does not prove provider auth, quota, upload, real device execution, compatibility coverage, or billing-safe readiness.

## 21. Cloud Device Provider Auth Profile Gate Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/opt_in_network_auth | **Risk**: medium
- **Preferred for**: explicitly validating provider-auth readiness before any real cloud-device execution or upload work
- **Forbidden for**: uploading APK/IPA/test packages, creating provider jobs, consuming quota, storing provider tokens/project ids/auth URL query values in evidence, or claiming real compatibility coverage
- **Fallback**: `cloud.device.provider.auth.real` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (real provider execution, app upload, quota-consuming runs, shared CI promotion, or storing provider credentials) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile cloud.device.provider.auth.real --evidence artifacts/cloud.device.provider.auth.real.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-CLOUD-DEVICE-PROVIDER-AUTH-SKELETON-A1`; real cloud-device execution still needs separate review.
- **Boundary note**: profile PASS proves only env presence and explicit provider-auth readiness; it does not prove quota, device capacity, upload success, matrix job creation, real device execution, compatibility coverage, or billing-safe readiness.

## 22. H5 Auth Login Execution Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/local_browser_execution | **Risk**: medium
- **Preferred for**: proving repo-local fake H5 auth login execution and Playwright storageState generation before real H5 auth/E2E work
- **Forbidden for**: visiting staging or production, submitting real credentials, committing generated storageState, storing passwords/cookies/localStorage values in evidence, or claiming real login/business E2E success
- **Fallback**: `h5.auth.login.local` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (real staging login, real credentials, shared CI promotion, or storing reusable auth state) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile h5.auth.login.local --evidence artifacts/h5.auth.login.local.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-H5-AUTH-LOGIN-EXECUTION-SKELETON-A1`; real H5 staging login still needs separate review.
- **Boundary note**: profile PASS proves only repo-local fake auth login execution and generated storageState shape; it does not prove real site reachability, credential validity, backend authorization, session freshness, business H5 E2E, or full regression coverage.

## 23. H5 Real Staging Login Opt-in Skeleton
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/explicit_network_auth | **Risk**: high
- **Preferred for**: explicitly validating real staging login only after human-approved env and selector configuration are present
- **Forbidden for**: default baseline execution, production login, committing generated storageState, storing usernames/passwords/cookies/localStorage values/full URL queries in evidence, or claiming business H5 E2E success
- **Fallback**: `h5.auth.login.staging.real` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (real credentials, real staging execution, shared CI promotion, or storing reusable auth state) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile h5.auth.login.staging.real --evidence artifacts/h5.auth.login.staging.real.json`
- **Status**: approved
- **Approval note**: enabled under user authorization on 2026-06-14 for `P1-H5-REAL-STAGING-LOGIN-OPTIN-A1`; production login and shared CI required execution still need separate review.
- **Boundary note**: profile PASS proves only one explicitly enabled staging login execution and generated storageState shape; it does not prove long-term account validity, full authorization, session freshness, business H5 E2E, or regression coverage.

## 24. Time Goal Manager MiniApp Positive Pilot Prerequisite Gate
- **Platform**: Both
- **Type**: validation | **Access**: required_capability_profile/prerequisite_probe | **Risk**: medium
- **Preferred for**: checking RuntimeAuthorization, WeChat DevTools path presence, automator package resolution, endpoint policy shape, and artifact path policy before a human-authorized positive pilot
- **Forbidden for**: starting WeChat DevTools, connecting a real automator endpoint, running MiniApp E2E, using real accounts/AppIDs/login state, or claiming Real MiniApp E2E readiness
- **Fallback**: `tgm.miniapp.positive_pilot.prereq` evidence JSON with required capability `BLOCKED`/`FAILED` states and non-zero CLI exit
- **Human gate**: yes (real MiniApp E2E, real endpoint connection, real login state, or shared CI promotion) | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence artifacts/tgm-miniapp-positive-pilot-prereq.json`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-TGM-MINIAPP-POSITIVE-PILOT-PREREQ-A1`; real MiniApp E2E still needs separate RuntimeAuthorization.
- **Boundary note**: profile PASS proves only positive pilot prerequisites and `real_env_probe_only` authorization; it does not prove WeChat DevTools launch, automator connection, route coverage, login, selector assertions, business E2E, or release readiness.
- **Reason-code note**: `tgm.miniapp.positive_pilot.prereq` emits local test-frame evidence `reason_code` values for BLOCKED/FAILED prerequisite states (`RUNTIME_AUTHORIZATION_MISSING`, `RUNTIME_AUTHORIZATION_FILE_MISSING`, `RUNTIME_AUTHORIZATION_DRY_RUN_ONLY`, `RUNTIME_AUTHORIZATION_INVALID`, `WECHAT_DEVTOOLS_PATH_MISSING`, `AUTOMATOR_PACKAGE_MISSING`, `ENDPOINT_POLICY_MISSING`, `ARTIFACT_ROOT_MISSING`, `WECHAT_DEVTOOLS_PATH_INVALID`, `ENDPOINT_POLICY_INVALID`, `ARTIFACT_PATH_OUT_OF_SCOPE`). `RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY` and `RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED` are local PASS reason codes for authorization-file presence only. These codes are verification evidence only, not a global agent-acceptance GateResult schema.

## 25. Module GPT Evidence Pack Manifest Gate
- **Platform**: Both
- **Type**: validation | **Access**: local_zip_manifest_validation | **Risk**: low
- **Preferred for**: checking that module GPT handoff ZIP packages include reports, reviewer index, status summary, command summary, git patch, manifest JSON, and raw evidence JSON
- **Forbidden for**: treating evidence package presence as product PASS, rewriting test results, or turning `BLOCKED`/`FAILED` evidence into success
- **Fallback**: `python -m cli.main evidence validate --pack <zip>` exits non-zero with missing entries listed
- **Human gate**: no for local package shape validation; yes if package contents require external runtime, secrets, or cross-module schemas | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main evidence validate --pack artifacts/evidence-pack.zip`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-EVIDENCE-PACK-MANIFEST-A1`.
- **Boundary note**: validator proves package completeness only; `BLOCKED` and `FAILED` can be valid evidence states and must not be promoted to PASS.
- **Sensitive-scan note**: validator scans text entries in the ZIP for local absolute paths, runtime paths, and raw secret values. This is test-frame evidence hygiene only; it is not final acceptance and does not define an agent-acceptance global schema.

## 26. Time Goal Manager MiniApp Prerequisite Report
- **Platform**: Both
- **Type**: reporting | **Access**: local_evidence_summary | **Risk**: low
- **Preferred for**: generating Markdown and JSON reviewer summaries from `tgm.miniapp.positive_pilot.prereq` evidence
- **Forbidden for**: claiming Real MiniApp E2E readiness, launching WeChat DevTools, connecting automator endpoints, or reporting dry-run as runtime success
- **Fallback**: raw `tgm-miniapp-positive-pilot-prereq.json` capability evidence
- **Human gate**: yes for real MiniApp runtime authorization; no for local report generation | **Must explain if skipped**: yes
- **Evidence**: `python tools/generate_miniapp_prereq_report.py --evidence artifacts/tgm-miniapp-positive-pilot-prereq.json --out reports/tgm-miniapp-prereq-report.md --json-out reports/tgm-miniapp-prereq-report.json`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-TGM-MINIAPP-PREREQ-REPORT-A1`.
- **Boundary note**: report output is reviewer-facing prerequisite evidence only. `final_verdict_for_real_e2e=NOT_READY` and `permits_real_e2e=false` are mandatory unless a separate RuntimeAuthorization TaskSpec changes the boundary.

## 27. Time Goal Manager MiniApp RuntimeAuthorization Package
- **Platform**: Both
- **Type**: validation | **Access**: local_json_schema_validation | **Risk**: medium
- **Preferred for**: validating the request package format and safety bounds needed before any human-authorized TGM MiniApp positive pilot
- **Forbidden for**: granting authorization by itself, launching WeChat DevTools, connecting automator endpoints, or proving real MiniApp E2E success
- **Fallback**: manual reviewer checklist using `docs/test-frame/tgm-miniapp-runtime-authorization.template.json`
- **Human gate**: yes for any `real_e2e_authorized` package; no for validating redacted examples | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main authorization validate --file docs/test-frame/tgm-miniapp-runtime-authorization.example.redacted.json`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-TGM-MINIAPP-RUNTIME-AUTH-PACK-A1`.
- **Boundary note**: validator PASS means the authorization package shape and safety bounds are acceptable. `TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE` lets the prerequisite profile read a redacted local authorization package and emit sanitized evidence. It does not mean real E2E was executed, and `real_env_probe_only` still sets `permits_real_e2e=false`. `real_e2e_authorized` is only recognized as an authorization record; a separate positive-pilot TaskSpec is still required before any real MiniApp E2E run.

## 28. Time Goal Manager MiniApp Positive Pilot Plan
- **Platform**: Both
- **Type**: planning | **Access**: local_plan_generation | **Risk**: medium
- **Preferred for**: generating a dry positive-pilot execution plan from `tgm.miniapp.positive_pilot.prereq` evidence before any real MiniApp runtime authorization
- **Forbidden for**: executing MiniApp E2E, launching WeChat DevTools, connecting automator endpoints, or treating plan READY as real E2E completion
- **Fallback**: reviewer reads raw prerequisite evidence and manually checks `planned_steps` boundaries
- **Human gate**: yes for any future real MiniApp runtime execution; no for local plan generation | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main plan miniapp-positive-pilot --prereq-evidence artifacts/tgm-miniapp-prereq-real-env-probe-only.json --out reports/tgm-miniapp-positive-pilot-plan.md --json-out reports/tgm-miniapp-positive-pilot-plan.json`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-TGM-MINIAPP-POSITIVE-PILOT-PLAN-A1`.
- **Boundary note**: plan generation is not execution. `READY_FOR_REAL_ENV_PROBE` must keep `permits_real_e2e=false`; `READY_FOR_REAL_E2E_AUTHORIZED_RUN` is a future command template only and still requires a separate positive-pilot TaskSpec before execution.

## 29. Time Goal Manager MiniApp Positive Pilot Dry Runner
- **Platform**: Both
- **Type**: planning | **Access**: local_dry_manifest_generation | **Risk**: medium
- **Preferred for**: converting a positive-pilot plan JSON into a dry execution manifest that reviewers can inspect before real runtime authorization
- **Forbidden for**: executing planned commands, launching WeChat DevTools, connecting automator endpoints, running Jest E2E, or claiming real execution success
- **Fallback**: reviewer reads plan JSON directly and verifies all runtime steps remain template-only
- **Human gate**: yes for any future real MiniApp runtime execution; no for local dry-runner manifest generation | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main pilot miniapp-positive-pilot-dry-run --plan reports/tgm-miniapp-positive-pilot-plan-real-env-probe-only.json --out artifacts/tgm-miniapp-positive-pilot-dry-run-manifest.json`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-TGM-MINIAPP-POSITIVE-PILOT-DRY-RUNNER-A1`.
- **Boundary note**: dry-runner output is not a real execution report. `executed_real_runtime` and every step's `actually_executed` must remain false.

## 30. Time Goal Manager MiniApp Positive Pilot Artifact Manifest Contract
- **Platform**: Both
- **Type**: validation | **Access**: local_json_contract_validation | **Risk**: medium
- **Preferred for**: validating the artifact manifest shape for a future TGM MiniApp positive pilot evidence package
- **Forbidden for**: claiming real MiniApp E2E success, launching WeChat DevTools, connecting an automator endpoint, running Jest E2E, accepting prohibited artifacts, or treating optional artifact absence as failure
- **Fallback**: reviewer reads the JSON manifest and checks required, optional, prohibited, and sensitive-scan fields manually
- **Human gate**: yes for any real MiniApp runtime execution or RuntimeAuthorization change; no for local manifest contract validation | **Must explain if skipped**: yes
- **Evidence**: `python -m cli.main manifest miniapp-positive-pilot validate --manifest artifacts/tgm-miniapp-positive-pilot-artifact-manifest.json`
- **Status**: approved
- **Approval note**: enabled under module GPT handoff on 2026-06-15 for `TESTFRAME-TGM-MINIAPP-POSITIVE-PILOT-ARTIFACT-MANIFEST-A1`.
- **Boundary note**: manifest validation PASS proves only that evidence structure and artifact hygiene are acceptable. It does not prove real MiniApp E2E ran or passed. A real E2E run still needs separate RuntimeAuthorization and a positive-pilot execution TaskSpec.

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
| 16 | Android Maestro Real Profile Gate Skeleton | Both | validation | medium | approved | local_probe |
| 17 | MiniApp Automator Real Profile Gate Skeleton | Both | validation | medium | approved | local_probe |
| 18 | MeterSphere Test-Plan Real Profile Gate Skeleton | Both | validation | medium | approved | local_probe |
| 19 | H5 Auth Staging Profile Gate Skeleton | Both | validation | medium | approved | local_probe |
| 20 | Cloud Device Matrix Contract Gate Skeleton | Both | validation | medium | approved | local_probe |
| 21 | Cloud Device Provider Auth Profile Gate Skeleton | Both | validation | medium | approved | local_probe |
| 22 | H5 Auth Login Execution Skeleton | Both | validation | medium | approved | local_probe |
| 23 | H5 Real Staging Login Opt-in Skeleton | Both | validation | high | approved | local_probe |
| 24 | Time Goal Manager MiniApp Positive Pilot Prerequisite Gate | Both | validation | medium | approved | local_probe |
| 25 | Module GPT Evidence Pack Manifest Gate | Both | validation | low | approved | local_zip_manifest_validation |
| 26 | Time Goal Manager MiniApp Prerequisite Report | Both | reporting | low | approved | local_evidence_summary |
| 27 | Time Goal Manager MiniApp RuntimeAuthorization Package | Both | validation | medium | approved | local_json_schema_validation |
| 28 | Time Goal Manager MiniApp Positive Pilot Plan | Both | planning | medium | approved | local_plan_generation |
| 29 | Time Goal Manager MiniApp Positive Pilot Dry Runner | Both | planning | medium | approved | local_dry_manifest_generation |
| 30 | Time Goal Manager MiniApp Positive Pilot Artifact Manifest Contract | Both | validation | medium | approved | local_json_contract_validation |

### Status Legend

| Status | Meaning |
|--------|---------|
| approved | Reviewer-approved, enabled |
| proposed | Awaiting approval; NOT usable |
| disabled | Previously approved, now off |
| rejected | Proposal rejected; do not use |
