/* 孩子端会话驱动：只管「取片 + 建图 + 重放」，判定与难度阶梯全交给不改的引擎。
 * 浏览器 window.CnmPlaySession，Node require() 即可。
 *
 * 懒加载钩子（plan D1/D2）：3504 个点全部有 diagnostic_question，E.buildGraph 会给
 * 未加载册的点塞一条 type:'legacy' 兜底题，isTestable 因此恒真。所以钩子必须拦
 * nextItem 的**返回值**，不能查 bank 是否非空。legacy 在这里是「该册还没取」的哨兵，
 * 绝不允许派给孩子。 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory(require('../diagnose/engine.js'));
  else root.CnmPlaySession = factory(root.DiagEngine);
})(typeof self !== 'undefined' ? self : this, function (E) {
  'use strict';

  function create(o) {
    return {
      data: o.data, subject: o.subject, types: o.types || null,
      opts: { limit: o.limit, confirm: o.confirm, seed: o.seed, avoid: (o.avoid || []).slice() },
      loaded: new Set(), unaskable: new Set(), graph: null, session: null, item: null
    };
  }

  function rebuild(ctx) {
    ctx.graph = ctx.data.buildGraphFor(ctx.subject, Array.from(ctx.loaded), ctx.types);
    // 新图会把兜底题带回来，重新清空已确认无可出题的点，保证循环单调推进。
    ctx.unaskable.forEach(function (id) { ctx.graph.bank[id] = []; });
  }

  async function next(ctx) {
    for (;;) {
      const item = E.nextItem(ctx.graph, ctx.session);
      if (!item) return null;
      if (item.question.type !== 'legacy') return item;
      const vol = ctx.data.volumeOf(item.topicId);
      if (vol && !ctx.loaded.has(vol)) {
        await ctx.data.loadQuestions(ctx.subject, vol);
        ctx.loaded.add(vol);
        rebuild(ctx);
        ctx.session = E.replay(ctx.graph, ctx.session.targets, ctx.session.answers, ctx.opts);
        continue;
      }
      // 该册已取却仍只有兜底题：题型过滤下这个点确实无可出题。
      // 清空 bank 让引擎自己跳过（isTestable 转 false），而不是把 diagnostic_question 派出去。
      ctx.unaskable.add(item.topicId);
      ctx.graph.bank[item.topicId] = [];
    }
  }

  async function open(ctx, targets) {
    await ctx.data.loadGraph(ctx.subject);
    const vols = [];
    targets.forEach(function (id) {
      const v = ctx.data.volumeOf(id);
      if (v && vols.indexOf(v) < 0) vols.push(v);
    });
    for (const v of vols) {
      await ctx.data.loadQuestions(ctx.subject, v);
      ctx.loaded.add(v);
    }
    rebuild(ctx);
    ctx.session = E.createSession(ctx.graph, targets, ctx.opts);
    ctx.item = await next(ctx);
    return ctx;
  }

  async function answer(ctx, result, text) {
    ctx.session = E.applyAnswer(ctx.graph, ctx.session, ctx.item.topicId, result, text == null ? undefined : { text: text });
    ctx.item = null;
    ctx.item = await next(ctx);
    return ctx.item;
  }

  function summary(ctx) { return E.summarize(ctx.graph, ctx.session); }

  return { create: create, open: open, next: next, answer: answer, summary: summary };
});