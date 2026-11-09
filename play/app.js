/* 孩子端：系统按教材顺序自动派题，四屏状态机。不显示诊断术语，无倒计时、无扣分。
 * 判定与难度阶梯全在 diagnose/engine.js（不改）；这里只管取片驱动、屏幕与本机存储。 */
(function () {
  'use strict';
  var E = window.DiagEngine, CC = window.CnmChildren, D = window.CnmPlayDispatch, S = window.CnmPlaySession;
  var PD = window.CnmPlayData.create({ base: '../data/bank/' });
  var root = document.getElementById('root');
  var LABEL = { math: '数学', chinese: '语文', english: '英语', physics: '物理', science: '科学', morality: '道德与法治', history: '历史', geography: '地理' };
  var SUBJECT_KEY = 'cnmPlay.subject.v1';
  var st = { childId: null, subject: 'math', cfg: null, topicIds: [], ctx: null, busy: false, timer: null, storageOk: true };

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function lsGet(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function seenKey(id) { return 'cnmPlay.seen.v1.' + id; }
  function seenList(id) { var v = lsGet(seenKey(id)); return Array.isArray(v) ? v : []; }
  function markSeen(id, qid) { if (!qid || !id) return; var v = seenList(id); if (v.indexOf(qid) < 0) { v.push(qid); lsSet(seenKey(id), v); } }
  function skipKey(id, s) { return 'cnmPlay.skipped.v1.' + id + '.' + s; }
  function skippedList(id, s) { var v = lsGet(skipKey(id, s)); return Array.isArray(v) ? v : []; }
  function addSkipped(id, s, tid) {
    if (!id || !tid) return;
    var v = skippedList(id, s);
    if (v.indexOf(tid) < 0) { v.push(tid); lsSet(skipKey(id, s), v); }
  }
  function probeStorage() {
    try { localStorage.setItem('cnmPlay.probe', '1'); localStorage.removeItem('cnmPlay.probe'); return true; }
    catch (e) { return false; }
  }
  function newSeed() { return Math.random().toString(36).slice(2, 10); }
  function show(node) {
    if (st.timer) { clearTimeout(st.timer); st.timer = null; }
    while (root.firstChild) root.removeChild(root.firstChild);
    root.appendChild(node);
    window.scrollTo(0, 0);
  }
  function editionLabel() {
    var hit = PD.editionsFor(st.subject).filter(function (x) { return x.id === st.cfg.edition; })[0];
    return hit ? hit.label : st.cfg.edition;
  }
  function renderLoading() { show(el('p', 'play-loading', '正在准备题目…')); }
  function renderError(msg, retry) {
    var box = el('div', 'play-card');
    box.appendChild(el('p', 'play-error', msg));
    var b = el('button', 'play-go', '重试'); b.type = 'button';
    b.addEventListener('click', retry);
    box.appendChild(b);
    show(box);
  }
  function setupCard(box, title, text) {
    var card = el('div', 'play-card');
    card.appendChild(el('h1', null, title));
    card.appendChild(el('p', 'play-sub', text));
    var a = el('a', 'play-go', '请家长去设置');
    a.href = '../children/?from=play&subject=' + encodeURIComponent(st.subject);
    card.appendChild(a);
    box.appendChild(card);
  }
  function childSwitcher() {
    var row = el('div', 'play-row');
    row.appendChild(el('label', null, '我是'));
    var sel = el('select'); sel.id = 'play-child'; sel.setAttribute('aria-label', '选择孩子');
    CC.list().forEach(function (c) { var o = el('option', null, c.name); o.value = c.id; sel.appendChild(o); });
    sel.value = st.childId || '';
    sel.addEventListener('change', function () { CC.setCurrent(sel.value); boot(); });
    row.appendChild(sel);
    return row;
  }
  function subjectTabs() {
    var row = el('div', 'play-subjects');
    CC.SUBJECTS.forEach(function (s) {
      var b = el('button', 'play-subject' + (s === st.subject ? ' is-on' : ''), LABEL[s]);
      b.type = 'button';
      b.addEventListener('click', function () { st.subject = s; lsSet(SUBJECT_KEY, s); renderHome(); });
      row.appendChild(b);
    });
    return row;
  }
  function progressBar(p) {
    var wrap = el('div', 'play-progress');
    var bar = el('div', 'play-progress-bar');
    var fill = el('div', 'play-progress-fill');
    fill.style.width = Math.round(p.ratio * 100) + '%';
    bar.appendChild(fill); wrap.appendChild(bar);
    wrap.appendChild(el('p', 'play-progress-text', p.total ? '这册已经学会 ' + p.mastered + ' / ' + p.total + ' 个知识点' : '这册还没有知识点'));
    return wrap;
  }
  function targetCells() {
    var row = el('div', 'play-cells');
    st.ctx.session.targets.forEach(function (id) {
      var s = E.statusOf(st.ctx.session, id);
      var ok = s === 'mastered', again = s === 'weak' || s === 'shaky';
      row.appendChild(el('span', 'play-cell' + (ok ? ' is-ok' : again ? ' is-again' : ''), ok ? '✓' : again ? '!' : ''));
    });
    return row;
  }
  function parentNote() {
    var d = el('details', 'play-note');
    d.appendChild(el('summary', null, '家长说明'));
    d.appendChild(el('p', null, '练过的题记在这台设备的浏览器里，不上传、没有账号。清除浏览器数据或换设备后会重新开始；同一台设备上两个孩子各自独立，互不消耗对方的题。'));
    d.appendChild(el('p', null, '想调整教材版本、册次或「连续答对几道算学会」，去档案页改。'));
    var a = el('a', null, '打开档案设置');
    a.href = '../children/?from=play&subject=' + encodeURIComponent(st.subject);
    d.appendChild(a);
    return d;
  }
  function volumeEnd(wrap) {
    var next = D.nextVolume(PD.editionVolumes(st.cfg.edition, st.subject), st.cfg.volume);
    wrap.appendChild(el('p', 'play-cheer', next ? '这册学完了！' : '这一科学完了！'));
    var b = el('button', 'play-go', next ? '继续下一册（' + next + '）' : '请家长做一次综合复查');
    b.type = 'button';
    b.addEventListener('click', function () {
      if (next) { CC.setVolume(st.childId, st.subject, next); renderHome(); }
      else location.href = '../diagnose/?subject=' + encodeURIComponent(st.subject);
    });
    wrap.appendChild(b);
  }

  /* 跳过：引擎没有「摘掉一个目标」的接口，手改 session 会破坏 replay 确定性（plan D10）。
   * 所以记入本册末尾队列 → 把已作答部分写进记录（被跳过的点没作答，不进任何列表）→ 回首页。
   * 其余目标仍是 unknown，下次派题按教材顺序自然还在队列里，没有问题被丢掉。 */
  function skipTopic() {
    if (st.busy || !st.ctx || !st.ctx.item) return;
    addSkipped(st.childId, st.subject, st.ctx.item.topicId);
    saveProgress();
    st.ctx = null;
    renderHome();
  }

  async function renderHome() {
    var child = CC.current();
    st.childId = child ? child.id : null;
    var box = el('div', 'play-home');
    if (!child) { setupCard(box, '还没有孩子档案', '请家长先建一份档案，选好教材再开始。'); show(box); return; }
    box.appendChild(childSwitcher());
    box.appendChild(subjectTabs());
    if (!st.storageOk) {
      box.appendChild(el('p', 'play-warn', '这个浏览器不让保存数据（可能是隐私模式）。这次练习里不会重复出题，但关掉页面后练过哪些题就记不住了，请家长用普通窗口打开。'));
    }
    st.cfg = (child.subjects || {})[st.subject] || null;
    if (!st.cfg) {
      setupCard(box, '请家长先设置教材', '告诉爸爸妈妈：在档案里选好「' + LABEL[st.subject] + '」的教材版本、册次和确认题数。');
      show(box); return;
    }
    var wrap = el('div', 'play-card');
    wrap.appendChild(el('p', 'play-loading', '正在准备题目…'));
    box.appendChild(wrap);
    show(box);
    try {
      await PD.loadGraph(st.subject);
      st.topicIds = await PD.loadOrder(st.cfg.edition, st.subject);
    } catch (e) { renderError('加载失败，请检查网络', renderHome); return; }
    var status = CC.latestStatus(child.id, st.subject);
    var prog = D.volumeProgress({ topicIds: st.topicIds, volumeOf: PD.volumeOf, volume: st.cfg.volume, status: status });
    var pick = D.pickTargets({ topicIds: st.topicIds, volumeOf: PD.volumeOf, volume: st.cfg.volume, status: status, skipped: skippedList(child.id, st.subject), count: D.TARGET_COUNT });
    wrap.textContent = '';
    wrap.appendChild(el('h1', 'play-title', child.name + '，今天练 ' + D.TARGET_COUNT + ' 个知识点'));
    wrap.appendChild(el('p', 'play-sub', LABEL[st.subject] + ' · ' + editionLabel() + ' · ' + st.cfg.volume));
    wrap.appendChild(progressBar(prog));
    if (pick.exhausted) { volumeEnd(wrap); box.appendChild(parentNote()); return; }
    var go = el('button', 'play-go', '开始'); go.type = 'button';
    go.addEventListener('click', function () { start(pick.targets); });
    wrap.appendChild(go);
    box.appendChild(parentNote());
  }

  async function start(targets) {
    if (st.busy) return;
    st.busy = true;
    renderLoading();
    try {
      await PD.loadGraph(st.subject);
      st.ctx = S.create({ data: PD, subject: st.subject, types: ['choice', 'numeric'], seed: newSeed(), confirm: st.cfg.confirm, limit: D.limitFor(st.cfg.confirm), avoid: seenList(st.childId) });
      await S.open(st.ctx, targets);
      st.busy = false;
      if (!st.ctx.item) { renderDone(); return; }
      renderAsk();
    } catch (e) { st.busy = false; renderError('加载失败，请检查网络', function () { start(targets); }); }
  }

  function renderAsk() {
    var item = st.ctx.item, q = item.question;
    var box = el('div', 'play-ask');
    box.appendChild(targetCells());
    box.appendChild(el('p', 'play-topic', st.ctx.graph.byId[item.topicId].name));
    var card = el('div', 'play-card');
    card.appendChild(el('p', 'play-prompt', q.prompt));
    var fig = window.CnmFigure.el(q.figure, 'play-figure');
    if (fig) card.appendChild(fig);
    var input = null;
    if (q.type === 'choice') {
      var list = el('div', 'play-choices' + (q.hideChoiceText ? ' is-icons' : ''));
      (q.choices || []).forEach(function (c) {
        var b = el('button', 'play-choice'); b.type = 'button';
        var hide = !!(q.hideChoiceText && c.figure);
        b.appendChild(el('b', 'play-choice-key', hide ? c.key : (c.key + '.')));
        if (!hide) b.appendChild(document.createTextNode(' ' + c.text));
        var cf = c.figure ? window.CnmFigure.el(c.figure, 'play-figure') : null;
        if (cf) b.appendChild(cf);
        if (hide) b.setAttribute('aria-label', '选项 ' + c.key);
        b.addEventListener('click', function () { judge(q, c.key); });
        list.appendChild(b);
      });
      card.appendChild(list);
    } else {
      input = el('input', 'play-answer'); input.type = 'text'; input.id = 'play-answer';
      input.autocomplete = 'off'; input.placeholder = '在这里写答案'; input.setAttribute('aria-label', '答案');
      var submit = el('button', 'play-go', '提交'); submit.type = 'button';
      submit.addEventListener('click', function () { judge(q, input.value.trim()); });
      input.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.isComposing) judge(q, input.value.trim()); });
      card.appendChild(input); card.appendChild(submit);
    }
    box.appendChild(card);
    var skip = el('button', 'play-skip', '先跳过'); skip.type = 'button';
    skip.addEventListener('click', skipTopic);
    box.appendChild(skip);
    show(box);
    if (input) input.focus();
  }

  function judge(q, userText) {
    if (st.busy) return;
    if (!userText) { var n = document.getElementById('play-answer'); if (n) n.focus(); return; }
    renderFeedback(q, userText, E.judgeQuestion(q, userText).verdict);
  }
  function answerText(q) {
    if (q.type !== 'choice') return q.answer;
    var c = (q.choices || []).filter(function (x) { return x.key === q.answer; })[0];
    return q.answer + (c ? '. ' + c.text : '');
  }
  function renderFeedback(q, userText, verdict) {
    var ok = verdict === 'correct';
    var box = el('div', 'play-feedback');
    box.appendChild(targetCells());
    var card = el('div', 'play-card ' + (ok ? 'is-ok' : 'is-no'));
    card.appendChild(el('p', 'play-verdict', ok ? '✓ 答对了' : (verdict === 'manual' ? '这个写法电脑没看懂' : '✗ 再看一下')));
    if (!ok) {
      card.appendChild(el('p', 'play-your', (q.type === 'choice' ? '你选了：' : '你写了：') + userText));
      card.appendChild(el('p', 'play-answer-is', '正确答案：' + answerText(q)));
    }
    if (q.explanation) card.appendChild(el('p', 'play-explain', q.explanation));
    if (ok) card.appendChild(el('p', 'play-cheer', '真棒，继续！'));
    else {
      var b = el('button', 'play-go', '我懂了'); b.type = 'button';
      b.addEventListener('click', function () { commit(verdict === 'manual' ? 'skip' : 'wrong', userText); });
      card.appendChild(b);
    }
    box.appendChild(card);
    show(box);
    if (ok) st.timer = setTimeout(function () { st.timer = null; commit('correct', userText); }, 1000);
  }

  async function commit(result, text) {
    if (st.busy || !st.ctx || !st.ctx.item) return;
    st.busy = true;
    markSeen(st.childId, st.ctx.item.question.id);
    try {
      var item = await S.answer(st.ctx, result, text);
      st.busy = false;
      if (!item) { renderDone(); return; }
      renderAsk();
    } catch (e) { st.busy = false; renderError('加载失败，请检查网络', retryNext); }
  }
  async function retryNext() {
    renderLoading();
    try {
      var item = await S.next(st.ctx);
      if (!item) renderDone(); else renderAsk();
    } catch (e) { renderError('加载失败，请检查网络', retryNext); }
  }

  function saveProgress() {
    if (!st.ctx || !st.storageOk) return;
    var sum = S.summary(st.ctx);
    if (!sum.asked) return;
    CC.saveRecord(st.childId, D.buildRecord({ subject: st.subject, label: '同步练习 · ' + LABEL[st.subject] + ' ' + st.cfg.volume, session: st.ctx.session, summary: sum }));
  }
  function renderDone() {
    saveProgress();
    var sum = S.summary(st.ctx);
    var box = el('div', 'play-done');
    var card = el('div', 'play-card');
    card.appendChild(el('h1', null, '今天练完了'));
    var ul = el('ul', 'play-results');
    st.ctx.session.targets.forEach(function (id) {
      var learned = sum.mastered.indexOf(id) >= 0;
      var li = el('li', learned ? 'is-ok' : 'is-again');
      li.appendChild(el('span', 'play-result-name', st.ctx.graph.byId[id].name));
      li.appendChild(el('span', 'play-result-tag', learned ? '学会' : '还要练'));
      ul.appendChild(li);
    });
    card.appendChild(ul);
    if (sum.limitReached) card.appendChild(el('p', 'play-sub', '今天练完了，剩下的明天继续。'));
    card.appendChild(progressBar(D.volumeProgress({ topicIds: st.topicIds, volumeOf: PD.volumeOf, volume: st.cfg.volume, status: CC.latestStatus(st.childId, st.subject) })));
    var b = el('button', 'play-go', '明天再来'); b.type = 'button';
    b.addEventListener('click', function () { st.ctx = null; renderHome(); });
    card.appendChild(b);
    box.appendChild(card);
    show(box);
  }

  async function boot() {
    renderLoading();
    st.storageOk = probeStorage();
    try { await PD.loadManifest(); }
    catch (e) { renderError('加载失败，请检查网络', boot); return; }
    var cur = CC.current();
    st.childId = cur ? cur.id : null;
    var s = new URLSearchParams(location.search).get('subject') || lsGet(SUBJECT_KEY) || 'math';
    st.subject = CC.SUBJECTS.indexOf(s) >= 0 ? s : 'math';
    renderHome();
  }

  window.__play = { state: st, data: PD, boot: boot, start: start, commit: commit, retryNext: retryNext, renderHome: renderHome, skipTopic: skipTopic };
  boot();
})();