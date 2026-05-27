/**
 * UI Oracles — Testable, explainable rules for automated quality judgment.
 *
 * Each oracle is a pure function: (evidence) → { severity, title, reason, reproSteps }
 * Designed to be called from explorer or any Playwright test.
 *
 * Severity levels:
 *   P0 — Crash / data loss / security breach (auto-fail CI)
 *   P1 — Core feature broken / 5xx / 401 on critical API
 *   P2 — Non-critical error / console error / 404
 *   P3 — Cosmetic / no feedback / minor UX issue
 */

/**
 * Check if a page is blank (has #app but no meaningful content).
 * @param {object} pageState — { title, url, blank, bodyText, hasApp }
 * @returns {object|null} issue or null
 */
function oraclePageBlank(pageState) {
  if (pageState.blank || (pageState.hasApp && (!pageState.bodyText || pageState.bodyText.trim().length === 0))) {
    return {
      severity: 'P1',
      title: `Blank page detected: ${pageState.url || 'unknown'}`,
      reason: 'Page has #app container but no visible text content.',
      reproSteps: [
        `1. Navigate to ${pageState.url}`,
        '2. Wait for networkidle',
        '3. Verify body has no text content',
      ],
    };
  }
  return null;
}

/**
 * Classify console errors by severity.
 * @param {Array} consoleErrors — [{type: 'console_error'|'page_error', text, ...}]
 * @returns {Array} issues
 */
function oracleConsoleErrors(consoleErrors, whitelist = []) {
  const issues = [];
  const defaultWhitelist = [/favicon/i, /ResizeObserver/i, /Third-party cookie/i, /crbug/i];
  const allWhitelist = [...defaultWhitelist, ...whitelist];

  for (const err of consoleErrors) {
    const text = err.text || err.message || '';
    if (allWhitelist.some((p) => p.test(text))) continue;

    if (err.type === 'page_error') {
      issues.push({
        severity: 'P1',
        title: `Uncaught page error: ${text.substring(0, 120)}`,
        reason: text.substring(0, 300),
        reproSteps: ['1. Load page', '2. Check browser console for uncaught errors'],
      });
    } else {
      issues.push({
        severity: 'P2',
        title: `Console error: ${text.substring(0, 120)}`,
        reason: text.substring(0, 300),
        reproSteps: ['1. Load page', '2. Open DevTools Console'],
      });
    }
  }
  return issues;
}

/**
 * Classify network errors by HTTP status and endpoint criticality.
 * @param {Array} networkErrors — [{type, url, status, method}]
 * @returns {Array} issues
 */
function oracleNetworkErrors(networkErrors, criticalPaths = []) {
  const issues = [];

  for (const err of networkErrors) {
    const status = err.status || 0;
    const url = err.url || '';

    // 5xx → P1 (server error)
    if (status >= 500) {
      issues.push({
        severity: 'P1',
        title: `Server error ${status} on ${err.method || 'GET'} ${url.substring(0, 100)}`,
        reason: `HTTP ${status} indicates server-side failure.`,
        reproSteps: [`1. Navigate to page`, `2. Open DevTools Network tab`, `3. Observe ${status} on ${url}`],
      });
      continue;
    }

    // 401/403 on critical paths → P1
    if ((status === 401 || status === 403) && criticalPaths.some((p) => url.includes(p))) {
      issues.push({
        severity: 'P1',
        title: `Auth error ${status} on critical endpoint: ${url.substring(0, 100)}`,
        reason: `HTTP ${status} on critical path — authentication/authorization failure.`,
        reproSteps: [`1. Ensure authenticated session`, `2. Navigate to page`, `3. Check ${url} response`],
      });
      continue;
    }

    // 404 → P2
    if (status === 404) {
      issues.push({
        severity: 'P2',
        title: `Resource not found (404): ${url.substring(0, 100)}`,
        reason: 'Resource returned 404 — may be missing or misconfigured.',
        reproSteps: [`1. Navigate to page`, `2. Check Network tab for 404 on ${url}`],
      });
      continue;
    }

    // Other 4xx → P2
    if (status >= 400) {
      issues.push({
        severity: 'P2',
        title: `HTTP ${status} on ${url.substring(0, 100)}`,
        reason: `Client error ${status} — request may be malformed or unauthorized.`,
        reproSteps: [`1. Navigate to page`, `2. Check Network tab for ${status} on ${url}`],
      });
      continue;
    }

    // Connection failure → P1
    if (err.type === 'request_failed' && !status) {
      issues.push({
        severity: 'P1',
        title: `Request failed: ${url.substring(0, 100)}`,
        reason: err.failure || 'Network request did not complete — connection refused or timeout.',
        reproSteps: [`1. Navigate to page`, `2. Check Network tab for failed request to ${url}`],
      });
    }
  }
  return issues;
}

