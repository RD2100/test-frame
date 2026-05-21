// MiniApp E2E test - connects to running IDE in automation mode
const automator = require('miniprogram-automator');
const PORT = 19541;

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:' + PORT });
  const results = [];
  const add = (name, status) => results.push({ name, status });

  let p = await mp.currentPage(); add('page:' + p.path, 'passed');
  let s = await mp.systemInfo(); add('system:' + s.platform, 'passed');

  const tabs = [
    ['exercise', '/pages/exercise/exercise'],
    ['training', '/pages/training/training'],
    ['profile', '/pages/profile/profile'],
    ['index', '/pages/index/index'],
  ];
  for (const [name, path] of tabs) {
    await mp.switchTab(path); await sleep(700);
    add('tab_' + name, 'passed');
  }

  await mp.switchTab('/pages/index/index'); await sleep(1000);
  let d = await (await mp.currentPage()).data();
  add('index_data:' + Object.keys(d || {}).join(','), 'passed');

  await mp.switchTab('/pages/exercise/exercise'); await sleep(1500);
  d = await (await mp.currentPage()).data();
  add('exercise_data:' + Object.keys(d || {}).join(','), 'passed');

  await mp.screenshot({ path: 'reports/fittrack/screenshot.png' });
  add('screenshot', 'passed');

  await mp.close();
  console.log('MINIAPP_RESULTS:' + JSON.stringify(results));
}

main().catch(e => {
  console.log('MINIAPP_RESULTS:' + JSON.stringify([{ name: 'error', status: 'failed', error: e.message }]));
});
