/**
 * Exercise Smoke Test (Task B1)
 *
 * 6 business flows for FitTrack admin /exercises module:
 *   list, search, create, edit, validation, apiFailure
 *
 * Uses injected auth (no real backend) + API mocks.
 * Output: reports/business-smoke/exercise-results.json
 */

const { test } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { setupApiMocks, teardownApiMocks, exerciseStore } = require('./support/api-mocks');
const { setupAuth, getAuthInfo } = require('./support/auth');
const { runAllExerciseFlows } = require('./support/exercise-flows');

// --- Configuration ---
const BASE_URL = process.env.EXPLORER_BASE_URL || 'http://localhost:5190';
const AUTH_MODE = process.env.EXPLORER_AUTH_MODE || 'injected';
const REPORT_DIR = 'reports/business-smoke';
const REPORT_FILE = path.join(REPORT_DIR, 'exercise-results.json');

test.describe('Exercise Smoke (B1)', () => {
  let results;

  test('exercise 6-flow business smoke', async ({ page }) => {
    test.setTimeout(120000); // 2 minutes for all 6 flows

    // Ensure report directory exists
    fs.mkdirSync(REPORT_DIR, { recursive: true });

    // Setup API mocks (intercepts /admin/* calls)
    await setupApiMocks(page);

    // Setup injected auth (writes admin_token to localStorage before page load)
    await setupAuth(page, AUTH_MODE);
    const authInfo = getAuthInfo(AUTH_MODE);

    // Collect console errors for diagnostics
    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 300));
    });

    // Run all 6 flows
    results = await runAllExerciseFlows(page, {
      exerciseStore,
      baseUrl: BASE_URL,
      authMode: AUTH_MODE,
    });

    results.consoleErrors = consoleErrors.slice(0, 50);

    // Write results to JSON
    fs.writeFileSync(REPORT_FILE, JSON.stringify(results, null, 2));
    console.log(`[B1] Results written to ${REPORT_FILE}`);

    // Log summary
    const s = results.summary;
    console.log(`[B1] Summary: ${s.total} flows — ${s.passed}P ${s.failed}F ${s.blocked}B (status: ${results.status})`);
    for (const flow of results.flows) {
      console.log(`[B1]   ${flow.flow}: ${flow.status} (${flow.steps.length} steps, ${flow.assertions.length} assertions, ${flow.durationMs}ms)${flow.error ? ' ERR: ' + flow.error.slice(0, 80) : ''}`);
    }

    // Attach results to test info (appears in Playwright report)
    await test.info().attach('exercise-results', {
      body: JSON.stringify(results, null, 2),
      contentType: 'application/json',
    });

    // Teardown API mocks
    await teardownApiMocks(page);

    // Fail test only if ALL flows are BLOCKED
    if (results.summary.blocked === results.summary.total) {
      throw new Error('All 6 flows BLOCKED — admin frontend may not be running');
    }
    // Individual flow failures are recorded in results, not thrown.
  });
});
