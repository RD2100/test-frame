#!/usr/bin/env node
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

function uniqueRoutes(value) {
  if (!value) return [];
  if (Array.isArray(value)) return [...new Set(value.map(normalizeRoute).filter(Boolean))];
  return [...new Set(String(value).split(',').map(normalizeRoute).filter(Boolean))];
}

function normalizeRoute(route) {
  return String(route || '').trim().replace(/^\/+/, '');
}

function toMiniappUrl(route) {
  return `/${normalizeRoute(route)}`;
}

function isConnectionError(error) {
  const message = String((error && error.message) || error || '');
  return message.includes('Failed connecting to ws://')
    || message.includes('Connection closed')
    || isTimeoutError(error);
}

function isTimeoutError(error) {
  return String((error && error.name) || '') === 'TimeoutError'
    || String((error && error.message) || error || '').includes('timed out after');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

async function runProbe(options) {
  const port = Number(options.port || 9420);
  const host = options.host || 'localhost';
  const waitMs = Number(options['wait-ms'] || 1000);
  const opTimeoutMs = operationTimeoutMs(options);
  const automator = await loadAutomator(options);
  const routes = uniqueRoutes(options['required-routes']);
  const endpoint = `ws://${host}:${port}`;
  let mp;

  try {
    mp = await withTimeout(automator.connect({ wsEndpoint: endpoint }), opTimeoutMs, 'connect');
  } catch (error) {
    return {
      schema_version: 'test-frame.miniapp-runtime-probe.v1',
      status: 'blocked',
      error_type: 'RESOURCE_UNAVAILABLE',
      reason: isTimeoutError(error)
        ? `miniprogram-automator connect timed out at ${endpoint}`
        : `miniprogram-automator could not connect to ${endpoint}`,
      endpoint,
      message: error.message,
    };
  }

  try {
    const initialPage = await withTimeout(mp.currentPage(), opTimeoutMs, 'currentPage');
    const initialPath = normalizeRoute(initialPage.path);
    const stack = await withTimeout(mp.pageStack(), opTimeoutMs, 'pageStack');
    const result = {
      schema_version: 'test-frame.miniapp-runtime-probe.v1',
      status: 'passed',
      reason: '',
      endpoint,
      initialPage: initialPath,
      currentPage: initialPath,
      stack: stack.map((page) => normalizeRoute(page.path)),
      expectedRoutes: routes,
    };

    if (routes.length === 0) {
      return result;
    }

    if (routes.includes(initialPath)) {
      return result;
    }

    const targetRoute = routes[0];
    try {
      await withTimeout(mp.reLaunch(toMiniappUrl(targetRoute)), opTimeoutMs, 'reLaunch');
      await sleep(waitMs);
      const relaunchedPage = await withTimeout(mp.currentPage(), opTimeoutMs, 'currentPage');
      const relaunchedPath = normalizeRoute(relaunchedPage.path);
      result.currentPage = relaunchedPath;
      result.relaunchTarget = targetRoute;

      if (routes.includes(relaunchedPath)) {
        return result;
      }

      return {
        ...result,
        status: 'blocked',
        error_type: 'RUNTIME_PROJECT_MISMATCH',
        reason: `MiniApp runtime opened unexpected page: ${relaunchedPath}`,
      };
    } catch (error) {
      return {
        ...result,
        status: isConnectionError(error) ? 'blocked' : 'blocked',
        error_type: isConnectionError(error) ? 'RESOURCE_UNAVAILABLE' : 'RUNTIME_PROJECT_MISMATCH',
        reason: isTimeoutError(error)
          ? `miniprogram-automator ${error.operation || 'operation'} timed out during runtime probe`
          : isConnectionError(error)
          ? 'miniprogram-automator connection closed during runtime probe'
          : `MiniApp runtime does not contain expected route: ${targetRoute}`,
        message: error.message,
        relaunchTarget: targetRoute,
      };
    }
  } catch (error) {
    return {
      schema_version: 'test-frame.miniapp-runtime-probe.v1',
      status: isConnectionError(error) ? 'blocked' : 'error',
      error_type: isConnectionError(error) ? 'RESOURCE_UNAVAILABLE' : 'RUNTIME_PROBE_ERROR',
      reason: isTimeoutError(error)
        ? `miniprogram-automator ${error.operation || 'operation'} timed out during runtime probe`
        : isConnectionError(error)
        ? 'miniprogram-automator connection closed during runtime probe'
        : `miniapp runtime probe failed: ${error.message}`,
      endpoint,
      message: error.message,
    };
  } finally {
    if (mp) {
      try {
        mp.disconnect();
      } catch (_) {
        // Best-effort cleanup only; probe result has already been decided.
      }
    }
  }
}

async function main() {
  const result = await runProbe(parseArgs(process.argv.slice(2)));
  const exitCode = result.status === 'passed' ? 0 : (result.status === 'blocked' ? 2 : 1);
  process.stdout.write(`${JSON.stringify(result)}\n`, () => process.exit(exitCode));
}

if (require.main === module) {
  main();
}

module.exports = {
  isConnectionError,
  isTimeoutError,
  loadAutomator,
  normalizeRoute,
  operationTimeoutMs,
  parseArgs,
  runProbe,
  uniqueRoutes,
  withTimeout,
};
