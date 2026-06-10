/**
 * Explorer UI Test — Goal-based Structured Exploration MVP
 *
 * Reads goals and routes from config (or env), visits each page,
 * observes page state, performs safe interactions, collects issues
 * with severity/reproSteps/evidence.
 *
 * Output: reports/ui-explorer/explorer-results.json
 */

const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { setupApiMocks, teardownApiMocks, getMockStats } = require('./support/api-mocks');
const { setupAuth, getAuthInfo } = require('./support/auth');

// --- Configuration (env overrides config) ---
const BASE_URL = process.env.EXPLORER_BASE_URL || 'http://localhost:5190';
const MAX_DEPTH = parseInt(process.env.EXPLORER_MAX_DEPTH || '2', 10);
const MAX_ACTIONS = parseInt(process.env.EXPLORER_MAX_ACTIONS || '20', 10);

const DEFAULT_ROUTES = [
  { path: '/', goal: '确认仪表盘核心数据可见，快捷操作可用' },
  { path: '/login', goal: '确认登录表单校验、错误提示、成功跳转' },
  { path: '/exercises', goal: '确认列表搜索、筛选、分页、编辑入口' },
  { path: '/exercises/create', goal: '确认表单必填校验、取消返回、保存反馈' },
];

// Hardcoded safe defaults — used only as fallback when YAML parsing fails.
// When YAML succeeds, YAML forbiddenActions are the sole source of truth.
const FORBIDDEN_DEFAULTS = ['delete', 'remove', 'clear', 'pay', 'publish', 'logout', 'sign out',
  '删除', '清空', '支付', '发布', '确认删除'];

let FORBIDDEN = FORBIDDEN_DEFAULTS;
let forbiddenActionsSource = 'default'; // 'config' | 'default'

// Auth mode: resolved from env > YAML > default('real')
let authMode = process.env.EXPLORER_AUTH_MODE || 'real';

// Try to load config from env or fittrack.yaml
let routes = DEFAULT_ROUTES;
let configWarnings = [];

// EXPLORER_ROUTES env var takes highest priority
if (process.env.EXPLORER_ROUTES) {
  routes = process.env.EXPLORER_ROUTES.split(',').map((r) => {
    const trimmed = r.trim();
    return { path: trimmed, goal: `探索页面: ${trimmed}` };
  });
  console.log(`[EXPLORER] Loaded ${routes.length} routes from EXPLORER_ROUTES env`);
} else {
try {
  const configPath = path.resolve(__dirname, '../../config/projects/fittrack.yaml');
  if (fs.existsSync(configPath)) {
    const content = fs.readFileSync(configPath, 'utf8');
    // Simple YAML parsing for the explorer block (avoid full YAML dep)
    const inExplorer = content.indexOf('explorer:');
    if (inExplorer > 0) {
      const explorerSection = content.substring(inExplorer);
      const routeMatches = explorerSection.match(/routes:[\s\S]*?forbiddenActions:/);
      if (routeMatches) {
        const parsed = [];
        const lineRe = /-\s+path:\s*"([^"]+)"\s*\n\s+goal:\s*"([^"]+)"/g;
        let m;
        while ((m = lineRe.exec(routeMatches[0])) !== null) {
          parsed.push({ path: m[1], goal: m[2] });
        }
        if (parsed.length > 0) routes = parsed;
      }

      // Parse forbiddenActions from YAML — YAML is the sole source of truth
      try {
        const faIdx = explorerSection.indexOf('forbiddenActions:');
        if (faIdx >= 0) {
          const faSection = explorerSection.substring(faIdx);
          const faMatches = [...faSection.matchAll(/^\s*-\s*"([^"]+)"/gm)];
          if (faMatches.length > 0) {
            FORBIDDEN = faMatches.map((m) => m[1]);
            forbiddenActionsSource = 'config';
          }
        }
      } catch (_) {
        configWarnings.push('parsing_forbiddenActions_failed');
      }

      // Parse authMode from YAML (env EXPLORER_AUTH_MODE takes precedence)
      if (!process.env.EXPLORER_AUTH_MODE) {
        try {
          const amIdx = explorerSection.indexOf('authMode:');
          if (amIdx >= 0) {
            const amLine = explorerSection.substring(amIdx);
            const amMatch = amLine.match(/authMode:\s*(\S+)/);
            if (amMatch && ['real', 'injected', 'mock'].includes(amMatch[1])) {
              authMode = amMatch[1];
            }
          }
        } catch (_) {
          configWarnings.push('parsing_authMode_failed');
        }
      }
    }
    console.log(`[EXPLORER] Loaded ${routes.length} routes, ${FORBIDDEN.length} forbidden actions (source: ${forbiddenActionsSource}), authMode=${authMode}`);
  }
} catch (e) {
  console.log(`[EXPLORER] Using default routes (${routes.length})`);
  configWarnings.push('using_default_forbiddenActions');
}
} // end else (config parsing)

