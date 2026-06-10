let cachedAutomatorPackage = null;
let cachedAutomator = null;

async function loadAutomator(options = {}) {
  const packageName = options['automator-package']
    || process.env.MINIAPP_AUTOMATOR_PACKAGE
    || 'miniprogram-automator';
  if (cachedAutomator && cachedAutomatorPackage === packageName) {
    return cachedAutomator;
  }
  const module = await import(packageName);
  const automatorModule = module.default || module;
  cachedAutomatorPackage = packageName;
  if (typeof automatorModule.connect === 'function') {
    cachedAutomator = automatorModule;
  } else if (typeof automatorModule.Automator === 'function') {
    cachedAutomator = new automatorModule.Automator();
  } else if (typeof automatorModule.Launcher === 'function') {
    const launcher = new automatorModule.Launcher();
    cachedAutomator = { connect: (options) => launcher.connect(options) };
  } else {
    throw new Error(`Automator package does not expose a connect API: ${packageName}`);
  }
  return cachedAutomator;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith('--')) continue;
    const key = item.slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      args[key] = next;
      i += 1;
    } else {
      args[key] = true;
    }
  }
  return args;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isConnectionError(error) {
  const message = String((error && error.message) || error || '');
  return message.includes('Connection closed')
    || message.includes('Failed connecting to ws://')
    || isTimeoutError(error);
}

function isTimeoutError(error) {
  return String((error && error.name) || '') === 'TimeoutError'
    || String((error && error.message) || error || '').includes('timed out after');
}

function operationTimeoutMs(options) {
  return Number(
    options['operation-timeout-ms']
    || options['operation-timeout']
    || process.env.MINIAPP_OPERATION_TIMEOUT_MS
    || 15000,
  );
}

function withTimeout(promise, timeoutMs, operation) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      const error = new Error(`${operation} timed out after ${timeoutMs}ms`);
      error.name = 'TimeoutError';
      error.operation = operation;
      reject(error);
    }, timeoutMs);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function normalizeRoute(route) {
  return String(route || '').trim().replace(/^\/+/, '');
}

async function safeData(page, timeoutMs) {
  try {
    return await withTimeout(page.data(), timeoutMs, 'page.data');
  } catch (_) {
    return null;
  }
}

async function safeCount(page, selector, timeoutMs) {
  try {
    const elements = await withTimeout(page.$$(selector), timeoutMs, 'page.$$');
    return elements.length;
  } catch (_) {
    return -1;
  }
}

function resultRecorder(results) {
  return {
    pass(name, extra = {}) {
      results.push({ name, status: 'passed', ...extra });
    },
    fail(name, error, extra = {}) {
      results.push({
        name,
        status: 'failed',
        error: String(error).slice(0, 240),
        ...extra,
      });
    },
    skip(name, reason, extra = {}) {
      results.push({
        name,
        status: 'skipped',
        error: String(reason).slice(0, 240),
        ...extra,
      });
    },
  };
}

async function navigate(mp, spec) {
  const route = `/${normalizeRoute(spec.route)}`;
  if (spec.nav === 'switchTab') {
    await withTimeout(mp.switchTab(route), spec.operationTimeoutMs, 'switchTab');
  } else if (spec.nav === 'reLaunch') {
    await withTimeout(mp.reLaunch(route), spec.operationTimeoutMs, 'reLaunch');
  } else {
    await withTimeout(mp.navigateTo(route), spec.operationTimeoutMs, 'navigateTo');
  }
}

function routeMatches(actual, expected) {
  return normalizeRoute(actual) === normalizeRoute(expected);
}

