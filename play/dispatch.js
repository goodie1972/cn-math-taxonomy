/* 孩子端派题：纯函数，无 DOM、无异步、无存储。
 * 顺序由版本×学科的 registry topicIds 决定（教材顺序），状态由 CnmChildren.latestStatus 决定。
 * 浏览器 window.CnmPlayDispatch，Node require() 即可。 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory();
  else root.CnmPlayDispatch = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var TARGET_COUNT = 5;

  function limitFor(confirm) { return TARGET_COUNT * (confirm + 2); }

  function st(status, id) {
    var v = status && status[id];
    return v ? v.status : 'unknown';
  }

  function pickTargets(o) {
    var skipped = o.skipped || [];
    var inVolume = o.topicIds.filter(function (id) { return o.volumeOf(id) === o.volume; });
    var notMastered = inVolume.filter(function (id) { return st(o.status, id) !== 'mastered'; });
    var fresh = notMastered.filter(function (id) { return skipped.indexOf(id) < 0; });
    var deferred = notMastered.filter(function (id) { return skipped.indexOf(id) >= 0; });
    var pool = fresh.length ? fresh : deferred;
    return {
      targets: pool.slice(0, o.count == null ? TARGET_COUNT : o.count),
      fresh: fresh, deferred: deferred, exhausted: pool.length === 0
    };
  }

  function volumeProgress(o) {
    var inVolume = o.topicIds.filter(function (id) { return o.volumeOf(id) === o.volume; });
    var mastered = inVolume.filter(function (id) { return st(o.status, id) === 'mastered'; }).length;
    return { total: inVolume.length, mastered: mastered, ratio: inVolume.length ? mastered / inVolume.length : 0 };
  }

  function nextVolume(volumes, current) {
    var i = volumes.indexOf(current);
    return i >= 0 && i + 1 < volumes.length ? volumes[i + 1] : null;
  }

  /* 与 diagnose/app.js 的 saveToChild 记录格式逐字段相同，档案页与历史页因此无需分支。 */
  function buildRecord(o) {
    var sum = o.summary, s = o.session;
    return {
      key: [o.subject, s.seed, s.targets.join(',')].join('|'),
      subject: o.subject, label: o.label, mode: sum.mode, asked: sum.asked,
      targets: sum.mode === 'screen' || sum.targets.length > 6 ? null : sum.targets,
      counts: { weak: sum.weak.length, shaky: sum.shaky.length, mastered: sum.mastered.length, untested: sum.untested.length },
      weak: sum.weak, roots: sum.roots.map(function (r) { return r.id; }), shaky: sum.shaky, mastered: sum.mastered
    };
  }

  return {
    TARGET_COUNT: TARGET_COUNT, limitFor: limitFor, pickTargets: pickTargets,
    volumeProgress: volumeProgress, nextVolume: nextVolume, buildRecord: buildRecord
  };
});