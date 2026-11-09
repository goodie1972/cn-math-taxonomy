#!/usr/bin/env node
/* 孩子端派题与会话：node tests/test_play.js（无依赖、无 DOM、无网络）。 */
'use strict';
const assert = require('assert');
const E = require('../diagnose/engine.js');
const D = require('../play/dispatch.js');
const S = require('../play/session.js');
let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + (e && e.stack || e).split('\n').slice(0, 4).join('\n       ')); }
}
const status = map => Object.fromEntries(Object.entries(map).map(([k, v]) => [k, { status: v }]));
const ids = ['t1', 't2', 't3', 't4', 't5', 't6', 't7'];
const volumeOf = id => (id === 't6' || id === 't7') ? '三下' : '三上';
const pick = (over) => D.pickTargets(Object.assign({
  topicIds: ids, volumeOf, volume: '三上', status: {}, skipped: [], count: D.TARGET_COUNT
}, over || {}));

test('派题保持教材顺序，只取本册前 5 个', () => {
  const r = pick();
  assert.deepEqual(r.targets, ['t1', 't2', 't3', 't4', 't5']);
  assert.deepEqual(r.fresh, ['t1', 't2', 't3', 't4', 't5']);
  assert.deepEqual(r.deferred, []);
  assert.equal(r.exhausted, false);
});

test('mastered 被跳过，weak / shaky 不跳过', () => {
  const r = pick({ status: status({ t1: 'mastered', t2: 'weak', t3: 'shaky' }) });
  assert.deepEqual(r.targets, ['t2', 't3', 't4', 't5']);
});

test('topicIds 顺序就是派题顺序，不按 id 排序', () => {
  const r = D.pickTargets({ topicIds: ['t5', 't3', 't1', 't4', 't2'], volumeOf, volume: '三上', status: {}, skipped: [], count: 3 });
  assert.deepEqual(r.targets, ['t5', 't3', 't1']);
});

test('跳过的点排到本册末尾：未跳过的取尽后才放回，且仍按教材顺序', () => {
  const r = pick({ status: status({ t1: 'mastered' }), skipped: ['t2', 't4'] });
  assert.deepEqual(r.fresh, ['t3', 't5']);
  assert.deepEqual(r.deferred, ['t2', 't4']);
  assert.deepEqual(r.targets, ['t3', 't5']);
  const r2 = pick({ status: status({ t1: 'mastered', t3: 'mastered', t5: 'mastered' }), skipped: ['t4', 't2'] });
  assert.deepEqual(r2.fresh, []);
  assert.deepEqual(r2.targets, ['t2', 't4'], '放回时必须按教材顺序，不是按跳过顺序');
  assert.equal(r2.exhausted, false);
});

test('本册全 mastered 或全部取尽 → exhausted', () => {
  assert.equal(pick({ status: status({ t1: 'mastered', t2: 'mastered', t3: 'mastered', t4: 'mastered', t5: 'mastered' }) }).exhausted, true);
  assert.equal(pick({ status: status({ t1: 'mastered', t3: 'mastered', t5: 'mastered' }), skipped: ['t2', 't4'] }).exhausted, false);
  const all = pick({ status: status({ t1: 'mastered', t2: 'mastered', t3: 'mastered', t4: 'mastered', t5: 'mastered' }), skipped: ['t2'] });
  assert.equal(all.exhausted, true, 'mastered 优先于 skipped：已掌握就不再放回');
  assert.deepEqual(all.targets, []);
});

test('count 与 limit 公式', () => {
  assert.equal(D.TARGET_COUNT, 5);
  assert.equal(D.limitFor(2), 20);
  assert.equal(D.limitFor(3), 25);
  assert.equal(D.limitFor(5), 35);
  assert.deepEqual(pick({ count: 2 }).targets, ['t1', 't2']);
});

test('册进度只数本册的点，ratio 在空册时为 0', () => {
  const p = D.volumeProgress({ topicIds: ids, volumeOf, volume: '三上', status: status({ t1: 'mastered', t2: 'weak', t6: 'mastered' }) });
  assert.deepEqual(p, { total: 5, mastered: 1, ratio: 0.2 });
  assert.deepEqual(D.volumeProgress({ topicIds: [], volumeOf, volume: '三上', status: {} }), { total: 0, mastered: 0, ratio: 0 });
});