/**
 * Detect clicks that produced no visible feedback.
 * @param {object} action — { type, target, status, beforeUrl, afterUrl, evidence }
 * @returns {object|null} issue or null
 */
function oracleClickNoFeedback(action) {
  if (action.type !== 'click' || action.status !== 'passed') return null;
  if (action.afterUrl && action.afterUrl !== action.beforeUrl) return null; // navigation IS feedback

  const hasFeedback = (action.evidence || []).some(
    (e) => e.type === 'feedback' || e.type === 'navigation' || e.type === 'toast' || e.type === 'dialog' || e.type === 'popup'
  );
  if (!hasFeedback) {
    return {
      severity: 'P3',
      title: `Click with no visible feedback: ${action.target}`,
      reason: 'After clicking, URL unchanged, no toast/dialog/modal appeared, no DOM change detected.',
      reproSteps: [
        `1. Navigate to ${action.beforeUrl}`,
        `2. Click "${action.target}"`,
        '3. Observe: no URL change, no toast, no dialog, no visible state change',
      ],
    };
  }
  return null;
}

/**
 * Check if a form fill+submit produced no validation or feedback.
 * @param {Array} actions — all actions on a page
 * @returns {Array} issues
 */
function oracleFormNoFeedback(actions) {
  const issues = [];
  const fillActions = (actions || []).filter((a) => a.type === 'fill' && a.status === 'passed');
  const hasSubmit = (actions || []).some((a) => a.type === 'click' && /submit|提交|保存|save/.test(a.target || ''));

  if (fillActions.length > 0 && !hasSubmit) {
    // User filled fields but there's no submit button clicked → check if there IS a submit visible
    // This is informational, not necessarily an error
  }

  if (fillActions.length > 0 && hasSubmit) {
    const hasValidation = (actions || []).some((a) =>
      (a.evidence || []).some((e) => e.type === 'validation' || e.type === 'feedback' || e.type === 'error')
    );
    if (!hasValidation) {
      issues.push({
        severity: 'P2',
        title: 'Form filled and submitted but no validation or feedback observed',
        reason: 'Form inputs were filled but after interaction, no validation messages, toast, or error feedback appeared.',
        reproSteps: [
          '1. Fill all form fields with test values',
          '2. Click submit/save',
          '3. Observe: no success message, no error message, no redirect',
        ],
      });
    }
  }
  return issues;
}

/**
 * Validate that failed issues have sufficient evidence.
 * @param {Array} issues
 * @returns {Array} evidence gaps
 */
function oracleEvidenceGaps(issues) {
  const gaps = [];
  for (const issue of issues) {
    if (issue.severity === 'P0' || issue.severity === 'P1') {
      const hasScreenshot = issue.screenshot && issue.screenshot.length > 0;
      const hasTrace = issue.trace && issue.trace.length > 0;
      if (!hasScreenshot && !hasTrace) {
        gaps.push({
          severity: 'P2',
          title: `Evidence gap: ${issue.severity} issue has no screenshot or trace`,
          reason: `Issue "${issue.title}" is ${issue.severity} but lacks screenshot and trace evidence.`,
          reproSteps: ['1. Re-run test with screenshot:on and trace:on-first-retry'],
        });
      }
    }
  }
  return gaps;
}

/**
 * Run all oracles against collected page data.
 * Returns array of all issues found.
 *
 * @param {object} pageData — { pageState, consoleErrors, networkErrors, actions }
 * @param {object} options — { whitelist, criticalPaths }
 * @returns {Array} issues
 */
