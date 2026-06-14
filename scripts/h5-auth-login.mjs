import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DEMO_EMAIL = 'demo@example.test';
const DEMO_PASSWORD = 'demo-password';

function readArg(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return process.argv[index + 1] || fallback;
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const fixturePath = path.resolve(readArg('--fixture', path.join(repoRoot, 'examples', 'app-h5-auth', 'index.html')));
const outputPath = path.resolve(readArg('--out', path.join(repoRoot, 'artifacts', 'h5-auth', 'storage-state.json')));

let browser;
let server;

async function startFixtureServer(filePath) {
  const html = await fs.readFile(filePath, 'utf8');
  const localServer = http.createServer((request, response) => {
    if (request.url !== '/' && request.url !== '/index.html') {
      response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('not found');
      return;
    }
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    response.end(html);
  });
  await new Promise((resolve, reject) => {
    localServer.once('error', reject);
    localServer.listen(0, '127.0.0.1', resolve);
  });
  const address = localServer.address();
  if (!address || typeof address === 'string') {
    throw new Error('fixture server did not expose a TCP port');
  }
  return {
    server: localServer,
    url: `http://127.0.0.1:${address.port}/`,
  };
}

try {
  const fixture = await startFixtureServer(fixturePath);
  server = fixture.server;
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(fixture.url);
  await page.getByTestId('email').fill(DEMO_EMAIL);
  await page.getByTestId('password').fill(DEMO_PASSWORD);
  await page.getByTestId('login-submit').click();
  await page.waitForSelector('[data-testid="login-success"]', { timeout: 5000 });

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await context.storageState({ path: outputPath });
  await page.close();
  await context.close();

  console.log(JSON.stringify({
    storage_state_generated: true,
    fixture: 'repo-local',
  }));
} catch (error) {
  console.error(`h5 auth login failed: ${error?.name || 'Error'}`);
  process.exit(1);
} finally {
  if (browser) {
    await browser.close();
  }
  if (server) {
    await new Promise((resolve) => server.close(resolve));
  }
}