const REPORT_DIR = process.env.EXPLORER_REPORT_DIR || 'reports/ui-explorer';
const REPORT_FILE = path.join(REPORT_DIR, 'explorer-results.json');

// --- Safety ---
const DANGEROUS = new RegExp(FORBIDDEN.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'i');

function isSafe(text) {
  return text && typeof text === 'string' && !DANGEROUS.test(text);
}

const SAFE_VALUES = {
  name: 'TestExplorer', title: 'TestItem', description: 'Auto-explorer test',
  email: 'test@example.com', search: 'test', weight: '10', sets: '3',
  reps: '12', duration: '30', notes: 'explorer note',
};

// --- Dedup tracker for P3 no-feedback issues ---
const dedupedIssues = new Set();

// --- Exploration state ---
const log = {
  baseUrl: BASE_URL,
  maxDepth: MAX_DEPTH,
  maxActions: MAX_ACTIONS,
  startTime: new Date().toISOString(),
  pages: [],
  summary: {
    routesVisited: 0,
    actionsAttempted: 0,
    actionsPassed: 0,
    actionsFailed: 0,
    actionsSkipped: 0,
    actionsBlocked: 0,
    issuesFound: 0,
    bySeverity: { P0: 0, P1: 0, P2: 0, P3: 0 },
  },
};

/**
 * Explore a single page with a specific goal.
 */