async function probePage(mp, spec, record) {
  try {
    await navigate(mp, spec);
    await sleep(spec.waitMs || 1200);
    const page = await withTimeout(mp.currentPage(), spec.operationTimeoutMs, 'currentPage');
    const data = await safeData(page, spec.operationTimeoutMs);
    const label = spec.name;

    if (routeMatches(page.path, spec.route)) {
      record.pass(`${label}:page_loaded`, { route: normalizeRoute(spec.route) });
    } else {
      record.fail(`${label}:page_loaded`, `expected ${spec.route}, got ${page.path}`, {
        route: normalizeRoute(spec.route),
      });
    }

    for (const field of spec.fields || []) {
      if (data && data[field] !== undefined) {
        record.pass(`${label}:field_${field}`);
      } else {
        record.skip(`${label}:field_${field}`, 'not in page data');
      }
    }

    const count = await safeCount(page, spec.selector || 'view, text, image, button, input', spec.operationTimeoutMs);
    if (count >= 0) {
      record.pass(`${label}:ui_elements=${count}`);
    } else {
      record.skip(`${label}:ui_elements`, 'query failed');
    }
  } catch (error) {
    record.fail(spec.name, error.message || error, { route: normalizeRoute(spec.route) });
  }
}

async function probeExerciseDetail(mp, record, timeoutMs) {
  try {
    await withTimeout(mp.switchTab('/pages/exercise/exercise'), timeoutMs, 'switchTab');
    await sleep(1000);
    const exercisePage = await withTimeout(mp.currentPage(), timeoutMs, 'currentPage');
    const exerciseData = await safeData(exercisePage, timeoutMs);
    const exercise = exerciseData && Array.isArray(exerciseData.exercises)
      ? exerciseData.exercises[0]
      : null;
    if (!exercise || !exercise._id) {
      record.skip('exercise-detail:page_loaded', 'no exercise id available');
      return;
    }
    await withTimeout(
      mp.navigateTo(`/pages/exercise/exercise-detail/exercise-detail?id=${exercise._id}`),
      timeoutMs,
      'navigateTo',
    );
    await sleep(1200);
    const page = await withTimeout(mp.currentPage(), timeoutMs, 'currentPage');
    const data = await safeData(page, timeoutMs);
    if (routeMatches(page.path, 'pages/exercise/exercise-detail/exercise-detail')) {
      record.pass('exercise-detail:page_loaded');
    } else {
      record.fail('exercise-detail:page_loaded', `expected exercise-detail, got ${page.path}`);
    }
    if (data && data.exercise !== undefined) {
      record.pass('exercise-detail:field_exercise');
    } else {
      record.skip('exercise-detail:field_exercise', 'not in page data');
    }
    await withTimeout(mp.navigateBack(), timeoutMs, 'navigateBack');
  } catch (error) {
    record.fail('exercise-detail', error.message || error);
  }
}

const GROUPS = {
  'login-index': [
    {
      name: 'login',
      route: 'pages/login/login',
      nav: 'reLaunch',
      fields: ['loading', 'userInfo'],
    },
    {
      name: 'index',
      route: 'pages/index/index',
      nav: 'switchTab',
      fields: ['greeting', 'weekStats', 'recentWorkouts'],
    },
  ],
  tabs: [
    { name: 'index', route: 'pages/index/index', nav: 'switchTab', fields: ['greeting'] },
    { name: 'training', route: 'pages/training/training', nav: 'switchTab', fields: ['currentTab'] },
    { name: 'exercise', route: 'pages/exercise/exercise', nav: 'switchTab', fields: ['keyword', 'categories'] },
    { name: 'profile', route: 'pages/profile/profile', nav: 'switchTab', fields: ['userInfo', 'totalStats'] },
  ],
  training: [
    { name: 'training', route: 'pages/training/training', nav: 'switchTab', fields: ['currentTab'] },
  ],
  exercise: [
    {
      name: 'exercise',
      route: 'pages/exercise/exercise',
      nav: 'switchTab',
      fields: ['keyword', 'currentCategory', 'categories', 'exercises'],
    },
  ],
  profile: [
    { name: 'profile', route: 'pages/profile/profile', nav: 'switchTab', fields: ['userInfo', 'totalStats'] },
    { name: 'profile-edit', route: 'pages/profile/profile-edit/profile-edit', fields: ['nickname', 'height', 'weight'] },
    { name: 'body-metrics', route: 'pages/profile/body-metrics/body-metrics', fields: ['metrics', 'loading'] },
    { name: 'personal-records', route: 'pages/profile/personal-records/personal-records', fields: ['records', 'loading'] },
  ],
  'profile-main': [
    { name: 'profile', route: 'pages/profile/profile', nav: 'switchTab', fields: ['userInfo', 'totalStats'] },
  ],
  'profile-edit': [
    { name: 'profile-edit', route: 'pages/profile/profile-edit/profile-edit', fields: ['nickname', 'height', 'weight'] },
  ],
  'profile-body-metrics': [
    { name: 'body-metrics', route: 'pages/profile/body-metrics/body-metrics', fields: ['metrics', 'loading'] },
  ],
  'profile-personal-records': [
    { name: 'personal-records', route: 'pages/profile/personal-records/personal-records', fields: ['records', 'loading'] },
  ],
  'workout-plan-admin': [
    { name: 'workout-detail', route: 'pages/workout-detail/workout-detail', fields: ['workoutId', 'workout'] },
    { name: 'plan-edit', route: 'pages/plan-edit/plan-edit', fields: ['planId', 'plan', 'goals'] },
    { name: 'stats', route: 'pages/stats/stats', fields: ['period', 'stats'] },
    { name: 'seed-data', route: 'pages/admin/seed-data/seed-data', fields: ['stats', 'categoryProgress'] },
  ],
  'workout-detail': [
    { name: 'workout-detail', route: 'pages/workout-detail/workout-detail', fields: ['workoutId', 'workout'] },
  ],
  'plan-edit': [
    { name: 'plan-edit', route: 'pages/plan-edit/plan-edit', fields: ['planId', 'plan', 'goals'] },
  ],
  stats: [
    { name: 'stats', route: 'pages/stats/stats', fields: ['period', 'stats'] },
  ],
  'seed-data': [
    { name: 'seed-data', route: 'pages/admin/seed-data/seed-data', fields: ['stats', 'categoryProgress'] },
  ],
};

