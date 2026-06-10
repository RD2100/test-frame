/**
 * Minimal Mock H5 Server for Explorer Verification
 *
 * Serves pages at localhost:5190 with routes: /, /login, /exercises, /exercises/create
 * Includes intentional issues for explorer detection:
 *   - /login: button with no JS feedback (click produces no toast/URL change)
 *   - /exercises/create: form that doesn't validate on empty submit
 *   - /blank: page with #app but no content (for blank-page oracle)
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 5190;
const REPORT_DIR = path.join(__dirname, '../../..', 'reports', 'ui-explorer');

// ---------- HTML Templates ----------

const LAYOUT = (title, body) => `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} - FitTrack Admin</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; color: #333; }
    #app { max-width: 1200px; margin: 0 auto; padding: 20px; }
    .header { background: #1a73e8; color: white; padding: 16px 24px; font-size: 20px; font-weight: bold; }
    .sidebar { float: left; width: 200px; background: #fff; padding: 16px; margin-right: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .sidebar a { display: block; padding: 8px 12px; color: #333; text-decoration: none; border-radius: 4px; margin-bottom: 4px; }
    .sidebar a:hover { background: #e8f0fe; }
    .main { margin-left: 220px; }
    .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .btn { display: inline-block; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    .btn-primary { background: #1a73e8; color: white; }
    .btn-danger { background: #d93025; color: white; }
    .btn-secondary { background: #e0e0e0; color: #333; }
    input, select, textarea { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; margin-bottom: 12px; }
    label { display: block; font-size: 13px; color: #666; margin-bottom: 4px; }
    .form-group { margin-bottom: 16px; }
    .toast { position: fixed; top: 20px; right: 20px; background: #333; color: white; padding: 12px 20px; border-radius: 8px; z-index: 9999; display: none; }
    .error-msg { color: #d93025; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
    th { color: #666; font-size: 13px; }
  </style>
</head>
<body>
  <div class="header">FitTrack Admin</div>
  <div id="app">
    <div class="sidebar">
      <a href="/">仪表盘</a>
      <a href="/exercises">动作库</a>
      <a href="/exercises/create">新建动作</a>
      <a href="/login">登录</a>
    </div>
    <div class="main">${body}</div>
  </div>
</body>
</html>`;

const DASHBOARD = LAYOUT('仪表盘 - FitTrack', `
  <h2 style="margin-bottom: 16px;">仪表盘</h2>
  <div class="card">
    <h3>今日概览</h3>
    <p>今日训练: <strong>3</strong> 次</p>
    <p>活跃用户: <strong>42</strong> 人</p>
    <button class="btn btn-primary" onclick="location.href='/exercises'">管理动作库</button>
    <button class="btn btn-secondary" onclick="location.href='/exercises/create'">新建动作</button>
  </div>
  <div class="card">
    <h3>快捷操作</h3>
    <button class="btn btn-primary" id="quick-stats">查看统计</button>
    <button class="btn btn-primary" id="quick-users">用户管理</button>
    <button class="btn btn-danger" id="quick-delete">删除全部数据</button>
    <script>
      document.getElementById('quick-stats').onclick = () => alert('统计功能开发中');
      document.getElementById('quick-users').onclick = () => {
        window.location.href = '/#users';
      };
    </script>
  </div>
`);

const LOGIN = LAYOUT('登录 - FitTrack', `
  <div class="card" style="max-width: 400px; margin: 40px auto;">
    <h3>管理员登录</h3>
    <div class="form-group">
      <label>邮箱</label>
      <input type="email" name="email" placeholder="admin@fittrack.com" />
    </div>
    <div class="form-group">
      <label>密码</label>
      <input type="password" name="password" placeholder="请输入密码" />
    </div>
    <!-- Intentional: No-feedback button — click produces no toast, no URL change, no DOM change -->
    <button class="btn btn-primary" id="login-btn-no-feedback">登录</button>
    <button class="btn btn-primary" id="login-btn-with-toast" style="margin-left:8px;">登录(有提示)</button>
    <p class="error-msg" id="login-error" style="display:none;">登录失败，请重试</p>
    <script>
      // No-feedback button: explorer should detect P3 issue
      document.getElementById('login-btn-no-feedback').onclick = () => {
        // Intentionally does nothing visible — no toast, no navigation, no DOM change
      };
      // Good button: shows toast (explorer detects feedback)
      document.getElementById('login-btn-with-toast').onclick = () => {
        window.location.href = '/';
      };
    </script>
  </div>
`);

const EXERCISES = LAYOUT('动作库 - FitTrack', `
  <h2 style="margin-bottom: 16px;">动作库</h2>
  <div class="card">
    <input type="text" name="search" placeholder="搜索动作..." style="width: 300px; display: inline-block;" />
    <button class="btn btn-primary" style="margin-left: 8px;">搜索</button>
    <select style="width: 200px; display: inline-block; margin-left: 16px;">
      <option value="">所有分类</option>
      <option value="chest">胸部</option>
      <option value="back">背部</option>
      <option value="legs">腿部</option>
    </select>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>名称</th><th>分类</th><th>难度</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr><td>卧推</td><td>胸部</td><td>中</td><td><button class="btn btn-primary">编辑</button> <button class="btn btn-danger">删除</button></td></tr>
        <tr><td>深蹲</td><td>腿部</td><td>中</td><td><button class="btn btn-primary">编辑</button> <button class="btn btn-danger">删除</button></td></tr>
        <tr><td>引体向上</td><td>背部</td><td>高</td><td><button class="btn btn-primary">编辑</button> <button class="btn btn-danger">删除</button></td></tr>
      </tbody>
    </table>
  </div>
`);

const EXERCISE_CREATE = LAYOUT('新建动作 - FitTrack', `
  <div class="card" style="max-width: 600px; margin: 20px auto;">
    <h3>新建动作</h3>
    <div class="form-group">
      <label>动作名称 *</label>
      <input type="text" name="name" placeholder="例如: 卧推" />
    </div>
    <div class="form-group">
      <label>分类</label>
      <select name="category">
        <option value="">请选择</option>
        <option value="chest">胸部</option>
        <option value="back">背部</option>
        <option value="legs">腿部</option>
      </select>
    </div>
    <div class="form-group">
      <label>描述</label>
      <textarea name="description" rows="3" placeholder="动作描述..."></textarea>
    </div>
    <!-- Intentional: form that doesn't validate on empty submit — P2 issue -->
    <form id="create-form" onsubmit="event.preventDefault(); /* no validation shown */">
      <button type="submit" class="btn btn-primary" id="submit-no-validate">保存</button>
      <button class="btn btn-secondary" onclick="location.href='/exercises'">取消</button>
    </form>
    <div class="form-group" style="margin-top: 16px;">
      <!-- Good button: shows feedback -->
      <button class="btn btn-primary" id="save-with-feedback">保存(有反馈)</button>
      <script>
        document.getElementById('save-with-feedback').onclick = () => {
          const toast = document.createElement('div');
          toast.className = 'toast';
          toast.textContent = '保存成功';
          toast.style.display = 'block';
          document.body.appendChild(toast);
          setTimeout(() => { toast.remove(); }, 2000);
        };
      </script>
    </div>
  </div>
