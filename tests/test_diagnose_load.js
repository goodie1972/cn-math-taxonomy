#!/usr/bin/env node
/* 诊断页 loadData 取片行为：node tests/test_diagnose_load.js（抽出函数体，注入磁盘 fetch）。 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const E = require('../diagnose/engine.js');
const PD = require('../assets/play-data.js');
const ROOT = path.resolve(__dirname, '..');
const src = fs.readFileSync(path.join(ROOT, 'diagnose/app.js'), 'utf8');
const start = src.indexOf('  async function loadData() {');
const end = src.indexOf('  function buildTree(topics) {');
assert.ok(start > 0 && end > start, 'loadData 定位失败——若 diagnose/app.js 结构变了，先更新这里的切片标记');
const body = src.slice(start, end);
let passed = 0, failed = 0;
async function test(name, fn) {
  try { await fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + (e && e.stack || e).split('\n').slice(0, 4).join('\n       ')); }
}
async function run(subject) {
  const calls = [];
  // PD.create 的 fetchJson 契约：返回**解析后的 JSON**（浏览器里是 r.json()）。
  // 所以这里直接读磁盘返回对象；loadData 里的裸 fetch 只用来取 standards/aliases/registry，
  // 返回 Response-like 供 r.json() 用——两条路径各归各。
  const pdFetch = async url => {
    calls.push(url);
    const rel = url.replace(/^\.\.\//, '').split('?')[0];
    const full = path.join(ROOT, rel);
    if (!fs.existsSync(full)) throw new Error(url + ' → HTTP 404');
    return JSON.parse(fs.readFileSync(full, 'utf8'));
  };
  const ctxFetch = async url => {
    const rel = url.replace(/^\.\.\//, '').split('?')[0];
    const full = path.join(ROOT, rel);
    if (!fs.existsSync(full)) return { ok: false, status: 404 };
    return { ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(full, 'utf8')) };
  };
  const ctx = {
    E, subject, D: null, editionSel: '', location: { search: '' }, URLSearchParams,
    CnmPlayData: {
      create(opts) { return PD.create(Object.assign({ fetchJson: pdFetch }, opts)); }
    },
    buildTree: () => ({}),
    fetch: ctxFetch,
    Promise, Set, Array, Object, JSON, Error, console
  };
  vm.createContext(ctx);
  vm.runInContext(body + '\nthis.__run = loadData;', ctx, { filename: 'diagnose/app.js loadData' });
  await ctx.__run();
  return { D: ctx.D, calls, editionSel: ctx.editionSel };
}
(async () => {
  await test('math：取骨架 + 全部册分片，不取整包 questions.json，graph 覆盖全部数学点', async () => {
    const { D, calls } = await run('math');
    assert.equal(calls.some(u => u.includes('data/questions.json')), false);
    assert.ok(calls.some(u => u.includes('data/bank/graph/math.json')));
    const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/bank/manifest.json'), 'utf8'));
    manifest.subjects.math.volumes.forEach(v => assert.ok(calls.some(u => u.includes('data/bank/questions/math/' + v + '.json')), '缺册 ' + v));
    assert.equal(D.topics.length, manifest.subjects.math.topics);
    assert.equal(D.graph.hasBank, true);
    const types = new Set();
    Object.keys(D.graph.bank).forEach(id => D.graph.bank[id].forEach(q => types.add(q.type)));
    assert.ok(types.has('short'), '家长端必须保留 short');
    assert.ok(!types.has('legacy'), '全册加载后不应有兜底题');
    assert.ok(D.stdById && Object.keys(D.stdById).length > 0);
    assert.ok(D.editions.versions.length === 51);
  });
  await test('chinese：整包 16.95 MB → 按学科分片，且 tree 仍按 parseChapter 分册', async () => {
    const { D, calls } = await run('chinese');
    assert.equal(calls.some(u => u.includes('data/questions.json')), false);
    const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/bank/manifest.json'), 'utf8'));
    assert.equal(D.topics.length, manifest.subjects.chinese.topics);
    assert.equal(D.graph.hasBank, true);
  });
  await test('english：全部分片各取一次，无重复请求', async () => {
    const { D, calls } = await run('english');
    const shardCalls = calls.filter(u => u.includes('data/bank/questions/english/'));
    assert.equal(new Set(shardCalls).size, shardCalls.length, '同一分片不重复请求');
    const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/bank/manifest.json'), 'utf8'));
    manifest.subjects.english.volumes.forEach(v => assert.ok(shardCalls.some(u => u.includes('data/bank/questions/english/' + v + '.json')), '缺册 ' + v));
    assert.equal(D.graph.hasBank, true);
  });
  await test('?edition= 仍被采纳，选择器逻辑不受影响', async () => {
    const pdFetch = async url => {
      const rel = url.replace(/^\.\.\//, '').split('?')[0];
      const full = path.join(ROOT, rel);
      if (!fs.existsSync(full)) throw new Error(url + ' → HTTP 404');
      return JSON.parse(fs.readFileSync(full, 'utf8'));
    };
    const ctxFetch = async url => {
      const full = path.join(ROOT, url.replace(/^\.\.\//, '').split('?')[0]);
      if (!fs.existsSync(full)) return { ok: false, status: 404 };
      return { ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(full, 'utf8')) };
    };
    const ctx = {
      E, subject: 'math', D: null, editionSel: '', location: { search: '?edition=cn_beishida' }, URLSearchParams,
      CnmPlayData: { create(opts) { return PD.create(Object.assign({ fetchJson: pdFetch }, opts)); } },
      buildTree: () => ({}), fetch: ctxFetch,
      Promise, Set, Array, Object, JSON, Error, console
    };
    vm.createContext(ctx);
    vm.runInContext(body + '\nthis.__run = loadData;', ctx);
    await ctx.__run();
    assert.equal(ctx.editionSel, 'cn_beishida');
  });
  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();