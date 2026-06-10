#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

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

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function uniqueRoutes(value) {
  if (!value) return [];
  if (Array.isArray(value)) return [...new Set(value.filter(Boolean))];
  return [...new Set(String(value).split(',').map((item) => item.trim()).filter(Boolean))];
}

function resolveMiniappRoot(projectPath) {
  if (!projectPath) {
    return {
      status: 'blocked',
      reason: 'miniapp project path is not configured',
    };
  }

  const root = path.resolve(projectPath);
  if (!fs.existsSync(root)) {
    return {
      status: 'blocked',
      reason: `miniapp project path not found: ${root}`,
      projectRoot: root,
    };
  }

  const directAppJson = path.join(root, 'app.json');
  if (fs.existsSync(directAppJson)) {
    return { status: 'passed', projectRoot: root, miniappRoot: root, appJsonPath: directAppJson };
  }

  const projectConfigPath = path.join(root, 'project.config.json');
  if (!fs.existsSync(projectConfigPath)) {
    return {
      status: 'blocked',
      reason: `app.json or project.config.json not found under: ${root}`,
      projectRoot: root,
    };
  }

  let projectConfig;
  try {
    projectConfig = readJson(projectConfigPath);
  } catch (error) {
    return {
      status: 'error',
      reason: `failed to parse project.config.json: ${error.message}`,
      projectRoot: root,
      projectConfigPath,
    };
  }

  const miniprogramRoot = projectConfig.miniprogramRoot || 'miniprogram/';
  const miniappRoot = path.resolve(root, miniprogramRoot);
  const appJsonPath = path.join(miniappRoot, 'app.json');
  if (!fs.existsSync(appJsonPath)) {
    return {
      status: 'blocked',
      reason: `app.json not found: ${appJsonPath}`,
      projectRoot: root,
      miniappRoot,
      projectConfigPath,
    };
  }

  return { status: 'passed', projectRoot: root, miniappRoot, appJsonPath, projectConfigPath };
}

function collectClickableSummary(miniappRoot, pages) {
  return pages.map((pagePath) => {
    const pageBase = path.join(miniappRoot, pagePath);
    const wxmlPath = `${pageBase}.wxml`;
    if (!fs.existsSync(wxmlPath)) {
      return { route: pagePath, wxmlPath, exists: false, tapEvents: [], buttonCount: 0 };
    }
    const wxml = fs.readFileSync(wxmlPath, 'utf8');
    const taps = [...wxml.matchAll(/\b(?:bindtap|catchtap)="([^"]+)"/g)].map((m) => m[1]);
    const buttons = [...wxml.matchAll(/<button\b/g)];
    return {
      route: pagePath,
      wxmlPath,
      exists: true,
      tapEvents: [...new Set(taps)],
      buttonCount: buttons.length,
    };
  });
}

function buildInventory(projectPath, requiredRoutes) {
  const resolved = resolveMiniappRoot(projectPath);
  if (resolved.status !== 'passed') {
    return { schema_version: 'test-frame.miniapp-route-preflight.v1', ...resolved };
  }

  let appJson;
  try {
    appJson = readJson(resolved.appJsonPath);
  } catch (error) {
    return {
      schema_version: 'test-frame.miniapp-route-preflight.v1',
      status: 'error',
      reason: `failed to parse app.json: ${error.message}`,
      ...resolved,
    };
  }

  const pages = Array.isArray(appJson.pages) ? appJson.pages : [];
  const tabBarRoutes = ((appJson.tabBar || {}).list || [])
    .map((item) => item && item.pagePath)
    .filter(Boolean);
  const missingRoutes = requiredRoutes.filter((route) => !pages.includes(route));
  const missingFiles = pages.filter((route) => {
    const pageBase = path.join(resolved.miniappRoot, route);
    return !fs.existsSync(`${pageBase}.js`) || !fs.existsSync(`${pageBase}.wxml`);
  });

  const status = missingRoutes.length || missingFiles.length ? 'blocked' : 'passed';
  return {
    schema_version: 'test-frame.miniapp-route-preflight.v1',
    status,
    reason: status === 'passed' ? '' : 'miniapp route preflight failed',
    projectRoot: resolved.projectRoot,
    miniappRoot: resolved.miniappRoot,
    appJsonPath: resolved.appJsonPath,
    totalRoutes: pages.length,
    pages,
    tabBarRoutes,
    requiredRoutes,
    missingRoutes,
    missingFiles,
    clickableSummary: collectClickableSummary(resolved.miniappRoot, pages),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectPath = args.project || process.env.FITTRACK_PATH || process.env.MINIPROGRAM_PATH || '';
  const requiredRoutes = uniqueRoutes(args['required-routes']);
  const result = buildInventory(projectPath, requiredRoutes);
  process.stdout.write(`${JSON.stringify(result)}\n`);
  if (result.status === 'passed') process.exitCode = 0;
  else if (result.status === 'blocked') process.exitCode = 2;
  else process.exitCode = 1;
}

if (require.main === module) {
  main();
}

module.exports = {
  buildInventory,
  parseArgs,
  uniqueRoutes,
};
