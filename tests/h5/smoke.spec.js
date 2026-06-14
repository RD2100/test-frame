const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

test.describe('H5 local smoke fixture', () => {
  test('opens repo-local fixture and verifies interaction', async ({ page }, testInfo) => {
    expect(testInfo.project.name).toBe('chromium');

    const fixturePath = path.resolve(__dirname, '../../examples/app-h5/index.html');
    await page.goto(pathToFileURL(fixturePath).href);

    await expect(page).toHaveTitle('TestFrame H5 Fixture');
    await expect(page.getByTestId('heading')).toHaveText('TestFrame H5 Smoke Fixture');

    await page.getByTestId('increment').click();
    await expect(page.getByTestId('status')).toHaveText('clicked:1');
    await expect(page.locator('body')).toHaveAttribute('data-smoke-state', 'ready');
  });
});
