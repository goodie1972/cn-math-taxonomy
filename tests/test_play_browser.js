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
  const homeBytes = hits.filter(h => h.bytes > 0).reduce((n, h) => n + h.bytes, 0);
  console.log('首屏（首页 → 点开始 → 第一题）传输字节：' + homeBytes + ' B = ' + (homeBytes / 1048576).toFixed(2) + ' MB');
  assert.ok(homeBytes < 3 * 1048576, '首屏必须 < 3 MB，实测 ' + homeBytes);

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

  // ---- 跳过：记入本册末尾、不改变该点状态、其余目标下次仍在队列 ----
  // 小满刚在黄金路径里把三上 5 点全掌握，切到一个「未练习」的孩子才有「未测」起点可跳。
  await page.eval(`(() => { const r = CnmChildren.add({ name: '小禾', grade: '五年级', textbook: '人教版', subjects: { math: { edition: 'cn_renjiao', volume: '五上', confirm: 5 } } }); if (!r.ok) throw new Error(r.error); })()`);
  await page.eval('CnmChildren.setCurrent(CnmChildren.list()[1].id)');
  await page.eval('__play.boot()');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-go")'), 'child2 home');
  await page.eval('document.querySelector(".play-go").click()');
  await until(() => page.eval('!!document.querySelector(".play-prompt")'), 'ask again');
  const skipId = await page.eval('__play.state.ctx.item.topicId');
  const before = await page.eval('JSON.stringify(CnmChildren.latestStatus(__play.state.childId, "math"))');
  await page.eval('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "先跳过").click()');
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'home after skip');
  assert.ok(await page.eval(`JSON.parse(localStorage.getItem('cnmPlay.skipped.v1.' + __play.state.childId + '.math')).includes(${JSON.stringify(skipId)})`));
  const after = await page.eval('JSON.stringify(CnmChildren.latestStatus(__play.state.childId, "math"))');
  assert.equal(JSON.parse(after)[skipId], undefined, '跳过不改变该点状态');
  assert.equal(JSON.parse(before)[skipId], undefined, '跳过的点从未被作答，之前也是未测');
  const targetsNow = await page.eval(`(() => {
    const st = __play.state;
    const skipped = JSON.parse(localStorage.getItem('cnmPlay.skipped.v1.' + st.childId + '.math')) || [];
    return CnmPlayDispatch.pickTargets({ topicIds: st.topicIds, volumeOf: __play.data.volumeOf, volume: st.cfg.volume,
      status: CnmChildren.latestStatus(st.childId, 'math'), skipped: skipped, count: 5 }).targets;
  })()`);
  assert.equal(targetsNow.indexOf(skipId), -1, '跳过的点不在本次派题里');
  // 切回小满给后面的册末/404 场景用
  await page.eval('CnmChildren.setCurrent(CnmChildren.list()[0].id)');
  await page.eval('__play.boot()');
  await playReady();

  // ---- 切换孩子：seen / skipped / 档案全部按新 childId 读 ----
  await page.eval('CnmChildren.setCurrent(CnmChildren.list()[1].id)');
  await page.eval('__play.boot()');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'second child home');
  assert.ok(await page.eval('document.querySelector(".play-title").textContent.includes("小禾")'));
  assert.ok(await page.eval('document.querySelector(".play-sub").textContent.includes("五上")'));
  assert.notEqual(await page.eval('__play.state.childId'), await page.eval('CnmChildren.list()[0].id'));
  assert.equal(await page.eval(`localStorage.getItem('cnmPlay.seen.v1.' + __play.state.childId)`), null, '第二个孩子没消耗第一个孩子的题');
  await page.eval('document.getElementById("play-child").value = CnmChildren.list()[0].id; document.getElementById("play-child").dispatchEvent(new Event("change"))');
  await playReady();
  await until(() => page.eval('document.querySelector(".play-title").textContent.includes("小满")'), 'switch back');

  // ---- 学科未设置：出「请家长先设置教材」卡片，不进入答题 ----
  await page.eval('Array.from(document.querySelectorAll(".play-subject")).find(b => b.textContent === "物理").click()');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-card h1")'), 'setup card');
  assert.ok(await page.eval('document.querySelector(".play-card h1").textContent.includes("请家长先设置教材")'));
  // a.play-go 的 href 是相对路径 ../children/...，浏览器解析成绝对 URL；按 pathname/search 断言，不依赖 host。
  const physQuery = await page.eval('Array.from(document.querySelectorAll("a.play-go")).map(a => new URL(a.href)).map(u => u.pathname + u.search).join("|")');
  assert.ok(physQuery.split('|').some(p => p.indexOf('/children/') >= 0 && p.indexOf('from=play') >= 0 && p.indexOf('subject=physics') >= 0), '物理设置卡片应指向 children 设置页（from=play&subject=physics）');
  assert.equal(await page.eval('!!document.querySelector(".play-prompt")'), false);
  await page.eval('Array.from(document.querySelectorAll(".play-subject")).find(b => b.textContent === "数学").click()');
  await playReady();

  // ---- 隐私模式：存储抛错时首页给家长提示，仍能练 ----
  // 打 Storage.prototype（setItem 与 getItem 都拦），让 app.js 闭包里的 localStorage 走被替换的方法。
  // 先把原始方法存到本 realm 的 window（普通函数可被 CDP 安全回读），再换成全抛的 stub。
  // 关键：每个 eval 只返回原始值（布尔/字符串），绝不让 CDP 的 returnByValue 去序列化跨 realm 的
  // Storage 对象——那会报「Object reference chain is too long」。
  // ---- 隐私模式：存储被拒绝时，首页给家长提示，仍能进入练习 ----
  // probeStorage() 在 boot 时探测 localStorage 可写性；这里直接翻转 st.storageOk，
  // 等价模拟隐私模式（patch 真实 localStorage 会连带打破 CnmChildren，不隔离）。
  await page.eval(`(() => {
    CnmChildren.setCurrent(CnmChildren.list()[0].id);
    __play.state.subject = 'math';
    __play.state.storageOk = false;
    __play.renderHome();
    return 'ok';
  })()`);
  await until(() => page.eval('!!document.querySelector(".play-warn")'), 'privacy warning');
  assert.ok(await page.eval('document.querySelector(".play-warn").textContent.includes("隐私模式")'));
  // 恢复：storageOk 回到 true 并让首页回落到正常「开始」卡片
  await page.eval(`(() => { __play.state.storageOk = true; __play.renderHome(); return 'ok'; })()`);
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'home restored');

  // ---- 册末衔接：把本册全部点标成 mastered，首页应出「这册学完了」并能回写下一册 ----
  await page.eval(`(() => {
    const st = __play.state;
    const ids = st.topicIds.filter(id => __play.data.volumeOf(id) === st.cfg.volume);
    CnmChildren.saveRecord(st.childId, { key: 'math|fixture|all', subject: 'math', label: '测试整册掌握', mode: 'target', asked: ids.length,
      targets: null, counts: { weak: 0, shaky: 0, mastered: ids.length, untested: 0 }, weak: [], roots: [], shaky: [], mastered: ids });
  })()`);
  await page.eval('__play.renderHome()');
  await playReady();
  await until(() => page.eval('document.body.textContent.includes("这册学完了")'), 'volume end');
  const nextVol = await page.eval(`CnmPlayDispatch.nextVolume(__play.data.editionVolumes(__play.state.cfg.edition, __play.state.subject), __play.state.cfg.volume)`);
  assert.equal(nextVol, '三下');
  await page.eval('Array.from(document.querySelectorAll("button")).find(b => b.textContent.includes("继续下一册")).click()');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'next volume home');
  assert.equal(await page.eval('CnmChildren.current().subjects.math.volume'), '三下');
  assert.ok(await page.eval('document.querySelector(".play-sub").textContent.includes("三下")'));

  // ---- 最后一册：整册掌握后显示「这一科学完了」并链到家长诊断页 ----
  await page.eval(`(() => {
    const st = __play.state;
    const vols = __play.data.editionVolumes(st.cfg.edition, st.subject);
    const last = vols[vols.length - 1];
    CnmChildren.setVolume(st.childId, 'math', last);
    const ids = st.topicIds.filter(id => __play.data.volumeOf(id) === last);
    CnmChildren.saveRecord(st.childId, { key: 'math|fixture|last', subject: 'math', label: '测试末册掌握', mode: 'target', asked: ids.length,
      targets: null, counts: { weak: 0, shaky: 0, mastered: ids.length, untested: 0 }, weak: [], roots: [], shaky: [], mastered: ids });
  })()`);
  await page.eval('__play.renderHome()');
  await playReady();
  await until(() => page.eval('document.body.textContent.includes("这一科学完了")'), 'subject end');
  assert.ok(await page.eval('Array.from(document.querySelectorAll("button")).some(b => b.textContent.includes("综合复查"))'));
  assert.equal(await page.eval('document.body.textContent.includes("继续下一册")'), false);

  // ---- 分片 404：错误态 + 重试，绝不降级到 diagnostic_question ----
  await page.eval(`CnmChildren.setVolume(__play.state.childId, 'math', '三下')`);
  notFound.push('/data/bank/questions/math/三下.json');
  await page.eval('__play.renderHome()');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-go")'), 'home before 404');
  await page.eval('document.querySelector(".play-go").click()');
  await until(() => page.eval('!!document.querySelector(".play-error")'), 'shard 404 error');
  assert.ok(await page.eval('document.querySelector(".play-error").textContent.includes("加载失败")'));
  assert.equal(await page.eval('!!document.querySelector(".play-prompt")'), false, '绝不降级到 diagnostic_question');
  notFound.length = 0;
  await page.eval('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "重试").click()');
  await until(() => page.eval('!!document.querySelector(".play-prompt")'), 'retry after 404');
  assert.notEqual(await page.eval('__play.state.ctx.item.question.type'), 'legacy');

  // ---- 深浅色与桌面视口都不溢出 ----
  await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
  assert.ok(await page.eval('document.documentElement.scrollWidth <= innerWidth'));
  fs.writeFileSync(path.join(out, 'play-dark.png'), Buffer.from((await page.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
  await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  await page.send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  assert.ok(await page.eval('document.documentElement.scrollWidth <= innerWidth'));
  fs.writeFileSync(path.join(out, 'play-desktop.png'), Buffer.from((await page.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
  assert.deepEqual(errors, []);
  console.log('PASS: 跳过/切换孩子/学科未设置/隐私模式/册末衔接/最后一册/404 不降级/深浅色与桌面视口；无页面异常');
  console.log('截图与日志：' + out);
  fs.writeFileSync(path.join(out, 'play-done.png'), Buffer.from((await page.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
})().catch(e => { console.error(e.stack); process.exitCode = 1; }).finally(async () => {
  if (page) page.ws.close();
  if (chrome) chrome.kill();
  await new Promise(resolve => server.close(resolve));
});