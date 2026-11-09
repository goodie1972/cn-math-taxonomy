'use strict';
/* 浏览器测试共用件：静态服务器 + headless Chrome + 裸 CDP。无 npm 依赖，需 Node 22+（全局 WebSocket/fetch）。 */
const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function until(fn, label) {
  const end = Date.now() + 20000;
  while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(100); }
  throw new Error('Timeout: ' + label);
}

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = [];
    ws.addEventListener('message', e => {
      const m = JSON.parse(e.data);
      if (m.id) {
        const p = this.pending.get(m.id); this.pending.delete(m.id);
        if (m.error) p.reject(new Error(p.method + ': ' + m.error.message)); else p.resolve(m.result);
      } else this.handlers.forEach(fn => fn(m));
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject, method }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
}

/* opt.stubs: { '/assets/stats-config.js': 'window.CNM_STATS = {};' }
 * opt.notFound: ['/data/bank/questions/math/三上.json']  —— 按 pathname 匹配，忽略 ?v= 查询串
 * hits 记录每个请求的 pathname 与响应字节数，供首屏体积实测。 */
function serve(root, opt) {
  opt = opt || {};
  const stubs = opt.stubs || {};
  const notFound = opt.notFound || [];
  const hits = [];
  const server = http.createServer((req, res) => {
    let file = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (file.endsWith('/')) file += 'index.html';
    const rec = { url: req.url, file, bytes: 0 };
    hits.push(rec);
    if (notFound.indexOf(file) >= 0) { res.writeHead(404); res.end(); return; }
    if (Object.prototype.hasOwnProperty.call(stubs, file)) { res.setHeader('Content-Type', 'text/javascript'); res.end(stubs[file]); return; }
    const full = path.resolve(root, '.' + file);
    if (!full.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
    fs.readFile(full, (err, data) => {
      if (err) { res.writeHead(404); res.end(); return; }
      rec.bytes = data.length;
      res.setHeader('Content-Type', MIME[path.extname(full)] || 'application/octet-stream');
      res.end(data);
    });
  });
  return { server, hits };
}

async function launch(out) {
  const profile = path.join(out, 'profile');
  fs.mkdirSync(profile, { recursive: true });
  const chromePath = [process.env.CHROME,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    (process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'
  ].find(p => p && fs.existsSync(p));
  if (!chromePath) throw new Error('找不到 Chrome/Chromium，请设置 CHROME 环境变量');
  const chrome = spawn(chromePath, [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-sync', '--disable-extensions', '--disable-component-update',
    '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'
  ], { stdio: ['ignore', 'ignore', fs.openSync(path.join(out, 'chrome.log'), 'w')] });
  const activePort = path.join(profile, 'DevToolsActivePort');
  await until(() => fs.existsSync(activePort), 'Chrome debugger');
  const port = fs.readFileSync(activePort, 'utf8').split('\n')[0];
  async function connect(targetId) {
    const tabs = await fetch('http://127.0.0.1:' + port + '/json').then(r => r.json());
    const tab = targetId ? tabs.find(t => t.id === targetId) : tabs.find(t => t.type === 'page');
    const ws = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', reject); });
    return new CDP(ws);
  }
  return { chrome, port, connect };
}

async function initPage(cdp, errors, viewport) {
  cdp.handlers.push(m => { if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails); });
  await cdp.send('Page.enable'); await cdp.send('Runtime.enable'); await cdp.send('Network.enable');
  await cdp.send('Network.setBypassServiceWorker', { bypass: true });
  await cdp.send('Emulation.setDeviceMetricsOverride', Object.assign({ width: 390, height: 844, deviceScaleFactor: 1, mobile: true }, viewport || {}));
}

module.exports = { serve, until, CDP, launch, initPage, MIME };