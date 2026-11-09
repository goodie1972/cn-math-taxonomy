#!/usr/bin/env node
/* 孩子端派题与会话：node tests/test_play.js（无依赖、无 DOM、无网络）。 */
'use strict';
const assert = require('assert');
const E = require('../diagnose/engine.js');
const D = require('../play/dispatch.js');
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

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);