async function runGroup(options) {
  const group = options.group || 'login-index';
  const specs = GROUPS[group];
  const results = [];
  const record = resultRecorder(results);
  const endpoint = `ws://localhost:${Number(options.port || 19541)}`;
  const timeoutMs = operationTimeoutMs(options);
  const automator = await loadAutomator(options);
  let mp;

  if (!specs) {
    record.fail('env:group', `unknown group: ${group}`);
    record.skip('env:known_groups', Object.keys(GROUPS).join(','));
    return results;
  }

  try {
    mp = await withTimeout(automator.connect({ wsEndpoint: endpoint }), timeoutMs, 'connect');
    record.pass(`env:group=${group}`);
    const initialPage = await withTimeout(mp.currentPage(), timeoutMs, 'currentPage');
    record.pass(`env:page=${initialPage.path}`);
  } catch (error) {
    record.fail('fatal', error.message || error);
    return results;
  }

  for (const spec of specs) {
    await probePage(mp, { ...spec, operationTimeoutMs: timeoutMs }, record);
  }

  if (group === 'exercise') {
    await probeExerciseDetail(mp, record, timeoutMs);
  }

  try {
    mp.disconnect();
  } catch (_) {
    record.skip('env:disconnect', 'disconnect failed');
  }

  return results;
}

function emitResults(results, shouldExit = false) {
  const failed = results.filter((item) => item.status === 'failed').length;
  const exitCode = failed > 0 ? 1 : 0;
  const output = `MINIAPP_RESULTS:${JSON.stringify(results)}\n`;
  if (shouldExit) {
    process.stdout.write(output, () => process.exit(exitCode));
  } else {
    process.stdout.write(output);
    process.exitCode = exitCode;
  }
}

async function main() {
  const results = await runGroup(parseArgs(process.argv.slice(2)));
  if (results.some((item) => item.name === 'fatal' && isConnectionError(item.error))) {
    process.exitCode = 1;
  }
  emitResults(results, true);
}

if (require.main === module) {
  main().catch((error) => {
    emitResults([{ name: 'fatal', status: 'failed', error: error.message || String(error) }], true);
  });
}

module.exports = {
  GROUPS,
  isConnectionError,
  isTimeoutError,
  loadAutomator,
  normalizeRoute,
  operationTimeoutMs,
  parseArgs,
  runGroup,
  withTimeout,
};