`);

const BLANK = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Blank Page - FitTrack</title>
</head>
<body>
  <div id="app"></div>
  <script>
    // #app is present but intentionally empty — explorer should detect P1 blank page
  </script>
</body>
</html>`;

// ---------- Routes ----------
const routes = {
  '/': { html: DASHBOARD, status: 200 },
  '/login': { html: LOGIN, status: 200 },
  '/exercises': { html: EXERCISES, status: 200 },
  '/exercises/create': { html: EXERCISE_CREATE, status: 200 },
  '/blank': { html: BLANK, status: 200 },
  '/api/not-found': { html: '{"error":"not found"}', status: 404, type: 'application/json' },
  '/api/server-error': { html: '{"error":"internal error"}', status: 500, type: 'application/json' },
};

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const route = routes[url.pathname];

  if (route) {
    res.writeHead(route.status, { 'Content-Type': route.type || 'text/html; charset=utf-8' });
    res.end(route.html);
  } else {
    res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<html><body><h1>404 Not Found</h1></body></html>');
  }

  console.log(`${res.statusCode} ${req.method} ${url.pathname}`);
});

server.listen(PORT, () => {
  console.log(`[MOCK] FitTrack Admin running at http://localhost:${PORT}`);
  console.log(`[MOCK] Routes: ${Object.keys(routes).join(', ')}`);
  console.log(`[MOCK] Intentional issues:`);
  console.log(`  /login — no-feedback button (P3)`);
  console.log(`  /exercises/create — form without validation (P2)`);
  console.log(`  /blank — blank #app page (P1)`);
});

module.exports = server;