function runAllOracles(pageData, options = {}) {
  const issues = [];
  const ps = pageData.pageState || {};

  // 1. Blank page
  const blank = oraclePageBlank(ps);
  if (blank) issues.push(blank);

  // 2. Console errors
  issues.push(...oracleConsoleErrors(pageData.consoleErrors || [], options.whitelist || []));

  // 3. Network errors (generic)
  issues.push(...oracleNetworkErrors(pageData.networkErrors || [], options.criticalPaths || []));

  // 3b. API HTTP error classification (FitTrack-specific)
  issues.push(...oracleApiHttpError(pageData.networkErrors || []));

  // 4. Click no feedback
  for (const action of pageData.actions || []) {
    const noFeedback = oracleClickNoFeedback(action);
    if (noFeedback) {
      issues.push(noFeedback);
      break; // Only first per page to avoid noise
    }
  }

  // 5. Form no feedback
  issues.push(...oracleFormNoFeedback(pageData.actions || []));

  // 6. Evidence gaps (run after collecting all issues)
  issues.push(...oracleEvidenceGaps(issues));

  // --- FitTrack business oracles ---
  const actions = pageData.actions || [];

  // 7. Login failure detection
  const loginIssue = oracleLoginFailure(ps, actions);
  if (loginIssue) issues.push(loginIssue);

  // 8. Empty list without empty-state
  const emptyListIssue = oracleEmptyList(ps, options.tableSelector || '');
  if (emptyListIssue) issues.push(emptyListIssue);

  // 9. Search no-result without feedback
  const searchIssue = oracleSearchNoResult(ps, options.searchTerm || '');
  if (searchIssue) issues.push(searchIssue);

  // 10. Form required validation
  const formValIssue = oracleFormRequiredValidation(ps, actions);
  if (formValIssue) issues.push(formValIssue);

  // 11. Save operation feedback
  const saveFeedbackIssue = oracleSaveFeedback(ps, actions);
  if (saveFeedbackIssue) issues.push(saveFeedbackIssue);

  // 12. Pagination check
  const paginationIssue = oraclePaginationVisible(ps);
  if (paginationIssue) issues.push(paginationIssue);

  // 13. Auth gated route
  const authGateIssue = oracleAuthGatedRoute(ps);
  if (authGateIssue) issues.push(authGateIssue);

  return issues;
}

/**
 * Detect login page error — check for visible error message or unredirected page state.
 * @param {object} pageState — { url, bodyText, hasLoginForm }
 * @param {object} actions — optional actions array to inspect for failed-login evidence
 * @returns {object|null} issue or null
 */
function oracleLoginFailure(pageState, actions = []) {
  const url = pageState.url || '';

  // If still on /login after attempted submit, check for error indicators
  if (url.includes('/login') && pageState.bodyText) {
    const hasErrorIndicator =
      pageState.bodyText.includes('错误') ||
      pageState.bodyText.includes('失败') ||
      pageState.bodyText.includes('不存在') ||
      pageState.bodyText.includes('密码错误') ||
      pageState.bodyText.includes('账号') ||
      pageState.hasErrorMsg === true;
    if (hasErrorIndicator) {
      return {
        severity: 'P2',
        title: 'Login page shows error message',
        reason: 'Login form submitted but error text is visible — credentials may be invalid or server unreachable.',
        reproSteps: [
          '1. Navigate to /login',
          '2. Fill credentials and click login',
          '3. Observe: error message visible, still on /login',
        ],
      };
    }
  }
  return null;
}

/**
 * Check if an empty list shows an empty-state indicator.
 * @param {object} pageState — { url, bodyText, hasTable, tableRowCount, emptyStateVisible }
 * @param {string} tableSelector — CSS selector for the table container (e.g. '.el-table')
 * @returns {object|null} issue or null
 */
function oracleEmptyList(pageState, tableSelector = '') {
  // Only inspect pages that contain a table container
  if (!pageState.hasTable) return null;

  const isEmpty = pageState.tableRowCount === 0 || pageState.bodyText === '';
  if (!isEmpty) return null;

  const hasEmptyHint =
    (pageState.bodyText && (
      pageState.bodyText.includes('暂无数据') ||
      pageState.bodyText.includes('暂无记录') ||
      pageState.bodyText.includes('没有数据') ||
      pageState.bodyText.includes('无数据') ||
      pageState.bodyText.includes('no data')
    )) ||
    pageState.emptyStateVisible === true;

  if (!hasEmptyHint) {
    return {
      severity: 'P2',
      title: `Empty list with no empty-state hint${tableSelector ? ' (' + tableSelector + ')' : ''}`,
      reason: 'Table has no rows and the page shows no "暂无数据" or .empty-state element — user may think the page is broken.',
      reproSteps: [
        `1. Navigate to ${pageState.url || 'the page'}`,
        '2. Observe: table is empty but no empty-state message appears',
      ],
    };
  }
  return null;
}

/**
 * Check if a search returning no results shows feedback.
 * @param {object} pageState — { url, bodyText, hasTable, tableRowCount }
 * @param {string} searchTerm — the keyword that was searched
 * @returns {object|null} issue or null
 */
