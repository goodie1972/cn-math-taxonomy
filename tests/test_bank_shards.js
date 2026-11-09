#!/usr/bin/env node
/* 分片完整性：node tests/test_bank_shards.js（只读磁盘产物，不重新构建）。 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const E = require('../diagnose/engine.js');
const ROOT = path.resolve(__dirname, '..');
const BANK = path.join(ROOT, 'data', 'bank');
let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { failed++; console.log('  FAIL ' + name + '\n       ' + (e && e.stack || e).split('\n').slice(0, 4).join('\n       ')); }
}
const readJson = rel => JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
const readBank = rel => fs.readFileSync(path.join(BANK, rel), 'utf8');
const topics = readJson('data/topics.json');
const deps = readJson('data/dependencies.json');
const questions = readJson('data/questions.json');
const registry = readJson('data/editions/registry.json');
const manifest = readJson('data/bank/manifest.json');
const subjects = Object.keys(manifest.subjects).sort();
// 35143 题 × 35143 次线性查找会让每次回归跑几分钟，用索引表保持断言不变。
const topicById = new Map(topics.map(t => [t.id, t]));
const questionById = new Map(questions.map(q => [q.id, q]));

test('buildId 是四个真源文件内容的 SHA-256 前 12 位', () => {
  const h = crypto.createHash('sha256');
  ['data/topics.json', 'data/dependencies.json', 'data/questions.json', 'data/editions/registry.json']
    .forEach(rel => h.update(fs.readFileSync(path.join(ROOT, rel))));
  assert.equal(manifest.buildId, h.digest('hex').slice(0, 12));
});

test('每个知识点恰好出现在一个骨架文件，骨架并集 == 真源 topics，学科与文件名一致', () => {
  const seen = new Map();
  subjects.forEach(s => {
    const g = JSON.parse(readBank(manifest.subjects[s].graphFile));
    assert.equal(g.topics.length, manifest.subjects[s].topics);
    g.topics.forEach(t => {
      assert.ok(!seen.has(t.id), '重复骨架点 ' + t.id);
      assert.equal(E.subjectOf(t), s, '学科归属不一致 ' + t.id);
      assert.deepStrictEqual(t, topicById.get(t.id), '骨架必须原文照抄 ' + t.id);
      seen.set(t.id, s);
    });
  });
  assert.deepStrictEqual(Array.from(seen.keys()).sort(), topics.map(t => t.id).sort());
});

test('骨架 deps 并集 == 真源 deps（多重集相等），且无跨学科边', () => {
  const got = [];
  subjects.forEach(s => {
    const g = JSON.parse(readBank(manifest.subjects[s].graphFile));
    const allow = new Set(g.topics.map(t => t.id));
    g.deps.forEach(d => {
      assert.ok(allow.has(d.topicId) && allow.has(d.prerequisiteId), '跨学科边 ' + JSON.stringify(d));
      got.push(JSON.stringify(d));
    });
  });
  const ids = new Set(topics.map(t => t.id));
  const want = deps.filter(d => ids.has(d.topicId) && ids.has(d.prerequisiteId)).map(d => JSON.stringify(d));
  assert.deepStrictEqual(got.sort(), want.sort());
});

test('每道题恰好出现在一个分片，分片并集 == 真源题库，且落在正确的册', () => {
  const seen = new Map();
  let total = 0;
  subjects.forEach(s => {
    manifest.subjects[s].volumes.forEach(v => {
      const shard = manifest.subjects[s].shards[v];
      const body = readBank(shard.file);
      const qs = JSON.parse(body).questions;
      assert.ok(!body.includes('\n'), '分片必须单行 compact：' + shard.file);
      assert.equal(Buffer.byteLength(body, 'utf8'), shard.bytes);
      assert.equal(qs.length, shard.questions);
      total += qs.length;
      qs.forEach(q => {
        assert.ok(!seen.has(q.id), '重复题 ' + q.id);
        assert.equal(manifest.topicVolume[q.topicId], v, '题挂错册 ' + q.id);
        assert.deepEqual(q, questionById.get(q.id), '分片必须原文照抄 ' + q.id);
        seen.set(q.id, v);
      });
    });
  });
  assert.equal(total, questions.length);
  assert.deepStrictEqual(Array.from(seen.keys()).sort(), questions.map(q => q.id).sort());
});

test('每个知识点至少 1 道 choice/numeric（孩子端不会遇到无可出题的点）', () => {
  const ok = new Set();
  subjects.forEach(s => manifest.subjects[s].volumes.forEach(v => {
    JSON.parse(readBank(manifest.subjects[s].shards[v].file)).questions.forEach(q => {
      if (q.type === 'choice' || q.type === 'numeric') ok.add(q.topicId);
    });
  }));
  const missing = topics.filter(t => !ok.has(t.id)).map(t => t.id);
  assert.deepStrictEqual(missing, []);
});

test('manifest 的 topics 计量与骨架一致，册集合无重复无遗漏', () => {
  subjects.forEach(s => {
    const vols = manifest.subjects[s].volumes;
    assert.equal(new Set(vols).size, vols.length, '册键重复 ' + s);
    assert.deepStrictEqual(vols.slice().sort(), Object.keys(manifest.subjects[s].shards).sort());
    const fromTopics = [];
    topics.filter(t => E.subjectOf(t) === s).forEach(t => {
      const v = manifest.topicVolume[t.id];
      if (!fromTopics.includes(v)) fromTopics.push(v);
    });
    assert.deepStrictEqual(vols, fromTopics, '学科册顺序必须是 topics.json 首次出现顺序 ' + s);
    assert.equal(manifest.subjects[s].topics, topics.filter(t => E.subjectOf(t) === s).length);
  });
  assert.equal(subjects.reduce((n, s) => n + manifest.subjects[s].volumes.length, 0), 117);
});

test('版本册顺序 == registry topicIds 中册键的首次出现顺序，顺序表原文照抄 registry', () => {
  let pairs = 0;
  registry.versions.forEach(ed => {
    const m = manifest.editions[ed.id];
    assert.equal(m.label, ed.label);
    Object.keys(ed.subjects).forEach(s => {
      pairs++;
      const want = [];
      ed.subjects[s].topicIds.forEach(id => {
        assert.ok(Object.prototype.hasOwnProperty.call(manifest.topicVolume, id), 'registry 引用了未知点 ' + id);
        const v = manifest.topicVolume[id];
        if (!want.includes(v)) want.push(v);
      });
      assert.deepStrictEqual(m.subjects[s].volumes, want, ed.id + '/' + s);
      assert.equal(m.subjects[s].topics, ed.subjects[s].topicIds.length);
      assert.equal(m.subjects[s].label, ed.subjects[s].label);
      assert.deepStrictEqual(JSON.parse(readBank(m.subjects[s].orderFile)).topicIds, ed.subjects[s].topicIds);
    });
  });
  assert.equal(pairs, 99);
});

test('磁盘文件集合 == manifest 声明的集合（无陈旧分片）', () => {
  const want = new Set(['manifest.json']);
  subjects.forEach(s => {
    want.add(manifest.subjects[s].graphFile);
    manifest.subjects[s].volumes.forEach(v => want.add(manifest.subjects[s].shards[v].file));
  });
  Object.keys(manifest.editions).forEach(e => Object.keys(manifest.editions[e].subjects).forEach(s => {
    want.add(manifest.editions[e].subjects[s].orderFile);
  }));
  const got = new Set();
  (function walk(dir) {
    fs.readdirSync(dir, { withFileTypes: true }).forEach(ent => {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) walk(full);
      else got.add(path.relative(BANK, full).split(path.sep).join('/'));
    });
  })(BANK);
  assert.deepStrictEqual(Array.from(got).sort(), Array.from(want).sort());
  assert.equal(want.size, 225);
});

console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);