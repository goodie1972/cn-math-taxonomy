#!/usr/bin/env node
/* 分片加载器：node tests/test_play_data.js（注入磁盘 fetch，不走网络）。 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const PD = require('../assets/play-data.js');
const E = require('../diagnose/engine.js');
const ROOT = path.resolve(__dirname, '..');
let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + (e && e.stack || e).split('\n').slice(0, 4).join('\n       ')); }
}
async function atest(name, fn) {
  try { await fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + (e && e.stack || e).split('\n').slice(0, 4).join('\n       ')); }
}
function disk(calls, missing) {
  return async function (url) {
    calls.push(url);
    const rel = url.split('?')[0];
    if (missing && missing.indexOf(rel) >= 0) throw new Error(url + ' → HTTP 404');
    return JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
  };
}
// manifest 里的 file 字段相对 data/bank/，所以 base 必须带上这一段，
// 注入的磁盘 fetch 才能用 path.join(ROOT, rel) 命中真实文件。
const make = (calls, missing) => PD.create({ base: 'data/bank/', fetchJson: disk(calls, missing) });

(async () => {
  await atest('manifest / 骨架 / 分片 / 顺序表各自只取一次，并发共享同一个请求', async () => {
    const calls = [];
    const d = make(calls);
    const [m1, m2] = await Promise.all([d.loadManifest(), d.loadManifest()]);
    assert.strictEqual(m1, m2);
    assert.deepEqual(m1, JSON.parse(fs.readFileSync(path.join(ROOT, 'data/bank/manifest.json'), 'utf8')));
    await Promise.all([d.loadGraph('math'), d.loadGraph('math')]);
    await Promise.all([d.loadQuestions('math', '三上'), d.loadQuestions('math', '三上')]);
    await d.loadOrder('cn_renjiao', 'math');
    await d.loadOrder('cn_renjiao', 'math');
    assert.equal(calls.length, 4);
    assert.equal(calls[0], 'data/bank/manifest.json');
    assert.ok(calls[1].startsWith('data/bank/graph/math.json?v='));
    assert.ok(calls[2].startsWith('data/bank/questions/math/三上.json?v='));
    assert.ok(calls[3].startsWith('data/bank/order/cn_renjiao/math.json?v='));
  });

  await atest('buildGraphFor 只放已加载册的题，并按 types 过滤；未加载册保留 legacy 哨兵', async () => {
    const d = make([]);
    await d.loadManifest();
    await d.loadGraph('math');
    await d.loadQuestions('math', '三上');
    const g = d.buildGraphFor('math', ['三上'], ['choice', 'numeric']);
    const loaded = Object.keys(g.bank).filter(id => d.volumeOf(id) === '三上');
    assert.ok(loaded.length > 0);
    loaded.forEach(id => {
      assert.ok(g.bank[id].length > 0);
      g.bank[id].forEach(q => assert.ok(q.type === 'choice' || q.type === 'numeric', '漏进非机判题 ' + q.id));
    });
    const unloaded = Object.keys(g.bank).filter(id => d.volumeOf(id) !== '三上' && !g.byId[id].external);
    assert.ok(unloaded.length > 0);
    unloaded.forEach(id => {
      assert.equal(g.bank[id].length, 1);
      assert.equal(g.bank[id][0].type, 'legacy', '未加载册必须是 legacy 哨兵，不能是空 bank');
      assert.equal(g.bank[id][0].id, id + '_q1');
    });
    assert.throws(() => d.buildGraphFor('math', ['三上', '三下'], ['choice', 'numeric']), /题库未加载/);
    assert.throws(() => d.buildGraphFor('chinese', [], null), /骨架未加载/);
  });

  await atest('types=null 不过滤题型（家长诊断页仍能用 short/self）', async () => {
    const d = make([]);
    await d.loadManifest();
    await d.loadGraph('chinese');
    const vols = d.volumesOf('chinese');
    for (const v of vols) await d.loadQuestions('chinese', v);
    const g = d.buildGraphFor('chinese', vols, null);
    const types = new Set();
    Object.keys(g.bank).forEach(id => g.bank[id].forEach(q => types.add(q.type)));
    assert.ok(types.has('short'), '家长端必须保留 short');
    assert.ok(!types.has('legacy'), '全册加载后不应再有兜底题');
  });

  await atest('骨架索引与已加载册无关（replay 确定性的前提）', async () => {
    const d = make([]);
    await d.loadManifest();
    await d.loadGraph('math');
    await d.loadQuestions('math', '三上');
    const one = d.buildGraphFor('math', ['三上'], ['choice', 'numeric']);
    await d.loadQuestions('math', '三下');
    const two = d.buildGraphFor('math', ['三上', '三下'], ['choice', 'numeric']);
    assert.deepEqual(one.index, two.index);
    assert.deepEqual(one.prereqs, two.prereqs);
    const reversed = d.buildGraphFor('math', ['三下', '三上'], ['choice', 'numeric']);
    assert.deepEqual(two.bank, reversed.bank, '册加载顺序不得影响 bank');
  });

  await atest('volumeOf / volumesOf / editionsFor / editionVolumes 与 manifest 和 registry 一致', async () => {
    const d = make([]);
    const m = await d.loadManifest();
    const registry = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/editions/registry.json'), 'utf8'));
    assert.equal(d.volumeOf('cnm_p001'), m.topicVolume['cnm_p001']);
    assert.equal(d.volumeOf('不存在的点'), null);
    assert.deepEqual(d.volumesOf('math'), m.subjects.math.volumes);
    const eds = d.editionsFor('math');
    assert.ok(eds.some(x => x.id === 'cn_renjiao' && x.label === '人教版'));
    eds.forEach(x => assert.ok(registry.versions.find(v => v.id === x.id).subjects.math));
    assert.deepEqual(d.editionVolumes('cn_renjiao', 'math'), m.editions.cn_renjiao.subjects.math.volumes);
    assert.deepEqual(d.editionVolumes('cn_renjiao', '不存在的学科'), []);
    assert.deepEqual(d.editionVolumes('不存在的版本', 'math'), []);
  });

  await atest('分片 404 与骨架 404 都抛出带 HTTP 状态的错误，不静默兜底', async () => {
    const d = make([], ['data/bank/questions/math/三上.json']);
    await d.loadManifest();
    await d.loadGraph('math');
    await assert.rejects(() => d.loadQuestions('math', '三上'), /HTTP 404/);
    const d2 = make([], ['data/bank/graph/math.json']);
    await d2.loadManifest();
    await assert.rejects(() => d2.loadGraph('math'), /HTTP 404/);
  });

  await atest('失败的请求不被缓存，重试会重新取', async () => {
    const calls = [];
    let fail = true;
    const d = PD.create({ base: 'data/bank/', fetchJson: async url => {
      calls.push(url);
      // 只让骨架失败：manifest 必须先成功，否则测不到「失败后重试」这条路径。
      if (fail && url.indexOf('graph/math.json') >= 0) throw new Error(url + ' → HTTP 500');
      return JSON.parse(fs.readFileSync(path.join(ROOT, url.split('?')[0]), 'utf8'));
    } });
    await d.loadManifest();
    await assert.rejects(() => d.loadGraph('math'), /HTTP 500/);
    fail = false;
    const g = await d.loadGraph('math');
    assert.ok(g.topics.length > 0);
    assert.equal(calls.filter(u => u.indexOf('data/bank/graph/math.json') === 0).length, 2);
  });

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();