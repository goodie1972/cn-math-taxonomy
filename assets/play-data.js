/* 分片加载器：骨架按学科整取，题库按册懒取，顺序表按版本×学科取。
 * 孩子端 /play/ 与家长诊断页共用。浏览器 window.CnmPlayData，Node require() 即可。
 * 引擎不改：未加载册的点在 E.buildGraph 里会拿到 type:'legacy' 的 diagnostic_question
 * 兜底题，本模块**故意保留**它当「未加载」哨兵，由 play/session.js 拦截后取片（见 plan D1）。 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory(require('../diagnose/engine.js'));
  else root.CnmPlayData = factory(root.DiagEngine);
})(typeof self !== 'undefined' ? self : this, function (E) {
  'use strict';

  function defaultFetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ' → HTTP ' + r.status);
      return r.json();
    });
  }

  function create(opts) {
    opts = opts || {};
    const base = opts.base == null ? '../data/bank/' : opts.base;
    const fetchJson = opts.fetchJson || defaultFetchJson;
    let manifest = null;
    const pending = Object.create(null);
    const graphs = Object.create(null);
    const banks = Object.create(null);
    const orders = Object.create(null);

    function once(key, url) {
      if (!pending[key]) {
        pending[key] = fetchJson(url).catch(function (e) { delete pending[key]; throw e; });
      }
      return pending[key];
    }
    function versioned(rel) { return base + rel + '?v=' + manifest.buildId; }

    function loadManifest() {
      if (manifest) return Promise.resolve(manifest);
      return once('manifest', base + 'manifest.json').then(function (m) { manifest = m; return m; });
    }
    function loadGraph(subject) {
      if (graphs[subject]) return Promise.resolve(graphs[subject]);
      return loadManifest().then(function (m) {
        const entry = m.subjects[subject];
        if (!entry) throw new Error('没有这个学科的分片：' + subject);
        return once('graph:' + subject, versioned(entry.graphFile));
      }).then(function (g) { graphs[subject] = g; return g; });
    }
    function loadQuestions(subject, volume) {
      const key = subject + '/' + volume;
      if (banks[key]) return Promise.resolve(banks[key]);
      return loadManifest().then(function (m) {
        const entry = m.subjects[subject];
        const shard = entry && entry.shards[volume];
        if (!shard) throw new Error('没有这个册的分片：' + key);
        return once('bank:' + key, versioned(shard.file));
      }).then(function (r) { banks[key] = r.questions; return banks[key]; });
    }
    function loadOrder(editionId, subject) {
      const key = editionId + '/' + subject;
      if (orders[key]) return Promise.resolve(orders[key]);
      return loadManifest().then(function (m) {
        const ed = m.editions[editionId];
        const entry = ed && ed.subjects[subject];
        if (!entry) throw new Error('这个版本没有挂载该学科：' + key);
        return once('order:' + key, versioned(entry.orderFile));
      }).then(function (r) { orders[key] = r.topicIds; return orders[key]; });
    }

    function buildGraphFor(subject, loadedVolumes, types) {
      const g = graphs[subject];
      if (!g) throw new Error('骨架未加载：' + subject);
      const allow = types ? new Set(types) : null;
      const qs = [];
      loadedVolumes.forEach(function (v) {
        const list = banks[subject + '/' + v];
        if (!list) throw new Error('题库未加载：' + subject + '/' + v);
        list.forEach(function (q) { if (!allow || allow.has(q.type)) qs.push(q); });
      });
      // topics 永远是整学科的全量，所以 graph.index 与先修排序不随已加载册变化，
      // E.replay 重建后的出题序列因此确定（tests/test_play_data.js 锁住这一点）。
      return E.buildGraph(g.topics, g.deps, qs);
    }

    function volumeOf(topicId) {
      return manifest && Object.prototype.hasOwnProperty.call(manifest.topicVolume, topicId)
        ? manifest.topicVolume[topicId] : null;
    }
    function volumesOf(subject) {
      const entry = manifest && manifest.subjects[subject];
      return entry ? entry.volumes.slice() : [];
    }
    function editionsFor(subject) {
      if (!manifest) return [];
      return Object.keys(manifest.editions).filter(function (id) {
        return !!manifest.editions[id].subjects[subject];
      }).map(function (id) { return { id: id, label: manifest.editions[id].label }; });
    }
    function editionVolumes(editionId, subject) {
      const ed = manifest && manifest.editions[editionId];
      const entry = ed && ed.subjects[subject];
      return entry ? entry.volumes.slice() : [];
    }

    return {
      loadManifest: loadManifest, loadGraph: loadGraph, loadQuestions: loadQuestions, loadOrder: loadOrder,
      buildGraphFor: buildGraphFor, volumeOf: volumeOf, volumesOf: volumesOf,
      editionsFor: editionsFor, editionVolumes: editionVolumes
    };
  }

  return { create: create };
});