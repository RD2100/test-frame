import { chromium } from '@playwright/test';

const browserName = process.argv[2] || 'chromium';

if (browserName !== 'chromium') {
  console.error(`Unsupported browser probe: ${browserName}`);
  process.exit(64);
}

let browser;

try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('about:blank');
  const userAgent = await page.evaluate(() => navigator.userAgent);
  await page.close();

  console.log(JSON.stringify({
    browser: 'chromium',
    launched: true,
    userAgent,
  }));
} catch (error) {
  console.error(error?.stack || error?.message || String(error));
  process.exit(1);
} finally {
  if (browser) {
    await browser.close();
  }
}
