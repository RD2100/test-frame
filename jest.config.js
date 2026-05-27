// Jest configuration — JS/Node unit tests
// Note: tests/miniapp/specs/ is reserved for miniapp Jest specs (currently empty).
// Miniapp E2E tests (fittrack/miniapp/) are standalone Node scripts (miniprogram-automator),
// not Jest tests. H5 Playwright tests use Playwright runner, not Jest.
// Available JS unit tests: tests/h5/support/__tests__/*.test.js
module.exports = {
  testEnvironment: 'node',
  testMatch: [
    '**/tests/h5/support/__tests__/**/*.test.js',
    '**/tests/miniapp/specs/**/*.test.js',
  ],
  testTimeout: 60000,
  verbose: true,
  reporters: ['default'],
  globals: {
    WECHAT_DEVTOOL_PATH: process.env.WECHAT_DEVTOOL_PATH || '',
    MINIPROGRAM_PATH: process.env.MINIPROGRAM_PATH || './miniprogram',
  },
};
