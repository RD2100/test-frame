/**
 * Unit tests for FitTrack business oracles.
 * Run: node tests/h5/support/__tests__/oracles.test.js
 * Uses Node assert (no external deps).
 */

const assert = require('assert');
const path = require('path');

const oracles = require(path.resolve(__dirname, '../ui-oracles.js'));

// ---- Helpers ----

let passed = 0;
let failed = 0;
let errors = [];

function test(name, fn) {
  try {
    fn();
    process.stdout.write(`  PASS: ${name}\n`);
    passed++;
  } catch (e) {
    process.stdout.write(`  FAIL: ${name}\n    ${e.message}\n`);
    failed++;
    errors.push({ name, message: e.message });
  }
}

function assertNotNull(actual, msg) {
  assert.ok(actual !== null && actual !== undefined, msg || 'Expected non-null result');
}

function assertNull(actual, msg) {
  assert.strictEqual(actual, null, msg || 'Expected null result');
}

function assertSeverity(issue, expected, msg) {
  assert.strictEqual(issue.severity, expected, msg || `Expected severity ${expected}, got ${issue.severity}`);
}

// ============================================================
// oracleLoginFailure
// ============================================================
console.log('\noracleLoginFailure:');

test('detects error on login page with error text', () => {
  const pageState = {
    url: 'http://localhost:5190/login',
    bodyText: '密码错误，请重试',
    hasErrorMsg: true,
  };
  const result = oracles.oracleLoginFailure(pageState, []);
  assertNotNull(result, 'Should detect login error');
  assertSeverity(result, 'P2', 'Login failure should be P2');
  assert.ok(result.title.includes('Login'), 'Title should mention login');
});

test('returns null when not on /login', () => {
  const pageState = {
    url: 'http://localhost:5190/dashboard',
    bodyText: 'Welcome',
  };
  const result = oracles.oracleLoginFailure(pageState, []);
  assertNull(result, 'Should not flag non-login pages');
});

test('returns null when on /login but no error text', () => {
  const pageState = {
    url: 'http://localhost:5190/login',
    bodyText: 'FitTrack Admin',
  };
  const result = oracles.oracleLoginFailure(pageState, []);
  assertNull(result, 'Should not flag clean login page');
});

// ============================================================
// oracleEmptyList
// ============================================================
console.log('\noracleEmptyList:');

test('detects empty list without empty-state hint', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '动作库管理',
    hasTable: true,
    tableRowCount: 0,
    emptyStateVisible: false,
  };
  const result = oracles.oracleEmptyList(pageState, '.el-table');
  assertNotNull(result, 'Should detect missing empty-state');
  assertSeverity(result, 'P2');
});

test('returns null when table has rows', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '名称  分类  难度',
    hasTable: true,
    tableRowCount: 5,
  };
  const result = oracles.oracleEmptyList(pageState, '.el-table');
  assertNull(result, 'Should not flag when table has data');
});

test('returns null when empty but shows "暂无数据"', () => {
  const pageState = {
    url: 'http://localhost:5190/plans',
    bodyText: '暂无数据',
    hasTable: true,
    tableRowCount: 0,
  };
  const result = oracles.oracleEmptyList(pageState);
  assertNull(result, 'Should not flag when empty-state text is present');
});

test('returns null when page has no table', () => {
  const pageState = {
    url: 'http://localhost:5190/dashboard',
    bodyText: '仪表盘概览',
    hasTable: false,
  };
  const result = oracles.oracleEmptyList(pageState);
  assertNull(result, 'Should skip pages without tables');
});

// ============================================================
// oracleFormRequiredValidation
// ============================================================
console.log('\noracleFormRequiredValidation:');

test('detects missing validation on empty submit', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises/create',
    bodyText: '新增动作',
    hasFormError: false,
  };
  const actions = [
    { type: 'click', target: 'button:保存', status: 'passed' },
  ];
  const result = oracles.oracleFormRequiredValidation(pageState, actions);
  assertNotNull(result, 'Should detect missing required-field validation');
  assertSeverity(result, 'P2');
});

test('returns null when validation text is visible', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises/create',
    bodyText: '请输入动作名称',
    hasFormError: true,
  };
  const actions = [
    { type: 'click', target: 'button:保存', status: 'passed' },
  ];
  const result = oracles.oracleFormRequiredValidation(pageState, actions);
  assertNull(result, 'Should not flag when validation is visible');
});

test('returns null when no submit action occurred', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises/create',
    bodyText: '新增动作',
    hasFormError: false,
  };
  const actions = [
    { type: 'fill', target: 'input:name', status: 'passed' },
  ];
  const result = oracles.oracleFormRequiredValidation(pageState, actions);
  assertNull(result, 'Should not trigger without a submit click');
});

test('identifies submit via "创建" button', () => {
  const pageState = {
    url: 'http://localhost:5190/plans/create',
    bodyText: '创建计划',
  };
  const actions = [
    { type: 'click', target: 'button:创建计划', status: 'passed' },
  ];
  const result = oracles.oracleFormRequiredValidation(pageState, actions);
  assertNotNull(result, '"创建计划" should count as a submit action');
});

// ============================================================
// oracleApiHttpError
// ============================================================
console.log('\noracleApiHttpError:');

test('classifies 401 as P1', () => {
  const networkErrors = [
    { url: 'https://api.fittrack.com/admin/users', status: 401, method: 'GET' },
  ];
  const results = oracles.oracleApiHttpError(networkErrors);
  assert.strictEqual(results.length, 1, 'Should produce 1 issue');
  assert.strictEqual(results[0].severity, 'P1', '401 should be P1');
  assert.ok(results[0].title.includes('Auth error'), 'Title should mention auth');
});