function oracleSearchNoResult(pageState, searchTerm) {
  if (!pageState.hasTable) return null;
  if (pageState.tableRowCount !== 0) return null; // has results, ok

  const bodyText = pageState.bodyText || '';
  const hasNoResultHint =
    bodyText.includes('未找到') ||
    bodyText.includes('无匹配') ||
    bodyText.includes('没有找到') ||
    bodyText.includes('暂无') ||
    bodyText.includes('0条') ||
    bodyText.includes('no result');

  if (!hasNoResultHint) {
    return {
      severity: 'P2',
      title: `Search "${searchTerm || '(unknown)'}" returned no results without feedback`,
      reason: 'Search produced an empty result set but no "未找到"/"无匹配结果" message is visible.',
      reproSteps: [
        `1. Navigate to ${pageState.url || 'the page'}`,
        `2. Enter "${searchTerm || 'a search term'}" in the search box and submit`,
        '3. Observe: empty list but no "no results" message',
      ],
    };
  }
  return null;
}

/**
 * Check if a form enforces required-field validation on empty submit.
 * @param {object} pageState — { url, bodyText }
 * @param {object} actions — submitted actions array
 * @returns {object|null} issue or null
 */
function oracleFormRequiredValidation(pageState, actions = []) {
  const hasSubmitAction = (actions || []).some(
    (a) => a.type === 'click' && /submit|提交|保存|save|登录|login|创建|确认/.test(a.target || '')
  );
  if (!hasSubmitAction) return null;

  const bodyText = pageState.bodyText || '';
  const hasValidation =
    pageState.hasFormError === true ||
    bodyText.includes('不能为空') ||
    bodyText.includes('请输入') ||
    bodyText.includes('必填') ||
    bodyText.includes('required') ||
    bodyText.includes('格式不正确');

  if (!hasValidation) {
    return {
      severity: 'P2',
      title: 'Form submitted with empty required fields but no validation feedback',
      reason: 'After submit click, no validation error text (e.g. "不能为空" / "请输入") and no .el-form-item__error visible.',
      reproSteps: [
        `1. Navigate to ${pageState.url || 'the page'}`,
        '2. Leave required fields empty and click submit',
        '3. Observe: no validation message appears',
      ],
    };
  }
  return null;
}

/**
 * Check if a save/update operation produced feedback (toast/message).
 * @param {object} pageState — { url, bodyText }
 * @param {object} actions — submitted actions array
 * @returns {object|null} issue or null
 */
function oracleSaveFeedback(pageState, actions = []) {
  const hasSaveAction = (actions || []).some(
    (a) => a.type === 'click' && /submit|提交|保存|save|更新|update|创建|create/.test(a.target || '')
  );
  if (!hasSaveAction) return null;

  const bodyText = pageState.bodyText || '';
  const hasFeedback =
    pageState.hasToast === true ||
    bodyText.includes('成功') ||
    bodyText.includes('失败') ||
    bodyText.includes('保存') ||
    bodyText.includes('已') ||
    bodyText.includes('操作') ||
    bodyText.includes('创建');

  if (!hasFeedback) {
    return {
      severity: 'P2',
      title: 'Save operation completed but no feedback (toast/message) detected',
      reason: 'After clicking save/submit, no success/failure toast or message appeared.',
      reproSteps: [
        `1. Navigate to ${pageState.url || 'the page'}`,
        '2. Fill form fields and click submit/save',
        '3. Observe: no .el-message, .toast, or notification visible',
      ],
    };
  }
  return null;
}

/**
 * Check if a data list page has pagination controls.
 * @param {object} pageState — { url, bodyText, hasTable, tableRowCount, hasPagination, totalRows }
 * @returns {object|null} issue or null
 */
function oraclePaginationVisible(pageState) {
  // Only relevant for list pages that have a table with data
  if (!pageState.hasTable) return null;
  if (!pageState.tableRowCount || pageState.tableRowCount === 0) return null;

  if (!pageState.hasPagination) {
    return {
      severity: 'P3',
      title: `List page with data but no pagination visible: ${pageState.url || 'unknown'}`,
      reason: 'Table has rows but .el-pagination / .pager is missing — all data shown on one page, which may be a UX issue.',
      reproSteps: [
        `1. Navigate to ${pageState.url || 'the page'}`,
        '2. Observe: table has rows but no pagination at bottom',
      ],
    };
  }
  return null;
}

/**
 * Classify HTTP network errors with FitTrack-specific severity.
 * Complements (not replaces) oracleNetworkErrors — this can also be called standalone.
 * @param {Array} networkErrors — [{type, url, status, method}] or plain strings
 * @returns {Array} issues
 */
