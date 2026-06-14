# 文档命令审计记录

> 审计日期：2026-06-14
> 目的：核对 README / VERIFY / SETUP / PIPELINE 中声明的本地命令是否真实可执行，并区分“项目能力问题”和“当前环境未就绪”。

## 已验证通过

| 命令 | 结果摘要 | 验证内容 |
|---|---|---|
| `python --version` | `Python 3.10.11` | Python 运行时可用 |
| `node --version` | `v24.15.0` | Node.js 运行时可用 |
| `npm --version` | `11.12.1` | npm 可用 |
| `python -m cli.main --help` | 列出 `attribute/check/report/run/watch` | CLI 入口可加载 |
| `python -m cli.main check --project=app-android` | `[OK] Config check passed` | Android 示例配置可加载 |
| `python -m cli.main check --project=app-miniapp` | `[OK] Config check passed` | 小程序示例配置可加载 |
| `python -m cli.main check --project=app-api` | `[OK] Config check passed` | API 示例配置可加载 |
| `python -m cli.main run --project=app-android --profile=smoke --dry-run` | 打印 `maestro` 阶段计划 | Android smoke 任务流可规划 |
| `python -m cli.main run --project=app-miniapp --profile=smoke --dry-run` | 打印 `miniprogram-automator` 阶段计划 | 小程序 smoke 任务流可规划 |
| `python -m cli.main run --project=app-api --profile=smoke --dry-run` | 打印 `metersphere` 阶段计划 | API smoke 任务流可规划 |
| `python -m cli.main attribute --project=app-android` | 生成归因报告，失败用例 0 | 归因入口可执行 |
| `python -m cli.main report --project=app-android` | 输出 Allure 缺失警告，仍生成报告目录 | 报告入口可执行且能降级 |
| `npx playwright --version` | `Version 1.60.0` | Playwright 本地包可用 |
| `npx jest --listTests --config=jest.config.js` | 发现 `tests/h5/support/__tests__/oracles.test.js` | Jest 配置能发现 JS oracle 测试 |
| `docker --version` | `Docker version 29.5.3` | Docker CLI 可用 |
| `python -c "import airtest; print('OK')"` | `OK` | Airtest Python 包可导入 |

## 已验证未通过 / 环境缺失

| 命令 | 结果摘要 | 判断 |
|---|---|---|
| `adb --version` | `adb` 不在 PATH | 当前机器不能直接跑 Android 真机/模拟器链路；不等于框架代码失败 |
| `maestro --version` | `maestro` 不在 PATH | Android Maestro smoke 真实执行链路当前不可用 |
| `allure --version` | `allure` 不在 PATH | HTML Allure 报告生成不可用；项目 `report` 入口已降级为警告 |

## 本轮未执行

| 命令/能力 | 未执行原因 | 对结论影响 |
|---|---|---|
| `python -m cli.main run --project=app-android --profile=smoke` | 需要 ADB / Maestro / 设备环境；当前 `adb` 与 `maestro` 缺失 | 无法证明 Android 真实设备执行链路可用 |
| `npx playwright test tests/h5/playwright/` | 文档路径与当前仓库实际测试布局不完全一致；本轮仅验证 Playwright 包与 Jest 发现 | 无法证明 H5 E2E 全链路可用 |
| `npx jest tests/miniapp/specs/ --json` | 文档路径未在当前命令审计中作为稳定入口验证；当前稳定入口是 `npm run test:miniapp` | 小程序 Jest 入口需以后续总验证为准 |
| `python -m cli.main run --project=app-miniapp --profile=smoke` | 需要微信开发者工具运行时 / automator endpoint | 无法证明小程序 UI 自动化真实链路可用 |
| `python -m cli.main run --project=app-api --profile=smoke` | 依赖 MeterSphere/API 服务环境 | 无法证明外部 API 平台集成可用 |
| `bash ci/scripts/run-tests.sh app-android smoke` | Windows 当前审计不把 Bash 脚本作为本地默认入口；且设备依赖缺失 | CI 脚本跨平台可用性仍待确认 |
| `allure serve reports/allure-results/` | Allure CLI 缺失，且会启动本地服务 | HTML 报告浏览能力未验证 |

## 结论

当前文档中“框架本体入口、配置检查、dry-run、报告/归因降级、JS/Playwright 包可用性”基本可信；“真实 Android 设备、小程序运行时、MeterSphere、Allure HTML、跨平台 Bash CI”仍属于环境依赖或外部集成能力，不能作为当前机器已通过的质量结论。

## Capability Probe Matrix 入口

2026-06-14 后新增统一 capability probe 入口，用于把外部能力缺失记录为可机读状态，而不是混入普通 PASS：

```powershell
python -m cli.main check --capability all --evidence artifacts/capabilities.local.json
python -m cli.main check --capability android.adb.devices --required android.adb.devices --evidence artifacts/android.required.json
python -m cli.main check --capability miniapp.automator.endpoint --required miniapp.automator.endpoint --evidence artifacts/miniapp.endpoint.required.json
```

## P1 H5 Browser Smoke / Allure Boundaries

