/**
 * Auth injection helper for E2E tests.
 *
 * When no real backend is available, the explorer can inject auth tokens
 * directly into localStorage so the Vue auth guard allows access to
 * protected routes (instead of redirecting everything to /login).
 *
 * Usage:
 *   const { setupAuth, getAuthInfo } = require('./support/auth');
 *   await setupAuth(page, 'injected');
 *   const info = getAuthInfo('injected');
 */

// --- localStorage keys (must match auth store) ---
const TOKEN_KEY = 'admin_token';
const INFO_KEY = 'admin_info';

// --- Mock JWT (never expires: exp far in the future) ---
const MOCK_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  'eyJpZCI6MSwibmFtZSI6IkUyRV9UZXN0QWRtaW4iLCJlbWFpbCI6ImUyZUBmaXR0cmFjay50ZXN0Iiwicm9sZSI6ImFkbWluIiwiZXhwIjo5OTk5OTk5OTk5fQ.' +
  'mock_signature_e2e_test_only';

// --- Default injected admin info ---
const DEFAULT_ADMIN_INFO = {
  id: 1,
  name: 'E2E_TestAdmin',
  email: 'e2e@fittrack.test',
  role: 'admin',
};

/**
 * Inject or skip authentication based on authMode.
 *
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {'real'|'injected'|'mock'} authMode - auth strategy
 * @param {object} [options] - optional overrides
 * @param {string} [options.token] - custom token (defaults to MOCK_TOKEN)
 * @param {object} [options.adminInfo] - custom admin info (defaults to DEFAULT_ADMIN_INFO)
 */
async function setupAuth(page, authMode, options = {}) {
  if (authMode === 'real') {
    // Real mode: do nothing, let the frontend handle auth normally
    return;
  }

  // injected and mock behave identically:
  // write token + admin_info to localStorage before the frontend loads.
  // Use addInitScript so the injection runs before Vue/JS boot, avoiding
  // the "Access is denied for this document" error from page.evaluate on a blank page.
  const token = options.token || MOCK_TOKEN;
  const adminInfo = options.adminInfo || DEFAULT_ADMIN_INFO;
  const tokenKey = TOKEN_KEY;
  const infoKey = INFO_KEY;

  await page.addInitScript(
    ({ tokenKey_, tokenVal_, infoKey_, infoVal_ }) => {
      try {
        localStorage.setItem(tokenKey_, tokenVal_);
        localStorage.setItem(infoKey_, JSON.stringify(infoVal_));
      } catch (_) {
        // Silently ignore if localStorage is unavailable (e.g., about:blank)
      }
    },
    { tokenKey_: tokenKey, tokenVal_: token, infoKey_: infoKey, infoVal_: adminInfo }
  );
}

/**
 * Return structured metadata about the current auth mode.
 *
 * @param {'real'|'injected'|'mock'} authMode
 * @returns {{ mode: string, injected: boolean, warning: string|null }}
 */
function getAuthInfo(authMode) {
  if (authMode === 'real') {
    return { mode: 'real', injected: false, warning: null };
  }
  return {
    mode: authMode,
    injected: true,
    warning: 'Injected auth used; backend auth not verified',
  };
}

module.exports = { setupAuth, getAuthInfo };