test('nextVolume 按传入顺序取下一册，末册与未知册返回 null', () => {
  const vols = ['三上', '三下', '四上'];
  assert.equal(D.nextVolume(vols, '三上'), '三下');
  assert.equal(D.nextVolume(vols, '四上'), null);
  assert.equal(D.nextVolume(vols, '不存在'), null);
  assert.equal(D.nextVolume([], '三上'), null);
});

test('buildRecord 与家长诊断页记录格式逐字段一致', () => {
  const topics = [{ id: 'a', name: 'A', external: false, diagnostic_question: { question: 'a?', answer: '1' } },
                  { id: 'b', name: 'B', external: false, diagnostic_question: { question: 'b?', answer: '1' } }];
  const g = E.buildGraph(topics, [{ topicId: 'b', prerequisiteId: 'a', strength: 'hard' }], null);
  const s = E.createSession(g, ['b'], { limit: 25, confirm: 3, seed: 'seed-1' });
  const sum = E.summarize(g, s);
  const rec = D.buildRecord({ subject: 'math', label: '同步练习 · 数学 三上', session: s, summary: sum });
  assert.deepEqual(rec, {
    key: 'math|seed-1|b', subject: 'math', label: '同步练习 · 数学 三上', mode: 'target', asked: 0,
    targets: ['b'], counts: { weak: 0, shaky: 0, mastered: 0, untested: 2 },
    weak: [], roots: [], shaky: [], mastered: []
  });
  assert.equal(Object.prototype.hasOwnProperty.call(rec, 'savedAt'), false);
});

/* ---- 会话与懒加载：手造两册小图，题库用内存注入，不走磁盘 ---- */
function fakeData(volumesByTopic, questionsByVolume, topics, deps) {
  const loaded = new Set();
  const calls = [];
  const typesSeen = [];
  return {
    calls, loaded, typesSeen,
    volumeOf: id => volumesByTopic[id] || null,
    volumesOf: () => Array.from(new Set(Object.values(volumesByTopic))),
    loadGraph: async () => ({ topics, deps }),
    loadQuestions: async (subject, volume) => {
      calls.push(volume);
      if (!questionsByVolume[volume]) throw new Error('HTTP 404 ' + volume);
      loaded.add(volume);
      return questionsByVolume[volume];
    },
    buildGraphFor: (subject, vols, types) => {
      typesSeen.push(types);
      const qs = [];
      vols.forEach(v => (questionsByVolume[v] || []).forEach(q => {
        if (!types || types.indexOf(q.type) >= 0) qs.push(q);
      }));
      return E.buildGraph(topics, deps, qs);
    }
  };
}
function mkTopic(id, vol) {
  return { id, name: id, chapter: vol + ' 第一单元', external: false, diagnostic_question: { question: id + ' 的兜底题？', answer: '兜底答案' } };
}
function mkQ(id, tid, difficulty, type) {
  return { id, topicId: tid, difficulty, type: type || 'choice', prompt: id + ' 题干',
    choices: [{ key: 'A', text: '对' }, { key: 'B', text: '错' }], answer: 'A', explanation: id + ' 解析', verify: 'A' };
}
const topics5 = [mkTopic('a', '一上'), mkTopic('b', '一上'), mkTopic('c', '一下'), mkTopic('d', '二上'), mkTopic('onlyshort', '一上')];
const deps5 = [{ topicId: 'b', prerequisiteId: 'a', strength: 'hard' }, { topicId: 'c', prerequisiteId: 'b', strength: 'hard' }, { topicId: 'd', prerequisiteId: 'c', strength: 'hard' }];
const bank5 = {
  '一上': [mkQ('a_q11', 'a', 'standard'), mkQ('a_q12', 'a', 'challenge'), mkQ('a_q13', 'a', 'challenge'),
           mkQ('b_q11', 'b', 'standard'), mkQ('b_q12', 'b', 'basic'), mkQ('b_q13', 'b', 'challenge'),
           mkQ('onlyshort_q11', 'onlyshort', 'standard', 'short')],
  '一下': [mkQ('c_q11', 'c', 'standard'), mkQ('c_q12', 'c', 'basic'), mkQ('c_q13', 'c', 'challenge')],
  '二上': [mkQ('d_q11', 'd', 'standard'), mkQ('d_q12', 'd', 'basic'), mkQ('d_q13', 'd', 'challenge')]
};
const opts5 = { subject: 'math', types: ['choice', 'numeric'], seed: 's1', confirm: 3, limit: 25, avoid: [] };