function oracleApiHttpError(networkErrors = []) {
  const issues = [];

  for (const err of networkErrors) {
    // Support both structured objects and plain string format
    const status = err.status || 0;
    const url = err.url || '';
    let statusFromStr = 0;
    let urlFromStr = '';

    if (!status && typeof err === 'string') {
      const m = err.match(/HTTP_(\d{3})/);
      if (m) statusFromStr = parseInt(m[1], 10);
      const u = err.match(/:\s+(\S+)/);
      if (u) urlFromStr = u[1];
    }

    const effectiveStatus = status || statusFromStr;
    const effectiveUrl = url || urlFromStr || (typeof err === 'string' ? err : '');

    // 401/403 → P1 authentication failure
    if (effectiveStatus === 401 || effectiveStatus === 403) {
      issues.push({
        severity: 'P1',
        title: `Auth error ${effectiveStatus}: ${effectiveUrl.substring(0, 100)}`,
        reason: `HTTP ${effectiveStatus} — authentication or authorization failure. Token may be expired or missing.`,
        reproSteps: [
          '1. Check localStorage for admin_token',
          '2. Verify JWT is not expired',
          `3. Retry request to ${effectiveUrl}`,
        ],
      });
      continue;
    }

    // 5xx → P1 server error
    if (effectiveStatus >= 500) {
      issues.push({
        severity: 'P1',
        title: `Server error ${effectiveStatus}: ${effectiveUrl.substring(0, 100)}`,
        reason: `HTTP ${effectiveStatus} — server-side failure. Cloud function or backend may be down.`,
        reproSteps: [
          '1. Check cloud function logs',
          `2. Verify ${effectiveUrl} endpoint is healthy`,
          '3. Check backend service status',
        ],
      });
      continue;
    }

    // Other 4xx → P2
    if (effectiveStatus >= 400) {
      issues.push({
        severity: 'P2',
        title: `Client error ${effectiveStatus}: ${effectiveUrl.substring(0, 100)}`,
        reason: `HTTP ${effectiveStatus} — request may be malformed or resource not found.`,
        reproSteps: [
          `1. Check request payload for ${effectiveUrl}`,
          '2. Open DevTools Network tab to inspect response body',
        ],
      });
      continue;
    }

    // Connection failure → P1
    if (typeof err === 'string' && err.includes('REQUEST_FAILED')) {
      issues.push({
        severity: 'P1',
        title: `Request failed: ${effectiveUrl.substring(0, 100)}`,
        reason: err.substring(0, 300),
        reproSteps: ['1. Check network connectivity', '2. Verify backend server is running'],
      });
    }
  }
  return issues;
}

/**
 * Check whether an unauthenticated user is properly gated from protected routes.
 * @param {object} pageState — { url, bodyText, redirected, hasAuthToken }
 * @returns {object|null} issue or null
 */
function oracleAuthGatedRoute(pageState) {
  // If the user has a token or we don't know, skip
  if (pageState.hasAuthToken !== false) return null;

  const url = pageState.url || '';
  const isProtectedRoute =
    url.includes('/exercises') ||
    url.includes('/plans') ||
    url.includes('/templates') ||
    url.includes('/users') ||
    url.includes('/stats') ||
    url.includes('/settings') ||
    url === '/' ||
    url.endsWith('/');

  const isLoginPage = url.includes('/login');

  // If on a protected route without auth token
  if (isProtectedRoute && !isLoginPage) {
    const redirectedToLogin = pageState.redirected === true || url.includes('/login');
    const showsLoginPrompt =
      (pageState.bodyText || '').includes('请先登录') ||
      (pageState.bodyText || '').includes('请登录') ||
      (pageState.bodyText || '').includes('未登录');

    if (!redirectedToLogin && !showsLoginPrompt) {
      return {
        severity: 'P2',
        title: `Protected route accessible without auth: ${url}`,
        reason: 'No admin_token in localStorage, but page did not redirect to /login and shows no login prompt — route guard may be broken.',
        reproSteps: [
          '1. Clear localStorage (admin_token, admin_info)',
          `2. Navigate to ${url}`,
          '3. Observe: should redirect to /login or show "请先登录"',
        ],
      };
    }
  }
  return null;
}

module.exports = {
  oraclePageBlank,
  oracleConsoleErrors,
  oracleNetworkErrors,
  oracleClickNoFeedback,
  oracleFormNoFeedback,
  oracleEvidenceGaps,
  oracleLoginFailure,
  oracleEmptyList,
  oracleSearchNoResult,
  oracleFormRequiredValidation,
  oracleSaveFeedback,
  oraclePaginationVisible,
  oracleApiHttpError,
  oracleAuthGatedRoute,
  runAllOracles,
};
