import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REQUIRED_ENVS = [
  'H5_STAGING_BASE_URL',
  'H5_AUTH_USERNAME',
  'H5_AUTH_PASSWORD',
  'H5_AUTH_USERNAME_SELECTOR',
  'H5_AUTH_PASSWORD_SELECTOR',
  'H5_AUTH_SUBMIT_SELECTOR',
  'H5_AUTH_SUCCESS_SELECTOR',
];

function readArg(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return process.argv[index + 1] || fallback;
}

function cleanEnv(name) {
  return (process.env[name] || '').trim();
}

function realLoginEnabled() {
  return ['1', 'true', 'yes'].includes(cleanEnv('H5_REAL_LOGIN').toLowerCase());
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const outputPath = path.resolve(
  readArg(
    '--out',
    cleanEnv('H5_AUTH_STAGING_STORAGE_STATE') ||
      path.join(repoRoot, 'artifacts', 'h5-auth', 'staging-storage-state.json')
  )
);

let browser;

try {
  if (!realLoginEnabled()) {
    console.error('h5 staging auth login blocked: explicit opt-in missing');
    process.exit(64);
  }

  const missing = REQUIRED_ENVS.filter((name) => !cleanEnv(name));
  if (missing.length > 0) {
    console.error(`h5 staging auth login blocked: missing required env count ${missing.length}`);
    process.exit(65);
  }

  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(cleanEnv('H5_STAGING_BASE_URL'));
  await page.locator(cleanEnv('H5_AUTH_USERNAME_SELECTOR')).fill(cleanEnv('H5_AUTH_USERNAME'));
  await page.locator(cleanEnv('H5_AUTH_PASSWORD_SELECTOR')).fill(cleanEnv('H5_AUTH_PASSWORD'));
  await page.locator(cleanEnv('H5_AUTH_SUBMIT_SELECTOR')).click();
  await page.waitForSelector(cleanEnv('H5_AUTH_SUCCESS_SELECTOR'), { timeout: 15000 });

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await context.storageState({ path: outputPath });
  await page.close();
  await context.close();

  console.log(JSON.stringify({
    storage_state_generated: true,
    target: 'staging',
  }));
} catch (error) {
  console.error(`h5 staging auth login failed: ${error?.name || 'Error'}`);
  process.exit(1);
} finally {
  if (browser) {
    await browser.close();
  }
}