async function explorePage(page, route, goal, depth = 0, visited = new Set()) {
  const routeKey = `${route}@d${depth}`;
  if (visited.has(routeKey)) return;
  if (depth > MAX_DEPTH) return;
  visited.add(routeKey);

  const fullUrl = route.startsWith('http') ? route : `${BASE_URL}${route}`;
  const entry = {
    route,
    goal,
    visited: true,
    fullUrl,
    depth,
    actions: [],
    issues: [],
    pageState: { title: '', url: '', status: 'unknown', blank: false },
    startedAt: new Date().toISOString(),
  };

  log.summary.routesVisited++;

  // ---- Navigate ----
  let response;
  try {
    response = await page.goto(fullUrl, { waitUntil: 'networkidle', timeout: 15000 });
    entry.pageState.status = response ? String(response.status()) : 'no-response';
  } catch (e) {
    const errMsg = (e.message || '').substring(0, 200);
    entry.pageState.status = `error: ${(e.message || '').substring(0, 80)}`;

    // Determine if page is totally unreachable (ERR_CONNECTION_REFUSED etc.)
    // vs. partial load where we can still take a screenshot.
    const isConnectionRefused = /connection refused|ECONNREFUSED|ERR_CONNECTION_REFUSED/i.test(errMsg);
    const isInvalidUrl = /Cannot navigate to invalid URL|Protocol error/i.test(errMsg);

    let screenshot = '';
    let evidenceError = '';
    if (isConnectionRefused || isInvalidUrl) {
      // Page never loaded — cannot screenshot, record why
      evidenceError = 'page not loaded, cannot screenshot';
    } else {
      // Try to capture whatever is on screen (may be error page or partial load)
      screenshot = await captureEvidence(page, `navfail_${route.replace(/\//g, '_')}`);
      if (!screenshot) {
        evidenceError = 'screenshot attempt failed';
      }
    }

    entry.issues.push({
      severity: 'P1',
      title: `Navigation failed: ${route}`,
      reason: errMsg || 'Unknown navigation error',
      reproSteps: [`1. goto ${fullUrl}`, `2. Page failed to load within 15s`],
      screenshot,
      trace: '',
      evidenceError,
      consoleErrors: [e.message?.substring(0, 200)],
      networkErrors: [],
    });
    log.summary.issuesFound++;
    log.summary.bySeverity.P1++;
    log.pages.push(entry);
    return;
  }

  await page.waitForTimeout(500);

  // ---- Observe page state ----
  entry.pageState.title = await page.title().catch(() => '');
  entry.pageState.url = page.url();

  const bodyEl = page.locator('body');
  const bodyText = await bodyEl.innerText().catch(() => '');
  if (!bodyText || bodyText.trim().length === 0) {
    entry.pageState.blank = true;
    const blankScreenshot = await captureEvidence(page, `blank_${route.replace(/\//g, '_')}`);
    entry.issues.push({
      severity: 'P1',
      title: `Blank page: ${route}`,
      reason: '#app visible but body has no text content',
      reproSteps: [`1. goto ${fullUrl}`, '2. Wait for networkidle', '3. body.innerText is empty'],
      screenshot: blankScreenshot,
      trace: '',
      evidenceError: blankScreenshot ? '' : 'screenshot attempt failed on blank page',
      consoleErrors: [],
      networkErrors: [],
    });
    log.summary.issuesFound++;
    log.summary.bySeverity.P1++;
    log.pages.push(entry);
    return;
  }

  // ---- Observe: visible elements ----
  const buttons = page.locator('button, [role="button"], .btn, a.button, input[type="submit"]');
  const links = page.locator('a[href]');
  const inputs = page.locator('input:not([type="hidden"]), textarea, select');
  entry.pageState.visibleButtons = await buttons.count().catch(() => 0);
  entry.pageState.visibleLinks = await links.count().catch(() => 0);
  entry.pageState.visibleInputs = await inputs.count().catch(() => 0);

  // ---- Observe: error indicators in DOM ----
  const errorEls = page.locator('.error, .err-msg, [class*="error"], [class*="toast-error"], '
    + '.alert-danger, .notification-error, [role="alert"]');
  const domErrorCount = await errorEls.count().catch(() => 0);
  for (let i = 0; i < Math.min(domErrorCount, 5); i++) {
    const errText = await errorEls.nth(i).innerText().catch(() => '');
    if (errText.trim()) {
      const domErrScreenshot = await captureEvidence(page, `domerror_${route.replace(/\//g, '_')}_${i}`);
      entry.issues.push({
        severity: 'P2',
        title: `DOM error visible: ${route}`,
        reason: errText.substring(0, 200),
        reproSteps: [`1. goto ${fullUrl}`, `2. Observe .error element text`],
        screenshot: domErrScreenshot,
        trace: '',
        evidenceError: domErrScreenshot ? '' : 'screenshot attempt failed',
        consoleErrors: [],
        networkErrors: [],
      });
      log.summary.issuesFound++;
      log.summary.bySeverity.P2++;
    }
  }

  // ---- Interact: click safe buttons ----
  let actCount = 0;
  const btnCount = entry.pageState.visibleButtons || 0;
  for (let i = 0; i < btnCount && actCount < MAX_ACTIONS; i++) {
    const action = { type: 'click', target: '', status: 'skipped', beforeUrl: page.url(), afterUrl: '', evidence: [] };
    log.summary.actionsAttempted++;

    try {
      const btn = buttons.nth(i);
      const visible = await btn.isVisible().catch(() => false);
      if (!visible) { action.status = 'skipped'; entry.actions.push(action); log.summary.actionsSkipped++; continue; }

      const text = (await btn.innerText().catch(() => '')).trim();
      if (!text || !isSafe(text)) { action.status = 'blocked'; action.target = `button:${text || 'unnamed'} (unsafe)`; entry.actions.push(action); log.summary.actionsBlocked++; continue; }

      action.target = `button:${text}`;
      action.beforeUrl = page.url();

      // Element Plus detection: check if button is a dropdown trigger
      const isDropdownTrigger = await btn.evaluate(el =>
        el.closest('.el-dropdown') !== null ||
        el.closest('.el-sub-menu') !== null
      ).catch(() => false);

      if (isDropdownTrigger) {
        // Hover first to trigger Element Plus popups (dropdown/menu)
        await btn.hover({ timeout: 2000 });
        await page.waitForTimeout(500);
      }

      await btn.click({ timeout: 3000 });
      await page.waitForTimeout(400);

      // Check for Element Plus popup/dropdown/menu after click
      const popupVisible = await page.locator(
        '.el-dropdown-menu:visible, .el-popper:visible, .el-select-dropdown:visible, ' +
        '.el-menu--popup:visible, .el-dialog:visible, .el-drawer:visible'
      ).count().catch(() => 0);
      if (popupVisible > 0) {
        action.evidence.push({ type: 'popup', element: 'el-dropdown/menu/dialog', visible: true });
      }

      action.afterUrl = page.url();
      action.status = 'passed';
      log.summary.actionsPassed++;
      actCount++;

      // If route changed, explore the new route
      if (action.afterUrl !== action.beforeUrl) {
        action.evidence.push({ type: 'navigation', from: action.beforeUrl, to: action.afterUrl });
        try {
          const newPath = new URL(action.afterUrl).pathname;
          if (!visited.has(newPath)) {
            await explorePage(page, newPath, `深度探索: ${newPath} (从 '${text}' 点击进入)`, depth + 1, visited);
          }
        } catch (_) {}
        // Navigate back
        await page.goto(fullUrl, { waitUntil: 'networkidle', timeout: 10000 }).catch(() => {});
        await page.waitForTimeout(300);
      }

      // Check for toast/dialog after click
      const toast = page.locator('.toast, .modal, .dialog, [role="dialog"], .notification');
      const toastCount = await toast.count().catch(() => 0);
      if (toastCount > 0) {
        const toastText = await toast.first().innerText().catch(() => '');
        action.evidence.push({ type: 'feedback', element: 'toast/dialog', text: toastText.substring(0, 200) });
      }
    } catch (e) {
      action.status = 'failed';
      action.evidence.push({ type: 'error', message: e.message?.substring(0, 200) });
      log.summary.actionsFailed++;
    }
    entry.actions.push(action);
  }

  // ---- Interact: fill safe inputs ----
  const inputCount = entry.pageState.visibleInputs || 0;
  for (let i = 0; i < inputCount && actCount < MAX_ACTIONS; i++) {
    const action = { type: 'fill', target: '', status: 'skipped', beforeUrl: page.url(), afterUrl: '', evidence: [] };
    log.summary.actionsAttempted++;

    try {
      const inp = inputs.nth(i);
      const visible = await inp.isVisible().catch(() => false);
      if (!visible) { action.status = 'skipped'; entry.actions.push(action); log.summary.actionsSkipped++; continue; }

      const inpType = await inp.getAttribute('type').catch(() => 'text');
      const inpName = await inp.getAttribute('name').catch(() => '');
      const placeholder = await inp.getAttribute('placeholder').catch(() => '');

      if (['password', 'file', 'hidden'].includes(inpType)) { action.status = 'blocked'; action.target = `input[${inpType}]`; entry.actions.push(action); log.summary.actionsBlocked++; continue; }

      const key = (inpName || placeholder || inpType).toLowerCase();
      let value = SAFE_VALUES[key] || 'test_value';
      if (inpType === 'number') value = '10';
      if (inpType === 'email') value = 'test@example.com';

      action.target = `input:${inpName || placeholder || `nth(${i})`}`;

      await inp.fill(String(value), { timeout: 3000 });
      action.status = 'passed';
      log.summary.actionsPassed++;
      actCount++;

      // Check for inline validation after fill
      const validationMsg = page.locator(`[data-error], .field-error, .form-error, .invalid-feedback`);
      const valCount = await validationMsg.count().catch(() => 0);
      if (valCount > 0) {
        const valText = await validationMsg.first().innerText().catch(() => '');
        action.evidence.push({ type: 'validation', text: valText.substring(0, 200) });
      }
    } catch (e) {
      action.status = 'failed';
      action.evidence.push({ type: 'error', message: e.message?.substring(0, 200) });
      log.summary.actionsFailed++;
    }
    entry.actions.push(action);
  }

  // ---- Collect console/network errors ----
  const consoleErrors = [];
  const networkErrors = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text().substring(0, 500));
  });
  page.on('pageerror', (err) => {
    consoleErrors.push(`PAGE_ERROR: ${(err.message || '').substring(0, 500)}`);
  });
  page.on('requestfailed', (req) => {
    networkErrors.push(`REQUEST_FAILED: ${req.method()} ${req.url()} — ${req.failure()?.errorText || 'unknown'}`);
  });
  page.on('response', (resp) => {
    if (resp.status() >= 400) {
      networkErrors.push(`HTTP_${resp.status()}: ${resp.request().method()} ${resp.url()}`);
    }
  });

  // Wait briefly to catch late errors
  await page.waitForTimeout(1000);

  if (consoleErrors.length > 0) {
    const consoleScreenshot = await captureEvidence(page, `console_${route.replace(/\//g, '_')}`);
    entry.issues.push({
      severity: 'P2',
      title: `${consoleErrors.length} console error(s) on ${route}`,
      reason: consoleErrors.slice(0, 3).join(' | '),
      reproSteps: [`1. goto ${fullUrl}`, '2. Check browser console'],
      screenshot: consoleScreenshot,
      trace: '',
      evidenceError: consoleScreenshot ? '' : 'screenshot attempt failed',
      consoleErrors: consoleErrors.slice(0, 10),
      networkErrors: [],
    });
    log.summary.issuesFound++;
    log.summary.bySeverity.P2++;
  }
  if (networkErrors.length > 0) {
    const has5xx = networkErrors.some((e) => /HTTP_5\d\d/.test(e));
    const netScreenshot = await captureEvidence(page, `net_${route.replace(/\//g, '_')}`);
    entry.issues.push({
      severity: has5xx ? 'P1' : 'P2',
      title: `${networkErrors.length} network error(s) on ${route}`,
      reason: networkErrors.slice(0, 3).join(' | '),
      reproSteps: [`1. goto ${fullUrl}`, '2. Open DevTools Network tab'],
      screenshot: netScreenshot,
      trace: '',
      evidenceError: netScreenshot ? '' : 'screenshot attempt failed',
      consoleErrors: [],
      networkErrors: networkErrors.slice(0, 10),
    });
    log.summary.issuesFound++;
    log.summary.bySeverity[has5xx ? 'P1' : 'P2']++;
  }

  // ---- Detect click-with-no-feedback ----
  for (const action of entry.actions) {
    if (action.type === 'click' && action.status === 'passed' && action.afterUrl === action.beforeUrl) {
      const hasFeedback = action.evidence.some((e) =>
        e.type === 'feedback' || e.type === 'navigation' || e.type === 'popup'
      );
      if (!hasFeedback) {
        // Dedup: same target across all pages → only keep 1
        if (!dedupedIssues.has(`nofeedback:${action.target}`)) {
          dedupedIssues.add(`nofeedback:${action.target}`);
          entry.issues.push({
            severity: 'P3',
            title: `Click with no visible feedback: ${action.target}`,
            reason: 'URL unchanged, no toast/dialog/modal appeared',
            reproSteps: [`1. goto ${fullUrl}`, `2. Click ${action.target}`, '3. Observe: no URL change, no toast, no dialog'],
            screenshot: '',
            trace: '',
            consoleErrors: [],
            networkErrors: [],
          });
          log.summary.issuesFound++;
          log.summary.bySeverity.P3++;
        }
        // Only flag first no-feedback per page to avoid noise
        break;
      }
    }
  }

  entry.endedAt = new Date().toISOString();
  log.pages.push(entry);
}

