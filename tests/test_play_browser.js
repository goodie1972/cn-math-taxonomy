#!/usr/bin/env node
/* 孩子端浏览器实测：node tests/test_play_browser.js（390×844 手机视口，需 Chrome）。 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { serve, until, launch, initPage } = require('./browser_harness.js');
const root = path.resolve(__dirname, '..');
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'cnm-play-browser-'));
const notFound = [];
const { server, hits } = serve(root, { stubs: { '/assets/stats-config.js': 'window.CNM_STATS = {};' }, notFound });
let chrome, page;
(async () => {
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const base = 'http://127.0.0.1:' + server.address().port;
  const l = await launch(out); chrome = l.chrome;
  page = await l.connect();
  const errors = [];
  await initPage(page, errors);
  async function go(pathname) {
    await page.send('Page.navigate', { url: base + pathname });
    await until(() => page.eval('document.readyState === "complete"'), 'load ' + pathname);
  }
  async function playReady() {
    await until(() => page.eval('!!window.__play && !document.querySelector(".play-loading")'), 'play ready');
  }

  await go('/children/');
  await until(() => page.eval('!!window.CnmChildren'), 'children api');
  await page.eval(`(() => {
    const r = CnmChildren.add({ name: '小满', grade: '三年级', textbook: '人教版',
      subjects: { math: { edition: 'cn_renjiao', volume: '三上', confirm: 3 } } });
    if (!r.ok) throw new Error(r.error);
  })()`);

  hits.length = 0;
  await go('/play/?subject=math');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'home title');
  assert.ok(await page.eval('document.querySelector(".play-title").textContent.includes("小满")'));
  assert.ok(await page.eval('document.querySelector(".play-sub").textContent.includes("三上")'));
  assert.equal(await page.eval('!!document.querySelector(".site-nav") || !!document.querySelector(".top-banner") || !!document.querySelector(".site-header")'), false);
  assert.equal(await page.eval('document.querySelectorAll(".play-subject").length'), 8);
  assert.ok(await page.eval('document.documentElement.scrollWidth <= innerWidth'), '390px 无横向溢出');
  const homeHits = hits.filter(h => h.bytes > 0).map(h => h.file);
  assert.ok(homeHits.some(f => f === '/data/bank/manifest.json'));
  assert.ok(homeHits.some(f => f === '/data/bank/graph/math.json'));
  assert.ok(homeHits.some(f => f === '/data/bank/order/cn_renjiao/math.json'));
  assert.equal(homeHits.some(f => f === '/data/questions.json'), false, '孩子端不得整包取题库');
  assert.equal(homeHits.some(f => f.indexOf('/data/bank/questions/') === 0), false, '首页不取题库分片');

  await page.eval('document.querySelector(".play-go").click()');
  await until(() => page.eval('!!document.querySelector(".play-prompt")'), 'ask screen');
  assert.equal(await page.eval('document.querySelectorAll(".play-cell").length'), 5);
  assert.equal(await page.eval('!!document.querySelector(".play-prompt").textContent.match(/先修|不稳|置信度|拓扑/)'), false);
  const minTarget = await page.eval(`Math.min(...Array.from(document.querySelectorAll('.play button')).map(n => n.getBoundingClientRect().height))`);
  assert.ok(minTarget >= 64, '触摸目标 ≥64px，实测 ' + minTarget);
  assert.ok(await page.eval(`(() => { const it = __play.state.ctx.item; return it.question.type === 'choice' || it.question.type === 'numeric'; })()`));
  assert.notEqual(await page.eval('__play.state.ctx.item.question.type'), 'legacy');
  const firstQid = await page.eval('__play.state.ctx.item.question.id');

  // 答对：点正确选项 → 绿勾 → 1 秒后自动下一题
  await page.eval(`(() => {
    const q = __play.state.ctx.item.question;
    if (q.type === 'choice') {
      const i = q.choices.findIndex(c => c.key === q.answer);
      document.querySelectorAll('.play-choice')[i].click();
    } else {
      document.getElementById('play-answer').value = q.answer;
      document.querySelectorAll('.play-card button.play-go')[0].click();
    }
  })()`);
  await until(() => page.eval('!!document.querySelector(".play-card.is-ok")'), 'correct feedback');
  assert.ok(await page.eval('document.querySelector(".play-verdict").textContent.includes("答对了")'));
  await until(() => page.eval('!!document.querySelector(".play-prompt")'), 'auto advance');
  assert.notEqual(await page.eval('__play.state.ctx.item.question.id'), firstQid);
  assert.ok(await page.eval(`JSON.parse(localStorage.getItem('cnmPlay.seen.v1.' + __play.state.childId)).includes(${JSON.stringify(firstQid)})`));

  // 答错：点错误选项 → 红叉 + 正确答案 + 解析 + 「我懂了」才继续
  await page.eval(`(() => {
    const q = __play.state.ctx.item.question;
    if (q.type === 'choice') {
      const i = q.choices.findIndex(c => c.key !== q.answer);
      document.querySelectorAll('.play-choice')[i].click();
    } else {
      document.getElementById('play-answer').value = '不可能对的答案';
      document.querySelectorAll('.play-card button.play-go')[0].click();
    }
  })()`);
  await until(() => page.eval('!!document.querySelector(".play-card.is-no")'), 'wrong feedback');
  assert.ok(await page.eval('document.querySelector(".play-answer-is").textContent.includes("正确答案")'));
  assert.ok(await page.eval('!!document.querySelector(".play-explain")'));
  assert.equal(await page.eval('!!document.querySelector(".play-prompt")'), false, '答错必须停在反馈屏，不自动跳');
  await page.eval('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "我懂了").click()');
  await until(() => page.eval('!!document.querySelector(".play-prompt")'), 'continue after 我懂了');

  // 剩下的题直接驱动 commit 跑完（避开 25 × 1 秒的自动跳等待），验证完成屏与记录写入
  await page.eval(`(async () => {
    const st = __play.state; let guard = 0;
    while (st.ctx && st.ctx.item && guard++ < 80) await __play.commit('correct', st.ctx.item.question.answer);
  })()`);
  await until(() => page.eval('!!document.querySelector(".play-done")'), 'done screen');
  assert.equal(await page.eval('document.querySelectorAll(".play-results li").length'), 5);
  assert.ok(await page.eval('document.querySelector(".play-done h1").textContent.includes("今天练完了")'));
  assert.equal(await page.eval('document.body.textContent.includes("未测")'), false);
  const rec = await page.eval(`(() => {
    const rs = CnmChildren.recordsOf(__play.state.childId);
    return rs.length ? { n: rs.length, subject: rs[0].subject, mode: rs[0].mode, asked: rs[0].asked, targets: rs[0].targets, label: rs[0].label } : null;
  })()`);
  assert.ok(rec, '完成屏必须写诊断记录');
  assert.equal(rec.n, 1);
  assert.equal(rec.subject, 'math');
  assert.equal(rec.mode, 'target');
  assert.ok(rec.asked > 0);
  assert.equal(rec.targets.length, 5);
  assert.ok(rec.label.includes('同步练习'));
  assert.ok(await page.eval(`CnmChildren.recordsOf(__play.state.childId)[0].key.split('|').length === 3`));

  await page.eval('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "明天再来").click()');
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'back home');
  assert.deepEqual(errors, []);
  console.log('PASS: 黄金路径 首页→开始→答对自动跳→答错停反馈→我懂了→完成→记录写入档案→回首页（390×844，无页面异常）');
  console.log('截图与日志：' + out);
  fs.writeFileSync(path.join(out, 'play-done.png'), Buffer.from((await page.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
})().catch(e => { console.error(e.stack); process.exitCode = 1; }).finally(async () => {
  if (page) page.ws.close();
  if (chrome) chrome.kill();
  await new Promise(resolve => server.close(resolve));
});