test('classifies 403 as P1', () => {
  const networkErrors = [
    { url: 'https://api.fittrack.com/admin/exercises', status: 403, method: 'POST' },
  ];
  const results = oracles.oracleApiHttpError(networkErrors);
  assert.strictEqual(results[0].severity, 'P1');
});

test('classifies 500 as P1', () => {
  const networkErrors = [
    { url: 'https://api.fittrack.com/cloud/fn', status: 500, method: 'GET' },
  ];
  const results = oracles.oracleApiHttpError(networkErrors);
  assert.strictEqual(results[0].severity, 'P1');
  assert.ok(results[0].title.includes('Server error'), 'Title should mention server error');
});

test('classifies 404 as P2', () => {
  const networkErrors = [
    { url: 'https://api.fittrack.com/admin/missing', status: 404, method: 'GET' },
  ];
  const results = oracles.oracleApiHttpError(networkErrors);
  assert.strictEqual(results[0].severity, 'P2');
});

test('handles string-format network errors', () => {
  const networkErrors = [
    'HTTP_500: POST https://api.fittrack.com/admin/login',
    'HTTP_403: GET https://api.fittrack.com/admin/plans?page=1',
    'REQUEST_FAILED: GET https://api.fittrack.com/admin/stats — net::ERR_CONNECTION_REFUSED',
  ];
  const results = oracles.oracleApiHttpError(networkErrors);
  assert.strictEqual(results.length, 3, 'All 3 errors should be classified');
  assert.strictEqual(results[0].severity, 'P1', '500 → P1');
  assert.strictEqual(results[1].severity, 'P1', '403 → P1');
  assert.strictEqual(results[2].severity, 'P1', 'Request failed → P1');
});

test('returns empty array for no errors', () => {
  const results = oracles.oracleApiHttpError([]);
  assert.strictEqual(results.length, 0, 'Empty input should give no issues');
});

// ============================================================
// oracleAuthGatedRoute
// ============================================================
console.log('\noracleAuthGatedRoute:');

test('flags protected route accessible without auth', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '动作库管理  新增动作',
    hasAuthToken: false,
    redirected: false,
  };
  const result = oracles.oracleAuthGatedRoute(pageState);
  assertNotNull(result, 'Should flag unprotected access');
  assertSeverity(result, 'P2');
  assert.ok(result.title.includes('Protected'), 'Title should mention protected route');
});

test('passes when redirected to /login', () => {
  const pageState = {
    url: 'http://localhost:5190/login',
    bodyText: 'FitTrack Admin',
    hasAuthToken: false,
    redirected: true,
  };
  const result = oracles.oracleAuthGatedRoute(pageState);
  assertNull(result, 'Should pass when redirect to /login occurred');
});

test('passes when user has auth token', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '动作库管理',
    hasAuthToken: true,
  };
  const result = oracles.oracleAuthGatedRoute(pageState);
  assertNull(result, 'Should pass when auth token is present');
});

test('passes for non-protected routes', () => {
  const pageState = {
    url: 'http://example.com/public',
    bodyText: 'Public page',
    hasAuthToken: false,
  };
  const result = oracles.oracleAuthGatedRoute(pageState);
  assertNull(result, 'External URLs should be skipped');
});

// ============================================================
// oracleSearchNoResult
// ============================================================
console.log('\noracleSearchNoResult:');

test('detects search with no results and no feedback', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '动作库管理',
    hasTable: true,
    tableRowCount: 0,
  };
  const result = oracles.oracleSearchNoResult(pageState, '不存在的动作');
  assertNotNull(result, 'Should detect missing no-result hint');
  assertSeverity(result, 'P2');
});

test('passes when "未找到" is visible', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '未找到"xyz"相关动作',
    hasTable: true,
    tableRowCount: 0,
  };
  const result = oracles.oracleSearchNoResult(pageState, 'xyz');
  assertNull(result, 'Should pass when "未找到" hint is present');
});

test('does not trigger when table has results', () => {
  const pageState = {
    url: 'http://localhost:5190/exercises',
    bodyText: '深蹲',
    hasTable: true,
    tableRowCount: 3,
  };
  const result = oracles.oracleSearchNoResult(pageState, '深蹲');
  assertNull(result, 'Should not trigger when results exist');
});

// ============================================================
// oracleSaveFeedback
// ============================================================
console.log('\noracleSaveFeedback:');

test('returns null when no save action present', () => {
  const pageState = { url: '/exercises/create', bodyText: '新增动作' };
  const actions = [{ type: 'fill', target: 'input:name', status: 'passed' }];
  const result = oracles.oracleSaveFeedback(pageState, actions);
  assertNull(result, 'Should skip when no save/submit click');
});

// ============================================================
// oraclePaginationVisible
// ============================================================
console.log('\noraclePaginationVisible:');

test('returns null when no table on page', () => {
  const pageState = { url: '/login', hasTable: false };
  const result = oracles.oraclePaginationVisible(pageState);
  assertNull(result, 'Should skip non-table pages');
});

// ============================================================
// Summary
// ============================================================
console.log(`\n--- Results ---`);
console.log(`Total: ${passed + failed} | Passed: ${passed} | Failed: ${failed}`);

if (errors.length > 0) {
  console.log('\nFailures:');
  errors.forEach((e, i) => {
    console.log(`  ${i + 1}. ${e.name}\n     ${e.message}`);
  });
}

process.exitCode = failed > 0 ? 1 : 0;