/**
 * Capture screenshot evidence.
 */
async function captureEvidence(page, name) {
  try {
    const dir = 'reports/fittrack/screenshots';
    fs.mkdirSync(dir, { recursive: true });
    const fpath = path.join(dir, `${name}_${Date.now()}.png`);
    await page.screenshot({ path: fpath, fullPage: false });
    return fpath;
  } catch (_) {
    return '';
  }
}

// --- Test Suite ---
test.describe('UI Explorer MVP', () => {
  test('goal-based exploration of configured routes', async ({ page }) => {
    test.setTimeout(300000); // 5 min

    // Setup API mocks so the admin frontend works without a real backend
    await setupApiMocks(page);

    // Inject auth tokens if authMode is 'injected' or 'mock'
    // Must happen before any page.goto so the Vue app reads the injected tokens
    await setupAuth(page, authMode);
    const authInfo = getAuthInfo(authMode);
    log.authMode = authInfo.mode;
    log.authInjected = authInfo.injected;
    if (authInfo.warning) {
      log.authWarning = authInfo.warning;
    }

    // Setup quality monitor
    const monitorErrors = [];
    page.on('console', (msg) => { if (msg.type() === 'error') monitorErrors.push(msg.text()); });
    page.on('pageerror', (err) => monitorErrors.push(err.message));

    const visited = new Set();

    for (const { path: route, goal } of routes) {
      if (!route) continue;
      console.log(`\n[EXPLORER] Visiting: ${route} — ${goal}`);
      await explorePage(page, route.trim(), goal, 0, visited);
    }

    // Capture mock stats
    const mockStats = getMockStats();
    log.apiMock = {
      enabled: mockStats.enabled,
      matched: mockStats.matched,
      unmatched: mockStats.unmatched,
      unmatchedUrls: mockStats.unmatchedUrls.slice(0, 30),
    };
    if (mockStats.unmatchedWhitelistReason) {
      log.apiMock.unmatchedWhitelistReason = mockStats.unmatchedWhitelistReason;
    }
    console.log(`[EXPLORER] apiMock: matched=${mockStats.matched} unmatched=${mockStats.unmatched}`
      + (mockStats.unmatchedWhitelistReason ? ` (whitelisted: ${mockStats.unmatchedWhitelistReason})` : ''));
    if (mockStats.unmatched > 0) {
      for (const u of mockStats.unmatchedUrls.slice(0, 5)) {
        console.log(`[EXPLORER]   unmatched: ${u.method} ${(u.url || '').substring(0, 100)} — ${u.reason || '?'}`);
      }
    }

    // Finalize
    log.endTime = new Date().toISOString();
    log.monitorErrors = monitorErrors.slice(0, 50);
    log.forbiddenActionsSource = forbiddenActionsSource;
    if (configWarnings.length > 0) {
      log.configWarnings = configWarnings;
    }

    fs.mkdirSync(REPORT_DIR, { recursive: true });
    fs.writeFileSync(REPORT_FILE, JSON.stringify(log, null, 2));

    console.log(`\n[EXPLORER] Report: ${REPORT_FILE}`);
    const s = log.summary;
    console.log(`[EXPLORER] Routes: ${s.routesVisited} | Actions: ${s.actionsAttempted} `
      + `(P:${s.actionsPassed} F:${s.actionsFailed} S:${s.actionsSkipped} B:${s.actionsBlocked}) `
      + `| Issues: ${s.issuesFound} (P0:${s.bySeverity.P0} P1:${s.bySeverity.P1} P2:${s.bySeverity.P2} P3:${s.bySeverity.P3})`);

    await test.info().attach('explorer-results', {
      body: JSON.stringify(log, null, 2),
      contentType: 'application/json',
    });

    // Teardown API mocks
    await teardownApiMocks(page);

    if (log.summary.routesVisited === 0) {
      throw new Error('No pages visited — check BASE_URL and routes configuration');
    }
  });
});