Added 2026-06-14 for `P1-H5-REAL-BROWSER-ALLURE-A1`.

| Capability or command | What it proves | What it does not prove |
|---|---|---|
| `playwright.cli` | The Playwright package/CLI can answer `npx playwright --version`. | It does not prove any browser binary is installed or launchable. |
| `playwright.browser.chromium` | Playwright can launch and close Chromium headless through `scripts/probe-playwright-browser.mjs`. | It does not prove a project H5 scenario passed. |
| `npm run test:h5:smoke` | Chromium opens the repo-local `examples/app-h5/index.html` fixture and verifies a real click/state assertion. | It does not prove FitTrack admin, external backends, auth, or the full H5 explorer suite. |
| `allure.html` | `allure generate` exited 0 and `allure-report/index.html` exists. | A called command alone is not enough. |
| `allure.fallback` | HTML was not generated, but `summary.json`, `allure-results/`, and `allure-generation.json` preserve machine-readable evidence. | It is not an HTML report PASS. |

Hard rule: do not report `playwright.cli PASS` as H5 E2E PASS, and do not report Allure HTML generated unless `index.html` exists after a zero-exit generation command.

Default report mode preserves evidence: Allure `BLOCKED` writes `allure-generation.json` and exits 0. Required HTML mode is stricter: `python -m cli.main report --project=app-h5 --output artifacts\reports\app-h5 --require-html` exits non-zero for `BLOCKED` or `FAILED`.

## P1 Android ADB / Maestro Probe Boundaries

Added 2026-06-14 for `P1-ANDROID-ADB-MAESTRO-PROBE-A1`.

| Capability | What it proves | What it does not prove |
|---|---|---|
| `android.adb.cli` | `adb version` can execute. | Device availability or Android E2E success. |
| `android.adb.devices` | At least one `adb devices -l` entry is in `device` state. | App installation, login, or UI flow success. |
| `maestro.cli` | `maestro --version` can execute. | Maestro can run a flow. |
| `maestro.flow.contract` | The minimal flow can run when CLI, device, and flow preconditions exist. | Full Android regression coverage. |

Hard rule: do not report `android.adb.cli PASS` as Android device/E2E PASS, and do not report `maestro.cli PASS` as Maestro flow PASS.

## P1 MiniApp DevTools / Automator Probe Boundaries

Added 2026-06-14 for `P1-MINIAPP-DEVTOOLS-AUTOMATOR-PROBE-A1`.

| Capability | What it proves | What it does not prove |
|---|---|---|
| `miniapp.devtools.path` | A configured WeChat DevTools path exists. | CLI execution, automator endpoint, or MiniApp UI E2E success. |
| `miniapp.devtools.cli` | The resolved WeChat DevTools CLI can complete a lightweight help probe. | A project can open or automation can attach. |
| `miniapp.automator.sdk` | Node can resolve the configured miniprogram automator package. | DevTools is running or reachable. |
| `miniapp.automator.endpoint` | The configured `MINIAPP_AUTOMATOR_ENDPOINT` can complete the runtime probe handshake. | Full route coverage, selector assertions, login, or business E2E success. |

Hard rule: do not report `miniapp.devtools.path PASS` or `miniapp.automator.sdk PASS` as MiniApp automation PASS, and do not report `miniapp.automator.endpoint PASS` as full MiniApp UI E2E PASS.

状态语义：

| 状态 | 含义 |
|---|---|
| `PASS` | 该能力在当前环境真实可用 |
| `FAILED` | 工具存在，但命令执行失败 |
| `BLOCKED` | 缺少工具、环境变量、设备或外部服务 |
| `UNSUPPORTED` | 当前平台或项目暂不支持 |
| `NOT_REQUIRED` | 本轮 profile 未要求该能力 |

当前 probe 覆盖：`android.adb.cli`、`android.adb.devices`、`maestro.cli`、`maestro.flow.contract`、`allure`、`playwright.cli`、`playwright.browser.chromium`、`miniapp.devtools.path`、`miniapp.devtools.cli`、`miniapp.automator.sdk`、`miniapp.automator.endpoint`、`metersphere.env`。其中 `playwright.cli` 只证明 Playwright CLI/package 可用，不证明浏览器二进制或 H5 E2E 已通过；`miniapp.devtools.path` 只证明微信开发者工具路径配置状态，不证明 automator endpoint 可连接。没有外部工具时，baseline preflight 可以继续通过，但 evidence 必须明确记录 `BLOCKED`；若通过 `--required` 指定为必需能力，`BLOCKED/FAILED/UNSUPPORTED` 会导致命令失败。

后续若要把这些从“行业可自动化但当前不能测”变成 TestFrame 能力，应优先补：

1. 环境探针：ADB / Maestro / WeChat DevTools / MeterSphere / Allure 的统一 `check` 输出。
2. 可复现 harness：对每类外部工具提供 fake backend 或 local simulator，先验证框架协议，再接真实环境。
3. 证据分层：把 `dry-run PASS`、`environment BLOCKED`、`real execution PASS/FAIL` 明确分开，避免假绿。