async function atest(name, fn) {
  try { await fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + (e && e.stack || e).split('\n').slice(0, 4).join('\n       ')); }
}

(async () => {
  await atest('open 只取目标所在册，同册 5 点全对只取 1 片', async () => {
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank5, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5));
    await S.open(ctx, ['a', 'b']);
    assert.deepEqual(data.calls, ['一上']);
    assert.ok(ctx.item);
    assert.notEqual(ctx.item.question.type, 'legacy');
    assert.deepEqual(Array.from(data.typesSeen[data.typesSeen.length - 1]), ['choice', 'numeric']);
  });

  await atest('答错回溯到未加载册时先取该片再出题，绝不静默跳过、绝不派兜底题', async () => {
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank5, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5));
    await S.open(ctx, ['c']);
    assert.deepEqual(data.calls, ['一下'], '目标在一下，先只取一下');
    assert.equal(ctx.item.topicId, 'c');
    await S.answer(ctx, 'wrong', 'B');
    assert.equal(ctx.item.topicId, 'c', '第一次错先出确认题，还在同册');
    await S.answer(ctx, 'wrong', 'B');
    assert.deepEqual(data.calls, ['一下', '一上'], '确认题也错 → 回溯到 b，必须先取一上');
    assert.equal(ctx.item.topicId, 'b');
    assert.notEqual(ctx.item.question.type, 'legacy');
    assert.ok(ctx.item.question.prompt.includes('题干'));
    assert.ok(!ctx.item.question.prompt.includes('兜底'));
  });

  await atest('多册连续回溯不被轮次上限截断（D2）', async () => {
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank5, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5, { limit: 60 }));
    await S.open(ctx, ['d']);
    let guard = 0;
    while (ctx.item && guard++ < 60) await S.answer(ctx, 'wrong', 'B');
    assert.deepEqual(data.calls, ['二上', '一下', '一上'], '三册全部取到，没有截断');
    assert.equal(ctx.item, null);
    const sum = S.summary(ctx);
    assert.ok(sum.weak.length > 0);
  });

  await atest('懒加载前后 E.replay 重建的出题序列一致', async () => {
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank5, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5));
    await S.open(ctx, ['c']);
    const asked = [ctx.item.question.id];
    await S.answer(ctx, 'wrong', 'B'); asked.push(ctx.item.question.id);
    await S.answer(ctx, 'wrong', 'B'); asked.push(ctx.item.question.id);
    // 每次作答前引擎实际派出的题，即「作答前那一题」，与 recorded 的 qid 对应。
    const servedBeforeAnswer = asked.slice(0, ctx.session.answers.length);
    const recordedQids = ctx.session.answers.map(a => a.qid);
    assert.deepEqual(recordedQids, servedBeforeAnswer, '引擎对两次答错记录的确认题，必须等于会话实际经历的题');
    // replay / createSession 都必须吃完整的 ctx.opts（含 avoid），否则挑题会漂移。
    const rebuilt = E.replay(ctx.graph, ctx.session.targets, ctx.session.answers, ctx.opts);
    assert.deepEqual(rebuilt.answers, ctx.session.answers);
    assert.deepEqual(rebuilt.stack, ctx.session.stack);
    assert.deepEqual(rebuilt.status, ctx.session.status);
    // 重建后逐题重放作答，引擎重新记录的 qid 应与原会话一致 —— 这就是「出题序列可复现」。
    const replayed = [];
    let s2 = E.createSession(ctx.graph, ctx.session.targets, ctx.opts);
    for (let i = 0; i < ctx.session.answers.length; i++) {
      const cur = E.nextItem(ctx.graph, s2);
      if (cur) replayed.push(cur.question.id);
      const a = ctx.session.answers[i];
      s2 = E.applyAnswer(ctx.graph, s2, a.id, a.result, { text: a.text });
    }
    assert.deepEqual(replayed, servedBeforeAnswer, '重建后必须出同样的题');
  });

  await atest('已加载册里只有 short 的点：清空 bank 让引擎跳过，不派兜底题、不死循环', async () => {
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank5, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5));
    await S.open(ctx, ['onlyshort', 'a']);
    assert.ok(ctx.item);
    assert.notEqual(ctx.item.topicId, 'onlyshort');
    assert.ok(ctx.unaskable.has('onlyshort'));
    assert.equal(ctx.graph.bank.onlyshort.length, 0);
    assert.equal(E.isTestable(ctx.graph, 'onlyshort'), false);
  });

  await atest('avoid 让同一孩子 10 轮不重样（60 题/点 fixture）', async () => {
    const topics = [mkTopic('p', '一上')];
    const qs = [];
    for (let i = 11; i <= 70; i++) {
      qs.push(mkQ('p_q' + i, 'p', i <= 20 ? 'basic' : (i <= 30 ? 'standard' : 'challenge')));
    }
    const data = fakeData({ p: '一上' }, { '一上': qs }, topics, []);
    const seen = [];
    for (let round = 0; round < 10; round++) {
      const ctx = S.create(Object.assign({ data }, opts5, { confirm: 5, limit: 35, seed: 'round' + round, avoid: seen.slice() }));
      await S.open(ctx, ['p']);
      let guard = 0;
      while (ctx.item && guard++ < 40) {
        const qid = ctx.item.question.id;
        assert.ok(seen.indexOf(qid) < 0, '第 ' + (round + 1) + ' 轮重复出题 ' + qid);
        seen.push(qid);
        await S.answer(ctx, 'correct', 'A');
      }
      assert.equal(S.summary(ctx).mastered.includes('p'), true);
    }
    assert.equal(seen.length, 50, 'confirm=5 每轮 1 standard + 4 challenge，10 轮 50 题');
  });

  await atest('两个孩子的 seen 互不干扰（avoid 由调用方按 childId 传入）', async () => {
    const topics = [mkTopic('p', '一上')];
    const qs = [mkQ('p_q11', 'p', 'standard'), mkQ('p_q12', 'p', 'challenge'), mkQ('p_q13', 'p', 'challenge'), mkQ('p_q14', 'p', 'challenge')];
    const data = fakeData({ p: '一上' }, { '一上': qs }, topics, []);
    const seenA = [], seenB = [];
    for (const seen of [seenA, seenB]) {
      const ctx = S.create(Object.assign({ data }, opts5, { seed: 'same-seed', avoid: seen.slice() }));
      await S.open(ctx, ['p']);
      while (ctx.item) { seen.push(ctx.item.question.id); await S.answer(ctx, 'correct', 'A'); }
    }
    assert.deepEqual(seenA, seenB, '同 seed 同 avoid 起点 → 两个孩子互不消耗对方的题');
    assert.equal(seenA.length, 3);
  });

  await atest('limit 用尽时未判定点保持 unknown，下次仍在队列', async () => {
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank5, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5, { limit: 1 }));
    await S.open(ctx, ['a', 'b']);
    assert.ok(ctx.item);
    const after = await S.answer(ctx, 'correct', 'A');
    assert.equal(after, null);
    const sum = S.summary(ctx);
    assert.equal(sum.limitReached, true);
    assert.equal(sum.asked, 1);
    assert.equal(E.statusOf(ctx.session, 'b'), 'unknown');
    const D2 = require('../play/dispatch.js');
    const r = D2.pickTargets({ topicIds: ['a', 'b'], volumeOf: () => '一上', volume: '一上',
      status: { a: { status: 'mastered' } }, skipped: [], count: 5 });
    assert.deepEqual(r.targets, ['b']);
  });

  await atest('分片取失败时抛出，答案已记录、item 为 null，重试只调 next 不重复作答', async () => {
    // 目标 c 在 一下，两次答错沿先修边 b→a 回溯到 一上；bank 只给 一下，
    // 因此第二次 answer 触发对 一上 的取片，必然 404。
    const bank = { '一下': bank5['一下'] };
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5));
    await S.open(ctx, ['c']);
    await S.answer(ctx, 'wrong', 'B');
    await assert.rejects(() => S.answer(ctx, 'wrong', 'B'), /HTTP 404/);
    assert.equal(ctx.item, null);
    assert.equal(ctx.session.answers.length, 2);
    // 重试（next）时 一上 仍是 404，重试不得追加作答记录。
    await assert.rejects(() => S.next(ctx), /HTTP 404/);
    assert.equal(ctx.session.answers.length, 2, '重试不得追加作答');
  });

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();