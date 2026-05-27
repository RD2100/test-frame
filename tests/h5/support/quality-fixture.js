/**
 * H5 Quality Observation Fixture
 *
 * Unified monitoring for console errors, page crashes, failed network requests,
 * and HTTP error responses. Use as a Playwright fixture to auto-collect quality
 * signals on every page without repeating boilerplate.
 *
 * Usage in spec files:
 *   const { test, expect } = require('@playwright/test');
 *   const { qualityFixture } = require('./support/quality-fixture');
 *
 *   test.describe('My Suite', () => {
 *     qualityFixture(test);  // one-liner activation
 *     // ... your tests ...
 *   });
 *
 * Or import for direct use:
 *   const { createQualityCollector } = require('./support/quality-fixture');
 *   const qc = createQualityCollector(page);
 *   // ... navigate, interact ...
 *   const findings = await qc.report();
 */

// Whitelist patterns — these errors are expected and ignored
const DEFAULT_IGNORE_PATTERNS = [
  /favicon\.ico/i,
  /Failed to load resource: the server responded with a status of 404.*favicon/i,
  /net::ERR_FAILED.*favicon/i,
  /ResizeObserver loop/i,               // harmless observer warning
  /Third-party cookie/i,                // Chrome cookie warning
  /crbug/i,                             // Chromium internals
];

/**
 * Create a quality collector attached to a Playwright page.
 * Call before navigating to capture all events from page load onward.
 */
function createQualityCollector(page, options = {}) {
  const ignorePatterns = options.ignorePatterns || DEFAULT_IGNORE_PATTERNS;

  const collector = {
    consoleErrors: [],
    pageErrors: [],
    failedRequests: [],
    httpErrors: [],       // 4xx/5xx responses
    screenshots: [],
    startUrl: '',
    startTitle: '',

    _shouldIgnore(message) {
      return ignorePatterns.some((p) => p.test(message));
    },
  };

  // Console errors (console.error calls in JS)
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (!collector._shouldIgnore(text)) {
        collector.consoleErrors.push({
          type: 'console_error',
          text,
          location: msg.location(),
          timestamp: Date.now(),
        });
      }
    }
  });

  // Uncaught page errors (throws, unhandled rejections)
  page.on('pageerror', (err) => {
    const msg = err.message || String(err);
    if (!collector._shouldIgnore(msg)) {
      collector.pageErrors.push({
        type: 'page_error',
        message: msg,
        stack: err.stack || '',
        timestamp: Date.now(),
      });
    }
  });

  // Failed network requests (connection refused, timeout, DNS, etc.)
  page.on('requestfailed', (request) => {
    const url = request.url();
    if (!collector._shouldIgnore(url)) {
      collector.failedRequests.push({
        type: 'request_failed',
        url,
        method: request.method(),
        failure: request.failure()?.errorText || 'unknown',
        timestamp: Date.now(),
      });
    }
  });

  // HTTP error responses (4xx, 5xx even if request didn't "fail")
  page.on('response', (response) => {
    const status = response.status();
    if (status >= 400) {
      const url = response.url();
      if (!collector._shouldIgnore(url)) {
        collector.httpErrors.push({
          type: 'http_error',
          url,
          status,
          method: response.request().method(),
          timestamp: Date.now(),
        });
      }
    }
  });

  /**
   * Capture snapshot: title, URL, and optionally a screenshot.
   */
  collector.snapshot = async function (label = '') {
    const info = {
      label,
      url: page.url(),
      title: await page.title().catch(() => ''),
      timestamp: Date.now(),
    };
    collector.screenshots.push(info);
    return info;
  };

  /**
   * Record initial page state. Call after first page.goto().
   */
  collector.recordStart = async function () {
    collector.startUrl = page.url();
    collector.startTitle = await page.title().catch(() => '');
  };

  /**
   * Take a screenshot and store its path.
   */
  collector.captureScreenshot = async function (name) {
    const path = `reports/fittrack/screenshots/${name}_${Date.now()}.png`;
    try {
      await page.screenshot({ path, fullPage: false });
      collector.screenshots.push({ type: 'screenshot', path, name });
    } catch (e) {
      // screenshot can fail if page is closed
    }
  };

  /**
   * Generate a quality report with all collected issues.
   */
  collector.report = function () {
    const issues = [
      ...collector.consoleErrors,
      ...collector.pageErrors,
      ...collector.failedRequests,
      ...collector.httpErrors,
    ];

    return {
      startUrl: collector.startUrl,
      startTitle: collector.startTitle,
      issueCount: issues.length,
      issues,
      summary: {
        consoleErrors: collector.consoleErrors.length,
        pageErrors: collector.pageErrors.length,
        failedRequests: collector.failedRequests.length,
        httpErrors: collector.httpErrors.length,
      },
      screenshots: collector.screenshots.filter((s) => s.path),
    };
  };

  return collector;
}

/**
 * Playwright fixture: activates quality monitoring for every test in a describe block.
 * Adds a beforeEach that creates a collector on the page, and an afterEach that
 * dumps findings if the test failed or issues were found.
 *
 * @param {object} test - Playwright test object
 * @param {object} options
 * @param {boolean} options.reportAlways - If true, report even when test passes (default: false)
 */
function qualityFixture(test, options = {}) {
  const reportAlways = options.reportAlways || false;

  test.beforeEach(async ({ page }, testInfo) => {
    const qc = createQualityCollector(page, options);
    page._qualityCollector = qc;
    testInfo._collector = qc;
  });

  test.afterEach(async ({ page }, testInfo) => {
    const qc = page._qualityCollector || testInfo._collector;
    if (!qc) return;

    const report = qc.report();
    const hasIssues = report.issueCount > 0;

    // Attach report as test annotation
    testInfo.annotations.push({
      type: 'quality',
      description: JSON.stringify(report.summary),
    });

    if (hasIssues) {
      // Print issues to console for CI visibility
      console.log(`\n  [QUALITY] ${testInfo.title}: ${report.issueCount} issue(s)`);
      for (const issue of report.issues.slice(0, 5)) {
        console.log(`    - [${issue.type}] ${(issue.text || issue.message || issue.url || '').substring(0, 120)}`);
      }
      if (report.issueCount > 5) {
        console.log(`    ... and ${report.issueCount - 5} more`);
      }
      // Attach full report for failed tests
      if (testInfo.status !== 'passed' || reportAlways) {
        await testInfo.attach('quality-report', {
          body: JSON.stringify(report, null, 2),
          contentType: 'application/json',
        });
      }
    }
  });
}

module.exports = {
  createQualityCollector,
  qualityFixture,
  DEFAULT_IGNORE_PATTERNS,
};
