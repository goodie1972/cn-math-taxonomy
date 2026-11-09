# 孩子端 /play/ 自动派题 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 用户长期约束「不要用子代理了，全部自己跑吧」——本计划**只用 inline 执行**，不派 subagent，不走 subagent-driven-development。

**Goal:** 给孩子一个独立的 `/play/` 入口：系统按教材顺序自动派 5 个知识点、只出 choice/numeric、四屏无术语，题库按学科×册懒加载，设备级 10 次不重样。

**Architecture:** 引擎 `diagnose/engine.js` 完全不改。真源三文件 + registry 由 `scripts/build_bank_shards.py` 构建成 `data/bank/`（8 个学科骨架 + 117 个册题库 + 99 个版本×学科顺序表 + manifest）。`assets/play-data.js` 负责取片与建图，`play/dispatch.js` 负责纯派题，`play/session.js` 负责异步懒加载驱动，`play/app.js` 只管四屏 DOM。家长诊断页 `loadData()` 换成同一套分片加载器，其余逻辑不动。

**Tech Stack:** 原生 ES2017 JS（UMD/IIFE，无框架、无 npm 依赖）、Python 3（构建与测量脚本）、Node 22+ `assert` 单测、裸 CDP over WebSocket + headless Chrome 浏览器测试、静态托管 + Service Worker。

**Spec:** [docs/superpowers/specs/2026-11-08-child-play-ui-design.md](../specs/2026-11-08-child-play-ui-design.md)

## Global Constraints

以下取值逐条抄自 spec，每个任务的要求都隐含包含本节。

- 引擎 `diagnose/engine.js` **完全不改**（spec §3）。难度阶梯、回溯、判定语义全部沿用。
- 孩子端只派 `type ∈ {choice, numeric}`（spec §5.1）。`short` / `self` 留在真源与家长诊断页。
- 每次 **5 个知识点**；`limit = 5 × (confirm + 2)`（confirm=3 → 25，confirm=5 → 35）（spec §5.1）。
- `confirm ∈ {2, 3, 5}`，默认 **3**（spec §4）。
- 派题跳过 `mastered`；`weak` / `shaky` **不跳过**（spec §5.1）。
- 册键 = `gen_registry.norm_vol(chapter 首段)`，取值 `一上`…`九下`、`九全`、`九年级全册`、`高一`、`高二`、`必修一`…`必修三`、`选必一`…`选必四`（spec §4、§6.1）。
- 分片 JSON：`separators=(',', ':')`、`ensure_ascii=False`、无缩进、LF、无尾换行（spec §6.1）。
- `data/topics.json`、`data/dependencies.json`、`data/questions.json`、`data/editions/registry.json` 是**唯一真源**，本计划只读不写。分片是构建产物，**进 git**（spec §3）。
- 不重样键 `cnmPlay.seen.v1.<childId>`，**设备级 localStorage**，与 `cnmDiagnose.seen.v1` **独立不合并**（spec §7）。
- 跳过键 `cnmPlay.skipped.v1.<childId>.<subject>`（spec §5.2）。
- 档案备份 `version` 升到 **2**，version **1** 仍可导入（spec §4）。现有 `textbook`（7 个粗值）保留不动。
- 触摸目标 **≥64px**；字号比诊断页大一号；沿用 `assets/site.css` 的 CSS 变量，不引入框架或新设计系统（spec §5.4）。
- 孩子端**不显示**「先修 / 不稳 / 置信度 / 拓扑」等术语；**无倒计时、无扣分**；**无 site-nav、无 top-banner、无搜索**（spec §5.4、§3）。
- `limit` 用尽仍有点未判定 → 显示「今天练完了，剩下的明天继续」，**不显示「未测」**（spec §5.5）。
- 分片 404 / 网络失败 → 「加载失败，请检查网络」+「重试」；**绝不静默降级到 `diagnostic_question`**（spec §8）。
- 明确不做：账号与云同步、gamification、倒计时压力、拍照批改、语音朗读、per-edition 题库（spec §11）。
- 不重跑 `scripts/gen_registry.py` / `scripts/apply_province_map.py`，不编码五四制年级偏移（用户既有裁定）。
- **每个任务只本地 commit，不 push。** push 必须单独向用户确认（用户长期约束「改文件可以，push 要确认」）。
- 回归闸门（每个任务收尾都要全绿）：`PYTHONIOENCODING=utf-8 STRICT_STANDARDS=1 python scripts/validate.py`、`python scripts/verify_questions.py`、`python scripts/version_gate.py`、`node tests/test_engine.js`、`node tests/test_children.js`、`node tests/test_children_browser.js`。

### 环境约束（Windows + Git Bash，实测）

- **每条 Bash 命令结束后 cwd 会重置**到 `C:\Users\Bobo\Documents\Qoder\2026-11-02\b86c1056`。每条命令都必须自己 `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && …`。
- Python 一律带 `PYTHONIOENCODING=utf-8`。**中文 stdout 会被 GBK 弄乱**：脚本把结果写进 `_scratch/*.txt`（UTF-8），再用 Read 工具看。`_scratch/` 已 gitignore。
- Chrome 实测在 `C:/Program Files/Google/Chrome/Application/chrome.exe`，`CHROME` 环境变量**未设置**。现有 `tests/test_children_browser.js` 的候选路径只有 mac/linux，在本机跑会直接抛「找不到 Chrome/Chromium」——Task 3 修掉。
- 仓库 `core.autocrlf` 已配置，git 会警告「LF will be replaced by CRLF」。**不要改 git config**，写文件时用 `newline='\n'` / Edit 工具保持 LF。

---

## 与 spec 的偏差与理由

spec 已获用户批准。下面 11 条（D1–D11）是**实现前实测发现的、spec 写不下去或会出错的地方**，每条都保住 spec 的原意。执行时按本节为准；若用户否决某条，回到 spec 原文并重新设计该处。

**D1 — 懒加载钩子改成拦截 `E.nextItem` 的返回值（spec §6.3 的钩子永不触发）。**
实测 3504 个知识点**全部**有 `diagnostic_question`。`E.buildGraph`（[diagnose/engine.js:64-69](../../../diagnose/engine.js#L64)）会给「bank 为空的点」塞一条 `type:'legacy'` 兜底题，于是 `isTestable`（[:133-136](../../../diagnose/engine.js#L133)）对未加载册的点**恒为真**。spec 的「if graph.bank[id] 非空 → 返回」永远命中，钩子一次都不会跑，而引擎会把 `diagnostic_question` 直接派给孩子——正是 §8 明令禁止的。
改为：**保留 legacy 兜底题当「未加载」哨兵**，拦截 `nextItem` 的结果，`question.type === 'legacy'` 就去取该册、重建图、`E.replay` 重放。反过来「建图时剥掉 legacy」也不行：`applyAnswer` 的先修压栈过滤 `isTestable`（[:319-321](../../../diagnose/engine.js#L319)），剥掉会让未加载册的先修被静默丢弃，回溯退化。

**D2 — 轮次上限改成单调推进保证，不用「最多 5 轮」（spec §6.3、§8）。**
实测整册先修闭包最多跨 **20 册**，5 轮上限会静默截断会话。改为：每轮循环**必须**让 `ctx.loaded`（已取册集合）或 `ctx.unaskable`（确认无可出题的点集合）之一增长，两者都只增不减且有限，因此必然终止，且不会截断合法回溯。重建图后重放 `ctx.unaskable` 里的清空动作，避免新图把兜底题带回来导致死循环。

**D3 — `volumeOf` 查 manifest 反查表，不用 `E.parseChapter`（spec §6.2 已如此写，此处锁定理由）。**
实测 `norm_vol` 与 `E.parseChapter().volume` 在 **142 个点**上分歧：english「九年级全册」29 点（parseChapter 给「九全」）、science「七上…九下」113 点（parseChapter 给「七年级上册…」）。单个 alias 补不齐。分片键一律 `norm_vol` 原文，客户端只查表，不解析章节。

**D4 — 家长诊断页加载当前学科的**全部册**，不按 `editionSel` / 年级范围挑册（spec §6.5 不可实现）。**
`loadData()` 在初始化时跑一次，那时选择器还没填充；实测选择器变化只调 `fill()`，**不重新加载数据**。按选择器挑册会让之后每一次切换都选到空图。改为加载当前学科全部册：整包 questions 16.95 MB → 按学科最大 **3.84 MB**（chinese），仍然大幅瘦身，且所有选择器、整章浏览、筛查模式一行不动。

**D5 — 文件与测试拆分比 spec §3 更细。**
`play/app.js` 拆成 `play/dispatch.js`（纯派题，无 DOM 无异步）+ `play/session.js`（异步懒加载驱动，无 DOM）+ `play/app.js`（只管四屏 DOM）。测试拆成 `tests/test_play_data.js`（加载器）+ `tests/test_play.js`（派题 + 会话）+ `tests/test_play_browser.js`（DOM 实测）。理由：spec §10 列的 12 条断言里 11 条不需要浏览器，混在 app.js 里就只能靠 CDP 测。

**D6 — 新增 `data/bank/order/<edition>/<subject>.json`（99 个），spec §6.1 的产物清单里没有。**
spec §5.1 第 2 步要 `registry.versions[edition].subjects[subject].topicIds` 的**原顺序**。实测把全部 33730 个 id 塞进 manifest 要 **366,613 字节**，每次孩子端启动都得背；registry.json 整包 compact 也有 467,745 字节。拆成 99 个顺序表后，一次启动只取当前配置那一个（最大约 10 KB）。产物总数 8 + 117 + 99 + 1 = **225** 个文件。

**D7 — `numeric` 判定返回 `manual` 时记 `skip`，spec 未覆盖此边界。**
`E.judgeNumeric`（[diagnose/engine.js:1033](../../../diagnose/engine.js#L1033)）对看不懂写法会返回 `{verdict:'manual'}`。孩子端只有「答对 / 答错」两态，不能把孩子输入判成错。规则：反馈屏显示「这个写法电脑没看懂，正确答案是 X」+ 解析 +「我懂了」，提交给引擎的 result 是 `skip`（引擎对 skip 与 wrong 同语义：先出一道更基础的确认题）。不判对错、不扣分。

**D8 — `assets/children.js` 不引入 `engine.js`，自带 `CONFIRM_CHOICES = [2,3,5]`（spec §4 说「用 E.clampConfirm 校验」）。**
档案页现在不加载引擎，为校验一个三元素数组而引入 1137 行引擎不值当。改为 children.js 自己定义并导出 `CONFIRM_CHOICES`，由 `tests/test_children.js` **断言它与 `E.CONFIRM_CHOICES` 逐元素相等**，两处漂移会被测试拦住。

**D9 — 新增 `assets/figure.js`，diagnose 的 `figureEl` 改为委托（spec §3 说 diagnose 只改 loadData）。**
243 道题带 `figure`（SVG 字符串），10 道带 `hideChoiceText`。`diagnose/app.js:80-91` 的 `figureEl` 里有一段**安全白名单**（拒 `<script>` / `foreignObject` / `<image>` / 外链）。孩子端渲染同样内容需要同一段 sanitizer；复制一份意味着将来修一处漏一处。抽成 `assets/figure.js`，diagnose 的 `figureEl(svg)` 变成一行委托，行为与类名 `q-figure` 完全不变。

**D10 — 「先跳过」结束本次会话回首页，而不是只摘掉当前点继续（spec §5.2 未明确）。**
引擎没有「从会话里摘掉一个目标」的接口；手改 `session.stack` / `targets` 会破坏 `E.replay` 的确定性。改为：记入跳过列表 → 把已作答的部分写成诊断记录（被跳过的点没作答，因此**不进任何记录列表**，符合「跳过不写诊断记录、不改变该点状态」）→ 回首页。其余 4 个目标仍是 unknown，下次派题按教材顺序自然还在队列里，跳过的那个已排到本册末尾。**没有问题被丢掉。**

**D11 — `buildId` 取**四个**真源文件的 SHA-256（spec §6.1 写「三文件」）。**
manifest 内嵌了 registry 派生的册顺序与顺序表，registry 变了产物就得失效，所以必须进哈希。

---

## File Structure

**新建**

| 文件 | 职责 |
| --- | --- |
| `scripts/build_bank_shards.py` | 只读真源四文件，产出 `data/bank/` 全部 225 个文件；`--check` 只比对不写 |
| `data/bank/manifest.json` | buildId + 学科骨架/册清单/分片计量 + 版本×学科册顺序与顺序表路径 + topicId→册反查表 |
| `data/bank/graph/<subject>.json` ×8 | `{topics:[…原文照抄…], deps:[…同学科…]}`。**必须保留 `diagnostic_question`**，D1 的哨兵靠它 |
| `data/bank/questions/<subject>/<volume>.json` ×117 | `{questions:[…全部题型…]}`，题型过滤在客户端做 |
| `data/bank/order/<edition>/<subject>.json` ×99 | `{topicIds:[…registry 原顺序…]}`（D6） |
| `assets/play-data.js` | UMD 分片加载器：取片、缓存、建图、查册。孩子端与家长诊断页共用 |
| `assets/figure.js` | SVG 安全白名单渲染（D9），`window.CnmFigure.el(svg, cls)` |
| `play/dispatch.js` | UMD 纯函数：派题、册进度、下一册、记录格式 |
| `play/session.js` | UMD 异步：会话上下文 + D1/D2 懒加载钩子 |
| `play/app.js` | 四屏状态机、localStorage 读写、判定与反馈 |
| `play/index.html` | 孩子端入口，无 site-header / site-nav / top-banner / stats.js / pwa.js |
| `play/style.css` | 儿童化视觉，只用 `assets/site.css` 的 CSS 变量 |
| `scripts/shard_budget.py` | 体积预算测量（提升 `_scratch/_s185_shard.py`，改用 `norm_vol` 与实际产物） |
| `scripts/prereq_closure.py` | 先修闭包测量（`_s190/_s192` 已被临时目录清理，按 spec §2 口径重写并互验） |
| `tests/browser_harness.js` | 静态服务器 + headless Chrome + CDP + until，供浏览器测试共用 |
| `tests/test_bank_shards.js` | 分片完整性（spec §10 的 6 条 + 可机判题下限） |
| `tests/test_play_data.js` | 加载器：缓存、并发去重、题型过滤、骨架索引稳定性、404 |
| `tests/test_play.js` | 派题 + 会话：spec §10 的 12 条 |
| `tests/test_play_browser.js` | 390×844 实测：黄金路径 + 边界 + 首屏体积 |

**修改**

| 文件 | 改什么 |
| --- | --- |
| `assets/children.js` | `SUBJECTS` / `CONFIRM_CHOICES` / `cleanSubjects` / `clean` / `checkArchive` / `setVolume`；`exportBackup` version→2；`checkBackup` 接受 1 与 2 |
| `children/index.html` | 表单加「学科教材设置」区块（学科 / 版本 / 册次 / 确认题数） |
| `children/page.js` | 取 manifest 填版本与册次、编辑时回填、提交带 subjects、`?from=play` 回链 |
| `children/children.css` | 「学科教材设置」区块的样式（沿用既有变量，不引新设计系统） |
| `diagnose/app.js` | **只改** `loadData()`（[:255-283](../../../diagnose/app.js#L255)）与 `figureEl`（[:80-91](../../../diagnose/app.js#L80)） |
| `diagnose/index.html` | 加 `../assets/figure.js` 与 `../assets/play-data.js` 两个 script 标签 |
| `sw.js` | `VERSION` v5→v6；SHELL 加 play/ 与两个新 assets；DATA 加 `data/bank/manifest.json`（`data/questions.json` **保留**，home.js 与 explore/app.js 仍在用） |
| `tests/test_children.js` | version 断言 1→2；「未知版本」用例 2→3；新增 subjects 与 CONFIRM_CHOICES 一致性断言 |
| `tests/test_children_browser.js` | 无效版本 fixture 2→3；Chrome 候选路径加 Windows |
| `docs/pwa.md` | 追加孩子端不重样的设备级边界说明 |
| `CHANGELOG.md` | 追加本轮条目 |

---

## Task 1: 分片构建器与产物

**Files:**
- Create: `scripts/build_bank_shards.py`
- Create: `data/bank/manifest.json`、`data/bank/graph/*.json`（8）、`data/bank/questions/*/*.json`（117）、`data/bank/order/*/*.json`（99）——全部由脚本生成
- Test: `tests/test_bank_shards.js`

**Interfaces:**
- Consumes: `scripts/gen_registry.py` 的 `norm_vol(raw)`、`subject_of(topic)`（该文件有 `if __name__ == '__main__'` 守卫，可安全 import）；真源四文件。
- Produces: `data/bank/` 产物，schema 如下。后续所有任务都按这份 schema 读，**不得改名**。

```json
{
  "buildId": "a1b2c3d4e5f6",
  "subjects": {
    "math": {
      "graphFile": "graph/math.json",
      "topics": 870,
      "volumes": ["一上", "一下", "…"],
      "shards": { "一上": { "file": "questions/math/一上.json", "topics": 55, "questions": 570, "bytes": 123456 } }
    }
  },
  "editions": {
    "cn_renjiao": {
      "label": "人教版",
      "subjects": { "math": { "label": "数学", "topics": 870, "volumes": ["一上", "…"], "orderFile": "order/cn_renjiao/math.json" } }
    }
  },
  "topicVolume": { "cnm_p001": "一上" }
}
```

所有路径相对 `data/bank/`。`subjects[s].volumes` = 真源 topics.json 顺序里册键的首次出现；`editions[e].subjects[s].volumes` = 该版本 registry `topicIds` 顺序里册键的首次出现（spec §5.3）。`bytes` = 分片文件 UTF-8 字节数。

- [ ] **Step 1: 写失败测试 `tests/test_bank_shards.js`**

```js
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
const sha = (rel) => crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, rel))).digest('hex');

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
      assert.deepStrictEqual(t, topics.find(x => x.id === t.id), '骨架必须原文照抄 ' + t.id);
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
        assert.deepEqual(q, questions.find(x => x.id === q.id), '分片必须原文照抄 ' + q.id);
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_bank_shards.js`
Expected: FAIL —— `ENOENT … data/bank/manifest.json`（产物还不存在）。

- [ ] **Step 3: 写 `scripts/build_bank_shards.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 data/bank/ —— 学科骨架 + 学科×册题库分片 + 版本×学科顺序表 + manifest。

真源是 data/topics.json、data/dependencies.json、data/questions.json、
data/editions/registry.json，本脚本只读不写它们。产物进 git，静态托管直接可用，无后端。

  python scripts/build_bank_shards.py            # 构建（并删除 manifest 不再声明的陈旧产物）
  python scripts/build_bank_shards.py --check    # 只比对不写；有差异或缺文件退出码 1
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_registry import norm_vol, subject_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bank")
SOURCES = ["data/topics.json", "data/dependencies.json", "data/questions.json", "data/editions/registry.json"]


def read_json(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def volume_of(topic):
    return norm_vol((topic.get("chapter") or "").strip().split(" ")[0])


def first_seen(pairs):
    out = []
    for v in pairs:
        if v not in out:
            out.append(v)
    return out


def build():
    topics = read_json("data/topics.json")
    deps = read_json("data/dependencies.json")
    questions = read_json("data/questions.json")
    registry = read_json("data/editions/registry.json")

    h = hashlib.sha256()
    for rel in SOURCES:
        with io.open(os.path.join(ROOT, rel), "rb") as f:
            h.update(f.read())

    topic_volume = {}
    by_subject = {}
    for t in topics:
        if t["id"] in topic_volume:
            raise SystemExit("真源 topics 有重复 id：" + t["id"])
        s = subject_of(t)
        topic_volume[t["id"]] = volume_of(t)
        by_subject.setdefault(s, []).append(t)
    for q in questions:
        if q["topicId"] not in topic_volume:
            raise SystemExit("题目挂在未知知识点上：" + q["id"])

    files = {}
    manifest = {"buildId": h.hexdigest()[:12], "subjects": {}, "editions": {}, "topicVolume": topic_volume}

    for s in sorted(by_subject):
        ts = by_subject[s]
        allow = set(t["id"] for t in ts)
        ds = [d for d in deps if d["topicId"] in allow and d["prerequisiteId"] in allow]
        graph_rel = "graph/%s.json" % s
        files[graph_rel] = compact({"topics": ts, "deps": ds})
        volumes = first_seen(topic_volume[t["id"]] for t in ts)
        shards = {}
        for v in volumes:
            ids = set(t["id"] for t in ts if topic_volume[t["id"]] == v)
            qs = [q for q in questions if q["topicId"] in ids]
            rel = "questions/%s/%s.json" % (s, v)
            body = compact({"questions": qs})
            files[rel] = body
            shards[v] = {"file": rel, "topics": len(ids), "questions": len(qs), "bytes": len(body.encode("utf-8"))}
        manifest["subjects"][s] = {"graphFile": graph_rel, "topics": len(ts), "volumes": volumes, "shards": shards}

    for ed in registry["versions"]:
        entry = {"label": ed["label"], "subjects": {}}
        for s, sv in ed["subjects"].items():
            for tid in sv["topicIds"]:
                if tid not in topic_volume:
                    raise SystemExit("registry 引用了未知知识点：%s/%s %s" % (ed["id"], s, tid))
            rel = "order/%s/%s.json" % (ed["id"], s)
            files[rel] = compact({"topicIds": sv["topicIds"]})
            entry["subjects"][s] = {
                "label": sv["label"], "topics": len(sv["topicIds"]),
                "volumes": first_seen(topic_volume[tid] for tid in sv["topicIds"]), "orderFile": rel,
            }
        manifest["editions"][ed["id"]] = entry

    files["manifest.json"] = compact(manifest)
    return files, manifest["buildId"]


def disk_files():
    out = {}
    if not os.path.isdir(OUT):
        return out
    for dirpath, _, names in os.walk(OUT):
        for n in names:
            full = os.path.join(dirpath, n)
            out[os.path.relpath(full, OUT).replace(os.sep, "/")] = full
    return out


def main():
    check = "--check" in sys.argv[1:]
    files, build_id = build()
    existing = disk_files()
    changed = [rel for rel in sorted(files)
               if rel not in existing or io.open(existing[rel], encoding="utf-8").read() != files[rel]]
    stale = sorted(set(existing) - set(files))
    print("buildId=%s files=%d changed=%d stale=%d" % (build_id, len(files), len(changed), len(stale)))
    if check:
        for rel in changed:
            print("  CHANGED " + rel)
        for rel in stale:
            print("  STALE   " + rel)
        return 1 if (changed or stale) else 0
    for rel in sorted(files):
        full = os.path.join(OUT, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(files[rel])
    for rel in stale:
        print("  PRUNE " + rel)
        os.remove(existing[rel])
    print("OK -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 构建产物**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 python scripts/build_bank_shards.py`
Expected: `buildId=<12 hex> files=225 changed=225 stale=0` 然后 `OK -> …/data/bank`。
若 `files` 不是 225，停下核对：8 骨架 + 117 册分片 + 99 顺序表 + 1 manifest。册数或顺序表数变了说明真源变了，先查清再继续。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_bank_shards.js`
Expected: `8 passed, 0 failed`。
若「每个知识点至少 1 道 choice/numeric」失败，说明真源里有只含 short/self 的点——这会激活 D2 的 `unaskable` 分支，**不要改测试放宽它**，先报告该点 id 给用户。

- [ ] **Step 6: 验证构建幂等**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 python scripts/build_bank_shards.py --check && PYTHONIOENCODING=utf-8 python scripts/build_bank_shards.py --check`
Expected: 两次都 `changed=0 stale=0`、退出码 0。

- [ ] **Step 7: 跑回归闸门**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 STRICT_STANDARDS=1 python scripts/validate.py && PYTHONIOENCODING=utf-8 python scripts/verify_questions.py && PYTHONIOENCODING=utf-8 python scripts/version_gate.py && node tests/test_engine.js && node tests/test_children.js`
Expected: 全部通过，题库仍是 **35143**、知识点 **3504**（本任务不改真源）。

- [ ] **Step 8: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add scripts/build_bank_shards.py tests/test_bank_shards.js data/bank
git commit -m "feat(bank): 学科骨架 + 学科×册题库分片 + 版本顺序表 + manifest 构建器"
```

---

## Task 2: 分片加载器 `assets/play-data.js`

**Files:**
- Create: `assets/play-data.js`
- Test: `tests/test_play_data.js`

**Interfaces:**
- Consumes: Task 1 的 `data/bank/` schema；`diagnose/engine.js` 的 `E.buildGraph(topics, deps, questions)`。
- Produces: `CnmPlayData.create(opts)` → 实例，方法如下（Task 4/5/6/8 全部按这些签名调用）。

| 方法 | 签名 | 返回 |
| --- | --- | --- |
| `loadManifest` | `()` | `Promise<manifest>`，内存缓存 |
| `loadGraph` | `(subject)` | `Promise<{topics, deps}>`，内存缓存 |
| `loadQuestions` | `(subject, volume)` | `Promise<questions[]>`，内存缓存 |
| `loadOrder` | `(editionId, subject)` | `Promise<topicIds[]>`，内存缓存 |
| `buildGraphFor` | `(subject, loadedVolumes, types)` | 同步返回 `E.buildGraph` 的 graph；`types` 为 `null` 时不过滤题型 |
| `volumeOf` | `(topicId)` | 册键字符串，未知点返回 `null` |
| `volumesOf` | `(subject)` | `string[]`（学科册顺序） |
| `editionsFor` | `(subject)` | `[{id, label}]`（该学科有挂载的版本，manifest 顺序） |
| `editionVolumes` | `(editionId, subject)` | `string[]`（该版本该学科的册顺序），未挂载返回 `[]` |

`create({base, fetchJson})`：`base` 默认 `'../data/bank/'`；`fetchJson(url)` 默认用 `fetch` 并在 `!r.ok` 时抛 `Error(url + ' → HTTP ' + status)`。骨架/分片/顺序表 URL 带 `?v=<buildId>`，manifest 自身不带。

- [ ] **Step 1: 写失败测试 `tests/test_play_data.js`**

```js
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
const make = (calls, missing) => PD.create({ base: '', fetchJson: disk(calls, missing) });

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
    const d = PD.create({ base: '', fetchJson: async url => {
      calls.push(url);
      if (fail) throw new Error(url + ' → HTTP 500');
      return JSON.parse(fs.readFileSync(path.join(ROOT, url.split('?')[0]), 'utf8'));
    } });
    await d.loadManifest();
    await assert.rejects(() => d.loadGraph('math'), /HTTP 500/);
    fail = false;
    const g = await d.loadGraph('math');
    assert.ok(g.topics.length > 0);
    assert.equal(calls.filter(u => u.indexOf('graph/math.json') === 0).length, 2);
  });

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play_data.js`
Expected: FAIL —— `Cannot find module '../assets/play-data.js'`。

- [ ] **Step 3: 写 `assets/play-data.js`**

```js
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play_data.js`
Expected: `7 passed, 0 failed`。

- [ ] **Step 5: 跑回归闸门**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_engine.js && node tests/test_bank_shards.js && node tests/test_children.js`
Expected: 全部通过（本任务没碰真源和引擎）。

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add assets/play-data.js tests/test_play_data.js
git commit -m "feat(play): 分片加载器（骨架整取 + 册懒取 + legacy 哨兵 + 索引稳定性）"
```

---

## Task 3: 档案加学科教材设置，备份升 v2

**Files:**
- Modify: `assets/children.js:10-11`（常量）、`:42-47`（clean）、`:69-79`（update 后插入 setVolume）、`:169-175`（exportBackup）、`:193-230`（checkArchive）、`:231-237`（checkBackup）、`:328-335`（导出表）
- Modify: `children/index.html:66-82`（表单）
- Modify: `children/page.js:6-9`、`:33-50`、`:54-76`、`:143-151`
- Modify: `tests/test_children.js:66`、`:348`，并追加新测试
- Modify: `tests/test_children_browser.js:198`（无效版本 fixture）与 Chrome 候选路径行
- Test: `tests/test_children.js`、`tests/test_children_browser.js`

**Interfaces:**
- Consumes: Task 1 的 `data/bank/manifest.json`（`children/page.js` 直接 `fetch('../data/bank/manifest.json')`，**不引入 engine.js 也不引入 play-data.js**）。
- Produces:
  - `CnmChildren.SUBJECTS` → `['math','chinese','english','physics','science','morality','history','geography']`
  - `CnmChildren.CONFIRM_CHOICES` → `[2, 3, 5]`
  - `child.subjects` → `{ [subject]: { edition: string, volume: string, confirm: 2|3|5 } }`；旧档案可能**没有这个字段**，所有读取方一律写 `(child.subjects || {})`
  - `CnmChildren.setVolume(childId, subject, volume)` → `boolean`
  - `exportBackup().version` → `2`；`parseBackup` 接受 version 1 与 2

- [ ] **Step 1: 改 `tests/test_children.js` 的版本断言并追加失败测试**

把 `:66` 的 `assert.equal(backup.version, 1);` 改成 `assert.equal(backup.version, 2);`。
把 `:348` 的 `data => { data.version = 2; },` 改成 `data => { data.version = 3; },`。
在文件末尾 `console.log('\n' + passed + ' passed, 0 failed')` **之前**插入：

```js
test('CONFIRM_CHOICES 与引擎的取值集合逐元素相等（两处各写一份，靠这条防漂移）', () => {
  const E = require('../diagnose/engine.js');
  const { api } = load();
  assert.deepStrictEqual(api.CONFIRM_CHOICES, E.CONFIRM_CHOICES);
  assert.deepStrictEqual(api.SUBJECTS, ['math', 'chinese', 'english', 'physics', 'science', 'morality', 'history', 'geography']);
});

test('add / update 保存 subjects，非法学科与非法 confirm 被丢弃或夹回默认', () => {
  const { api } = load();
  const subjects = {
    math: { edition: 'cn_renjiao', volume: '三上', confirm: 5 },
    chinese: { edition: 'cn_tongbian', volume: '七年级上册', confirm: 9 },
    english: { edition: '', volume: '三上', confirm: 3 },
    physics: { edition: 'cn_renjiao', volume: '', confirm: 3 },
    不存在的学科: { edition: 'cn_renjiao', volume: '三上', confirm: 3 },
    __proto__: { edition: 'x', volume: 'y', confirm: 3 }
  };
  const added = api.add({ name: '小满', grade: '三年级', textbook: '人教版', subjects });
  assert.equal(added.ok, true);
  assert.deepStrictEqual(added.child.subjects, {
    math: { edition: 'cn_renjiao', volume: '三上', confirm: 5 },
    chinese: { edition: 'cn_tongbian', volume: '七年级上册', confirm: 3 }
  });
  assert.equal({}.polluted, undefined);
  const up = api.update(added.child.id, { name: '小满', grade: '四年级', textbook: '人教版', subjects: { math: { edition: 'cn_beishida', volume: '四上', confirm: 2 } } });
  assert.equal(up.ok, true);
  assert.deepStrictEqual(up.child.subjects, { math: { edition: 'cn_beishida', volume: '四上', confirm: 2 } });
  assert.equal(up.child.grade, '四年级');
});

test('旧档案没有 subjects 也能读、能导出、能校验', () => {
  const { api } = load(fixture());
  assert.equal(api.current().subjects, undefined);
  assert.equal(exported(api).version, 2);
  assert.deepStrictEqual(exported(api).profiles, profiles);
});

test('setVolume 只改当前学科的册，不动其他学科和其他字段', () => {
  const { api } = load();
  const c = api.add({ name: '小满', grade: '三年级', textbook: '人教版', subjects: {
    math: { edition: 'cn_renjiao', volume: '三上', confirm: 5 },
    chinese: { edition: 'cn_tongbian', volume: '三上', confirm: 3 }
  } }).child;
  assert.equal(api.setVolume(c.id, 'math', '三下'), true);
  assert.deepStrictEqual(api.get(c.id).subjects.math, { edition: 'cn_renjiao', volume: '三下', confirm: 5 });
  assert.deepStrictEqual(api.get(c.id).subjects.chinese, { edition: 'cn_tongbian', volume: '三上', confirm: 3 });
  assert.equal(api.get(c.id).grade, '三年级');
  assert.equal(api.setVolume(c.id, 'english', '三上'), false);
  assert.equal(api.setVolume(c.id, 'math', ''), false);
  assert.equal(api.setVolume('不存在', 'math', '三下'), false);
});

test('version 1 备份仍可导入，version 3 被拒', () => {
  const { api } = load(fixture());
  const v1 = exported(api);
  v1.version = 1;
  delete v1.profiles.children[0].subjects;
  assert.equal(api.parseBackup(JSON.stringify(v1)).version, 1);
  const { api: empty } = load();
  const preview = empty.previewImport(JSON.parse(JSON.stringify(v1)));
  assert.equal(preview.addedChildren, 2);
  empty.importBackup(JSON.parse(JSON.stringify(v1)), preview.token);
  assert.equal(empty.list().length, 2);
  const bad = exported(api);
  bad.version = 3;
  assert.throws(() => api.parseBackup(JSON.stringify(bad)), /暂不支持这个备份版本/);
});

test('备份里的 subjects 形状非法时整份拒绝，且不写存储', () => {
  const cases = [
    c => { c.subjects = 'wrong'; },
    c => { c.subjects = { math: { edition: 'cn_renjiao', volume: '三上', confirm: 4 } }; },
    c => { c.subjects = { math: { edition: '', volume: '三上', confirm: 3 } }; },
    c => { c.subjects = { math: { edition: 'cn_renjiao', volume: '', confirm: 3 } }; },
    c => { c.subjects = { math: { edition: 'cn_renjiao', volume: '三上'.repeat(20), confirm: 3 } }; },
    c => { c.subjects = { 不存在的学科: { edition: 'cn_renjiao', volume: '三上', confirm: 3 } }; },
    c => { c.subjects = { math: null }; }
  ];
  for (const mutate of cases) {
    const { api, writes } = load(fixture());
    const data = backup();
    mutate(data.profiles.children[0]);
    assert.throws(() => api.parseBackup(JSON.stringify(data)));
    assert.deepStrictEqual(writes, []);
  }
});
```

同时把 `tests/test_children_browser.js:198` 的 `['version.json',JSON.stringify({...backup,version:2})]` 改成 `version:3`，并把 Chrome 候选路径那一行（`const chromePath = [process.env.CHROME, '/Applications/…`）改成：

```js
  const chromePath = [process.env.CHROME,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    (process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'
  ].find(p => p && fs.existsSync(p));
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_children.js`
Expected: FAIL —— `api.CONFIRM_CHOICES` 为 undefined、`backup.version` 仍是 1。

- [ ] **Step 3: 改 `assets/children.js`**

在 `:11`（`var TEXTBOOKS = …`）之后插入：

```js
  var SUBJECTS = ['math', 'chinese', 'english', 'physics', 'science', 'morality', 'history', 'geography'];
  // 与 diagnose/engine.js 的 CONFIRM_CHOICES 同值；档案页不加载引擎，由 tests/test_children.js 锁住一致性。
  var CONFIRM_CHOICES = [2, 3, 5];
  var MAX_VOLUME_LEN = 16;
```

把 `clean(f)`（`:42-47`）整体替换为：

```js
  function cleanSubjects(raw) {
    var out = {};
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return out;
    SUBJECTS.forEach(function (s) {
      if (!Object.prototype.hasOwnProperty.call(raw, s)) return;
      var v = raw[s];
      if (!v || typeof v !== 'object' || Array.isArray(v)) return;
      var edition = typeof v.edition === 'string' ? v.edition.trim() : '';
      var volume = typeof v.volume === 'string' ? v.volume.trim() : '';
      if (!edition || !volume || volume.length > MAX_VOLUME_LEN) return;
      var c = Math.floor(Number(v.confirm));
      out[s] = { edition: edition, volume: volume, confirm: CONFIRM_CHOICES.indexOf(c) >= 0 ? c : 3 };
    });
    return out;
  }
  function clean(f) {
    var name = String(f && f.name || '').replace(/\s+/g, ' ').trim();
    var grade = GRADES.indexOf(f && f.grade) >= 0 ? f.grade : '';
    var textbook = TEXTBOOKS.indexOf(f && f.textbook) >= 0 ? f.textbook : TEXTBOOKS[0];
    return { name: name, grade: grade, textbook: textbook, subjects: cleanSubjects(f && f.subjects) };
  }
```

在 `update`（`:69-79`）之后、`remove` 之前插入：

```js
  /* 册末衔接回写：只改一个学科的册次，不走 clean()，避免表单字段不全时抹掉已有设置。 */
  function setVolume(childId, subject, volume) {
    if (SUBJECTS.indexOf(subject) < 0 || typeof volume !== 'string' || !volume.trim() || volume.length > MAX_VOLUME_LEN) return false;
    var s = state();
    var i = s.children.map(function (c) { return c.id; }).indexOf(childId);
    if (i < 0) return false;
    var c = s.children[i];
    var subs = c.subjects || {};
    if (!Object.prototype.hasOwnProperty.call(subs, subject)) return false;
    var next = Object.assign({}, subs);
    next[subject] = Object.assign({}, subs[subject], { volume: volume });
    s.children[i] = Object.assign({}, c, { subjects: next });
    return write(KEY, s);
  }
```

`exportBackup()` 的 `version: 1,`（`:171`）改成 `version: 2,`。

`checkArchive` 里 `profiles.children.forEach` 的校验块（`:199-206`）——在 `ids.add(c.id);` **之前**插入：

```js
      if (own(c, 'subjects')) {
        if (!isObject(c.subjects)) throw new Error('孩子的学科教材设置不正确。');
        Object.keys(c.subjects).forEach(function (s) {
          var v = c.subjects[s];
          if (SUBJECTS.indexOf(s) < 0 || !isObject(v) ||
              typeof v.edition !== 'string' || !validId(v.edition) ||
              typeof v.volume !== 'string' || !v.volume.trim() || v.volume.length > MAX_VOLUME_LEN ||
              CONFIRM_CHOICES.indexOf(v.confirm) < 0) throw new Error('孩子的学科教材设置不正确。');
        });
      }
```

`checkBackup` 的 `if (backup.version !== 1)`（`:233`）改成：

```js
    if (backup.version !== 1 && backup.version !== 2) throw new Error('暂不支持这个备份版本。');
```

导出表（`:328-335`）第一行改成 `GRADES: GRADES, TEXTBOOKS: TEXTBOOKS, SUBJECTS: SUBJECTS, CONFIRM_CHOICES: CONFIRM_CHOICES.slice(), MAX_CHILDREN: MAX_CHILDREN,`，并在 `add: add, update: update, remove: remove,` 后加 `setVolume: setVolume,`。

- [ ] **Step 4: 跑单测确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_children.js`
Expected: 原有测试 + 6 条新测试全部 ok，末行 `N passed, 0 failed`。
注意 `validId(v.edition)`：实测 51 个版本 id 全部匹配 `^[A-Za-z0-9_-]{1,128}$`，无需放宽。

- [ ] **Step 5: 改 `children/index.html` 表单**

把 `:75` 的 `<p class="muted small" id="book-note">…</p>` 之后、`<p class="err" id="f-error" …>` 之前插入：

```html
      <fieldset class="kid-subjects" id="subject-settings">
        <legend>学科教材（孩子端自动派题用）</legend>
        <p class="muted small">不设置的学科，孩子端会提示「请家长先设置教材」。年级和上面的教材版本照旧保留，这里选的是精确版本与册次。</p>
        <div id="subject-rows"></div>
        <p class="muted small" id="subject-note">确认题数：连续答对几道才算「学会」。选 5 更稳，但每个知识点要练更多题。</p>
      </fieldset>
```

- [ ] **Step 6: 改 `children/page.js`**

在 `:24`（`var editing = null;`）之后插入：

```js
  var SUBJECT_LABEL = { math: '数学', chinese: '语文', english: '英语', physics: '物理', science: '科学', morality: '道德与法治', history: '历史', geography: '地理' };
  var subjectRows = document.getElementById('subject-rows');
  var bankManifest = null;
  var subjectForm = {};

  function fillOptions(sel, items, placeholder) {
    sel.textContent = '';
    if (placeholder) { var o = el('option', null, placeholder); o.value = ''; sel.appendChild(o); }
    items.forEach(function (x) {
      var o = el('option', null, x.label);
      o.value = x.value;
      sel.appendChild(o);
    });
  }
  function buildSubjectRows() {
    subjectRows.textContent = '';
    subjectForm = {};
    CC.SUBJECTS.forEach(function (s) {
      var row = el('div', 'subject-row');
      row.appendChild(el('span', 'subject-name', SUBJECT_LABEL[s]));
      var ed = el('select'); ed.id = 'sub-edition-' + s; ed.setAttribute('aria-label', SUBJECT_LABEL[s] + '教材版本');
      var vol = el('select'); vol.id = 'sub-volume-' + s; vol.setAttribute('aria-label', SUBJECT_LABEL[s] + '册次');
      var cf = el('select'); cf.id = 'sub-confirm-' + s; cf.setAttribute('aria-label', SUBJECT_LABEL[s] + '确认题数');
      fillOptions(ed, [], '不设置');
      fillOptions(vol, [], '先选版本');
      fillOptions(cf, CC.CONFIRM_CHOICES.map(function (n) { return { value: String(n), label: '连续答对 ' + n + ' 道' }; }));
      cf.value = '3';
      ed.addEventListener('change', function () { fillVolumes(s); });
      row.appendChild(ed); row.appendChild(vol); row.appendChild(cf);
      subjectRows.appendChild(row);
      subjectForm[s] = { edition: ed, volume: vol, confirm: cf };
    });
  }
  function fillEditions() {
    CC.SUBJECTS.forEach(function (s) {
      var eds = bankManifest ? Object.keys(bankManifest.editions).filter(function (id) {
        return !!bankManifest.editions[id].subjects[s];
      }).map(function (id) { return { value: id, label: bankManifest.editions[id].label }; }) : [];
      var keep = subjectForm[s].edition.value;
      fillOptions(subjectForm[s].edition, eds, '不设置');
      if (eds.some(function (x) { return x.value === keep; })) subjectForm[s].edition.value = keep;
      fillVolumes(s);
    });
  }
  function fillVolumes(s) {
    var id = subjectForm[s].edition.value;
    var entry = id && bankManifest && bankManifest.editions[id] && bankManifest.editions[id].subjects[s];
    var vols = entry ? entry.volumes : [];
    var keep = subjectForm[s].volume.value;
    fillOptions(subjectForm[s].volume, vols.map(function (v) { return { value: v, label: v }; }), vols.length ? '请选择册次' : '先选版本');
    if (vols.indexOf(keep) >= 0) subjectForm[s].volume.value = keep;
  }
  function readSubjects() {
    var out = {};
    CC.SUBJECTS.forEach(function (s) {
      var f = subjectForm[s];
      if (!f.edition.value || !f.volume.value) return;
      out[s] = { edition: f.edition.value, volume: f.volume.value, confirm: Number(f.confirm.value) };
    });
    return out;
  }
  function writeSubjects(subjects) {
    var subs = subjects || {};
    CC.SUBJECTS.forEach(function (s) {
      var f = subjectForm[s], v = subs[s];
      f.edition.value = v ? v.edition : '';
      fillVolumes(s);
      f.volume.value = v ? v.volume : '';
      f.confirm.value = String(v && v.confirm ? v.confirm : 3);
    });
  }
  buildSubjectRows();
  fetch('../data/bank/manifest.json').then(function (r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }).then(function (m) {
    bankManifest = m;
    fillEditions();
    if (editing) writeSubjects((CC.get(editing) || {}).subjects);
  }).catch(function () {
    document.getElementById('subject-note').textContent = '教材清单加载失败，请刷新页面后再设置学科教材。';
  });
```

`resetForm()`（`:54-63`）里 `bookSel.value = CC.TEXTBOOKS[0];` 之后加 `writeSubjects({});`。
`startEdit(c)`（`:65-76`）里 `bookSel.value = c.textbook;` 之后加 `writeSubjects(c.subjects);`。
提交处理器（`:145`）的 `var f = { name: nameIn.value, grade: gradeSel.value, textbook: bookSel.value };` 改成 `var f = { name: nameIn.value, grade: gradeSel.value, textbook: bookSel.value, subjects: readSubjects() };`。

`?from=diagnose` 回链块（`:41-50`）之后插入：

```js
  if (params.get('from') === 'play') {
    var backPlay = document.getElementById('back');
    var aPlay = el('a', null, '← 回到孩子端');
    aPlay.href = '../play/' + (params.get('subject') ? '?subject=' + encodeURIComponent(params.get('subject')) : '');
    backPlay.appendChild(aPlay);
    backPlay.hidden = false;
  }
```

在 `children/children.css` 末尾追加：

```css
.kid-subjects { border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px 12px; margin: 12px 0; }
.kid-subjects legend { font-weight: 600; padding: 0 4px; }
.subject-row { display: grid; grid-template-columns: 5.5em 1fr 1fr 1fr; gap: 6px; align-items: center; margin: 6px 0; }
.subject-name { font-size: 0.95em; }
@media (max-width: 700px) { .subject-row { grid-template-columns: 1fr 1fr; } .subject-name { grid-column: 1 / -1; } }
```

- [ ] **Step 7: 跑浏览器回归**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_children_browser.js`
Expected: 三行 `PASS: …`，退出码 0。本机 Chrome 在 `C:/Program Files/Google/Chrome/Application/chrome.exe`，Step 1 已加进候选路径。
若备份往返断言失败，检查是不是 `clean()` 给导出加出了 `subjects` —— **不会**：`exportBackup` 直接读 localStorage 原文，不经过 `clean()`，所以 v1 档案导出后仍无 `subjects` 字段。

- [ ] **Step 8: 跑其余闸门**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_engine.js && node tests/test_bank_shards.js && node tests/test_play_data.js && PYTHONIOENCODING=utf-8 python scripts/version_gate.py`
Expected: 全部通过。

- [ ] **Step 9: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add assets/children.js children/index.html children/page.js children/children.css tests/test_children.js tests/test_children_browser.js
git commit -m "feat(children): 档案加学科×版本×册次×确认题数，备份升 v2（v1 仍可导入）"
```

---

## Task 4: 纯派题 `play/dispatch.js`

**Files:**
- Create: `play/dispatch.js`
- Test: `tests/test_play.js`（本任务建文件，Task 5 追加）

**Interfaces:**
- Consumes: `CnmChildren.latestStatus(childId, subject)` 的返回形状 `{ [topicId]: { status: 'mastered'|'shaky'|'weak', recKey, at, label, root, subject } }`；Task 2 的 `volumeOf`。
- Produces: `CnmPlayDispatch`（Node 下 `require('../play/dispatch.js')`）

| 成员 | 签名 | 返回 |
| --- | --- | --- |
| `TARGET_COUNT` | 常量 | `5` |
| `limitFor` | `(confirm)` | `5 * (confirm + 2)` |
| `pickTargets` | `({topicIds, volumeOf, volume, status, skipped, count})` | `{targets, fresh, deferred, exhausted}` |
| `volumeProgress` | `({topicIds, volumeOf, volume, status})` | `{total, mastered, ratio}` |
| `nextVolume` | `(volumes, current)` | `string \| null` |
| `buildRecord` | `({subject, label, session, summary})` | 诊断记录对象（不含 savedAt） |

`pickTargets` 语义（spec §5.1 + §5.2）：`fresh` = 本册、非 mastered、不在 skipped 里，**保持 topicIds 原顺序**；`deferred` = 本册、非 mastered、在 skipped 里，同样保持原顺序；`targets` = `(fresh.length ? fresh : deferred).slice(0, count)`；`exhausted` = 两个列表都空。

- [ ] **Step 1: 写失败测试 `tests/test_play.js`**

```js
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play.js`
Expected: FAIL —— `Cannot find module '../play/dispatch.js'`。

- [ ] **Step 3: 写 `play/dispatch.js`**

```js
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play.js`
Expected: `9 passed, 0 failed`。

- [ ] **Step 5: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add play/dispatch.js tests/test_play.js
git commit -m "feat(play): 教材顺序派题、跳过排到册末、册进度与记录格式（纯函数）"
```

---

## Task 5: 懒加载会话驱动 `play/session.js`

**Files:**
- Create: `play/session.js`
- Create: `scripts/prereq_closure.py`
- Test: `tests/test_play.js`（追加）

**Interfaces:**
- Consumes: Task 2 的加载器实例（`loadGraph` / `loadQuestions` / `buildGraphFor` / `volumeOf` / `volumesOf`）；`E.createSession` / `nextItem` / `applyAnswer` / `replay` / `summarize`。
- Produces: `CnmPlaySession`（Node 下 `require('../play/session.js')`，UMD 传入引擎）

| 方法 | 签名 | 返回 |
| --- | --- | --- |
| `create` | `({data, subject, types, seed, confirm, limit, avoid})` | `ctx` |
| `open` | `async (ctx, targets)` | `ctx`（已设 `ctx.item`，可能为 `null`） |
| `next` | `async (ctx)` | `item \| null`（`{topicId, question, attempt}`，**保证 `question.type !== 'legacy'`**） |
| `answer` | `async (ctx, result, text)` | 新的 `item \| null` |
| `summary` | `(ctx)` | `E.summarize` 的结果 |

`ctx` 形状：`{ data, subject, types, opts:{limit,confirm,seed,avoid}, loaded:Set<string>, unaskable:Set<string>, graph, session, item }`。
`answer` 的 `result` ∈ `'correct'|'wrong'|'skip'`；`text` 可省略。若 `next` 抛错，答案**已记录**、`ctx.item` 为 `null`，调用方重试时只调 `next(ctx)`，不得重复 `answer`。

- [ ] **Step 1: 追加失败测试到 `tests/test_play.js`**

在末尾 `console.log('\n' + passed + …)` **之前**插入（并把文件顶部的 `const D = require(...)` 之后加上 `const S = require('../play/session.js');`）：

```js
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
    const rebuilt = E.replay(ctx.graph, ctx.session.targets, ctx.session.answers, ctx.opts);
    assert.deepEqual(rebuilt.answers, ctx.session.answers);
    assert.deepEqual(rebuilt.stack, ctx.session.stack);
    assert.deepEqual(rebuilt.status, ctx.session.status);
    const replayed = [];
    let s2 = E.createSession(ctx.graph, ctx.session.targets, ctx.opts);
    for (const a of ctx.session.answers) {
      const it = E.nextItem(ctx.graph, s2);
      if (it) replayed.push(it.question.id);
      s2 = E.applyAnswer(ctx.graph, s2, a.id, a.result, { text: a.text });
    }
    assert.deepEqual(replayed, asked, '重建后必须出同样的题');
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
    const bank = { '一上': bank5['一上'], '一下': bank5['一下'] };
    const data = fakeData({ a: '一上', b: '一上', c: '一下', d: '二上', onlyshort: '一上' }, bank, topics5, deps5);
    const ctx = S.create(Object.assign({ data }, opts5));
    await S.open(ctx, ['c']);
    await S.answer(ctx, 'wrong', 'B');
    await assert.rejects(() => S.answer(ctx, 'wrong', 'B'), /HTTP 404/);
    assert.equal(ctx.item, null);
    assert.equal(ctx.session.answers.length, 2);
    bank['二上'] = bank5['二上'];
    data.loadQuestions = async (subject, volume) => {
      data.calls.push(volume);
      if (volume === '一上') { data.loaded.add(volume); return bank5['一上']; }
      throw new Error('HTTP 404 ' + volume);
    };
    await assert.rejects(() => S.next(ctx), /HTTP 404/);
    assert.equal(ctx.session.answers.length, 2, '重试不得追加作答');
  });

  console.log('\n' + passed + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
```

同时**删掉**文件原先末尾那两行同步收尾（`console.log('\n' + passed + …)` 与 `process.exit(…)`），因为收尾已移进上面的 async IIFE。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play.js`
Expected: FAIL —— `Cannot find module '../play/session.js'`。

- [ ] **Step 3: 写 `play/session.js`**

```js
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play.js`
Expected: `9 + 10 = 19 passed, 0 failed`。
若「10 轮不重样」失败，**不要改引擎**：先打印每轮选中的难度档，核对 `pickQuestion` 的「难度优先于没出过」语义（[diagnose/engine.js:237-278](../../../diagnose/engine.js#L237)）。fixture 给了 10 basic + 10 standard + 40 challenge，正好支撑 confirm=5 的 10 轮。

- [ ] **Step 5: 写先修闭包测量脚本 `scripts/prereq_closure.py`**

`_scratch/_s190_closure.py` / `_s192_clo5.py` 已随临时目录清理消失，按 spec §2 的口径重写：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""先修闭包测量：整册闭包 与 一次会话 5 个目标的闭包，各跨多少册、多少点。

spec §2 的数字用这个脚本复跑。结果写 _scratch/prereq_closure.txt（UTF-8），不打印中文到 stdout。

  python scripts/prereq_closure.py            # 全学科
  python scripts/prereq_closure.py --subject chinese
"""
from __future__ import annotations

import collections
import io
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_registry import norm_vol, subject_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def main():
    only = None
    if "--subject" in sys.argv:
        only = sys.argv[sys.argv.index("--subject") + 1]
    topics = load("data/topics.json")
    deps = load("data/dependencies.json")
    manifest = load("data/bank/manifest.json")
    registry = load("data/editions/registry.json")
    vol = manifest["topicVolume"]
    prereqs = collections.defaultdict(list)
    for d in deps:
        prereqs[d["topicId"]].append(d["prerequisiteId"])

    def closure(ids):
        seen = set()
        stack = list(ids)
        while stack:
            cur = stack.pop()
            for p in prereqs[cur]:
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    def measure(targets):
        cl = closure(targets) | set(targets)
        vols = set(vol[i] for i in cl if i in vol)
        return len(vols), len(cl)

    out = []
    whole = []
    five = []
    for ed in registry["versions"]:
        for s, sv in ed["subjects"].items():
            if only and s != only:
                continue
            by_vol = collections.OrderedDict()
            for tid in sv["topicIds"]:
                by_vol.setdefault(vol[tid], []).append(tid)
            for v, ids in by_vol.items():
                whole.append((measure(ids), ed["id"], s, v, len(ids)))
                # 孩子端一次派 5 个：跳过已掌握无法在此静态复现，取教材顺序前 5 个作为口径
                five.append((measure(ids[:5]), ed["id"], s, v))
    out.append("整册闭包：样本 %d" % len(whole))
    out.append("  跨册数 最大 %d / 中位 %d" % (max(x[0][0] for x in whole), int(statistics.median(x[0][0] for x in whole))))
    out.append("  点数   最大 %d / 中位 %d" % (max(x[0][1] for x in whole), int(statistics.median(x[0][1] for x in whole))))
    out.append("  top 10（跨册数, 点数, 版本, 学科, 册, 本册点数）：")
    for row in sorted(whole, key=lambda x: -x[0][0])[:10]:
        out.append("    %s" % (row,))
    out.append("")
    out.append("5 目标闭包：样本 %d" % len(five))
    out.append("  跨册数 最大 %d / 中位 %d" % (max(x[0][0] for x in five), int(statistics.median(x[0][0] for x in five))))
    out.append("  点数   最大 %d / 中位 %d" % (max(x[0][1] for x in five), int(statistics.median(x[0][1] for x in five))))
    out.append("")
    out.append("chinese 九下 整册：%s" % (measure([t for t in vol if vol[t] == "九下" and subject_of({"id": t, "subject": "chinese"}) == "chinese"]),))
    os.makedirs(os.path.join(ROOT, "_scratch"), exist_ok=True)
    with io.open(os.path.join(ROOT, "_scratch", "prereq_closure.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("whole=%d five=%d -> _scratch/prereq_closure.txt" % (len(whole), len(five)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: 跑闭包脚本并与 spec §2 互验**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 python scripts/prereq_closure.py`
然后 Read `_scratch/prereq_closure.txt`。
Expected: 量级与 spec §2 一致——整册闭包最多约 **20 册**、chinese 九下约 **17 册 / 751 点**、5 目标闭包中位数约 **9 册 / 134 点**。
**若不一致，先查脚本口径（是否漏了 soft 边、是否把 external 点算进去），不得默默改 spec 的数字。** 查清后在 CHANGELOG 里写明订正。
脚本里最后一行 `subject_of({"id": t, "subject": "chinese"})` 是恒真过滤，只为把 chinese 的九下单独列出来；若读起来别扭，改成 `[t for t in vol if vol[t] == "九下" and t.startswith("cnc_")]`，两者等价（实测 `cnc_` 前缀唯一对应 chinese）。

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add play/session.js tests/test_play.js scripts/prereq_closure.py
git commit -m "feat(play): legacy 哨兵懒加载钩子 + 单调推进保证 + 先修闭包测量脚本"
```

---

## Task 6: 孩子端壳、首页、答题与反馈屏

**Files:**
- Create: `assets/figure.js`、`play/index.html`、`play/style.css`、`play/app.js`
- Create: `tests/browser_harness.js`、`tests/test_play_browser.js`
- Modify: `diagnose/app.js:80-91`（figureEl 委托）、`diagnose/index.html`（两个 script 标签）

**Interfaces:**
- Consumes: Task 2 `CnmPlayData`、Task 3 `CnmChildren.SUBJECTS/setVolume/latestStatus`、Task 4 `CnmPlayDispatch`、Task 5 `CnmPlaySession`。
- Produces:
  - `CnmFigure.el(svg, cls)` → `HTMLElement|null`（与 diagnose 原 `figureEl` 行为一致，默认类名由调用方给）
  - `tests/browser_harness.js` 导出 `{ serve, launch, until, CDP, MIME }`（Task 7 复用）
  - `play/app.js` 的存储键：`cnmPlay.seen.v1.<childId>`、`cnmPlay.skipped.v1.<childId>.<subject>`、`cnmPlay.subject.v1`
  - `play/app.js` 暴露 `window.__play`（**仅测试用**）：`{ state, boot, start, commit, skipTopic, renderHome }`

- [ ] **Step 1: 写 `assets/figure.js`，diagnose 委托**

```js
/* 题目插图：只渲染通过白名单的内联 SVG。诊断页与孩子端共用，避免两份 sanitizer 漂移。 */
(function () {
  'use strict';
  function el(svg, cls) {
    if (typeof svg !== 'string' || svg.indexOf('<svg') !== 0) return null;
    if (/<\s*script|foreignObject|<\s*image\b|https?:\/\//i.test(svg.replace('xmlns="http://www.w3.org/2000/svg"', ''))) return null;
    var wrap = document.createElement('div');
    wrap.className = cls || 'q-figure';
    wrap.innerHTML = svg;
    var node = wrap.querySelector('svg');
    if (!node) return null;
    node.setAttribute('role', 'img');
    node.setAttribute('aria-hidden', 'true');
    node.setAttribute('focusable', 'false');
    return wrap;
  }
  window.CnmFigure = { el: el };
})();
```

把 `diagnose/app.js:80-91` 的 `function figureEl(svg) { … }` 整体替换为：

```js
  function figureEl(svg) { return window.CnmFigure ? window.CnmFigure.el(svg, 'q-figure') : null; }
```

在 `diagnose/index.html` 里加载 `app.js` 的那个 `<script>` 标签**之前**插入：

```html
<script src="../assets/figure.js"></script>
<script src="../assets/play-data.js"></script>
```

（`play-data.js` 供 Task 8 的 `loadData()` 用；它需要 `window.DiagEngine`，确认 `engine.js` 的标签在这两个之前。）

- [ ] **Step 2: 写 `play/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>今天练一练</title>
<meta name="theme-color" content="#0f6e62">
<meta name="robots" content="noindex">
<link rel="manifest" href="../manifest.webmanifest">
<link rel="apple-touch-icon" href="../assets/icons/apple-touch-icon.png">
<link rel="stylesheet" href="../assets/site.css">
<link rel="stylesheet" href="style.css">
</head>
<body class="page-play">
<main class="play" id="root" aria-live="polite"></main>
<script src="../diagnose/engine.js"></script>
<script src="../assets/children.js"></script>
<script src="../assets/figure.js"></script>
<script src="../assets/play-data.js"></script>
<script src="dispatch.js"></script>
<script src="session.js"></script>
<script src="app.js"></script>
<script>
/* 只注册 Service Worker，不引入 assets/pwa.js——它会往孩子端注入「添加到桌面」banner。 */
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
  window.addEventListener('load', function () { navigator.serviceWorker.register('../sw.js', { scope: '../' }).catch(function () {}); });
}
</script>
</body>
</html>
```

- [ ] **Step 3: 写 `play/style.css`**

```css
/* 孩子端视觉：只用 assets/site.css 的变量，字号比诊断页大一号，触摸目标 ≥64px。 */
.page-play { background: var(--bg); }
.play { max-width: 640px; margin: 0 auto; padding: 20px 16px 40px; font-size: 18px; line-height: 1.7; }
.play h1 { font-size: 1.5em; margin: 0 0 6px; }
.play button { min-height: 64px; font-size: 1.05em; border-radius: var(--radius); cursor: pointer; }
.play-card { background: var(--bg-elev); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); margin-bottom: 14px; }
.play-sub { color: var(--muted); margin: 0 0 14px; }
.play-go { display: block; width: 100%; background: var(--brand); color: var(--on-brand); border: 0; font-weight: 700; font-size: 1.25em; margin-top: 16px; }
.play-go:focus-visible, .play button:focus-visible, .play select:focus-visible, .play input:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.play-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.play-row label { color: var(--muted); font-size: 0.9em; }
.play-row select { min-height: 48px; font-size: 1em; padding: 6px 10px; border-radius: var(--radius-sm); border: 1px solid var(--line); background: var(--bg-elev); color: var(--text); }
.play-subjects { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.play-subject { min-height: 48px; padding: 6px 14px; border: 1px solid var(--line); background: var(--bg-elev); color: var(--text); border-radius: 999px; }
.play-subject.is-on { background: var(--brand-soft); border-color: var(--brand); color: var(--brand-strong); font-weight: 700; }
.play-progress { margin: 10px 0; }
.play-progress-bar { height: 14px; border-radius: 999px; background: var(--bg-muted); overflow: hidden; }
.play-progress-fill { height: 100%; background: var(--brand); border-radius: 999px; }
.play-progress-text { color: var(--muted); font-size: 0.9em; margin: 6px 0 0; }
.play-cells { display: flex; gap: 8px; margin-bottom: 12px; }
.play-cell { flex: 1; min-height: 44px; display: flex; align-items: center; justify-content: center; font-size: 1.3em; font-weight: 700; border-radius: var(--radius-sm); border: 2px solid var(--line); background: var(--bg-elev); color: var(--muted); }
.play-cell.is-ok { border-color: var(--ok); background: var(--ok-bg); color: var(--ok); }
.play-cell.is-again { border-color: var(--warn); background: var(--warn-bg); color: var(--warn); }
.play-topic { color: var(--muted); font-size: 0.9em; margin: 0 0 8px; }
.play-prompt { font-size: 1.3em; font-weight: 600; margin: 0 0 14px; white-space: pre-wrap; }
.play-figure { margin: 10px 0; color: var(--text); }
.play-figure svg { max-width: 100%; height: auto; }
.play-choices { display: flex; flex-direction: column; gap: 10px; }
.play-choices.is-icons { flex-direction: row; flex-wrap: wrap; }
.play-choice { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 64px; padding: 12px 14px; text-align: left; font-size: 1.1em; border: 2px solid var(--line); background: var(--bg-elev); color: var(--text); border-radius: var(--radius); }
.play-choice-key { flex: 0 0 auto; font-size: 1.1em; color: var(--brand-strong); }
.play-answer { width: 100%; min-height: 64px; font-size: 1.3em; padding: 12px 14px; border: 2px solid var(--line); border-radius: var(--radius); background: var(--bg-elev); color: var(--text); box-sizing: border-box; }
.play-verdict { font-size: 1.4em; font-weight: 700; margin: 0 0 10px; }
.play-card.is-ok { border-color: var(--ok); background: var(--ok-bg); }
.play-card.is-no { border-color: var(--bad); background: var(--bad-bg); }
.play-answer-is { font-size: 1.15em; font-weight: 600; }
.play-explain { color: var(--text); white-space: pre-wrap; }
.play-cheer { font-size: 1.15em; font-weight: 600; color: var(--ok); }
.play-results { list-style: none; padding: 0; margin: 12px 0; }
.play-results li { display: flex; justify-content: space-between; gap: 10px; align-items: center; min-height: 56px; padding: 8px 12px; border-radius: var(--radius-sm); margin-bottom: 6px; background: var(--bg-muted); }
.play-results li.is-ok { background: var(--ok-bg); }
.play-results li.is-again { background: var(--warn-bg); }
.play-result-tag { flex: 0 0 auto; font-weight: 700; }
.play-results li.is-ok .play-result-tag { color: var(--ok); }
.play-results li.is-again .play-result-tag { color: var(--warn); }
.play-note { margin-top: 16px; color: var(--muted); font-size: 0.85em; }
.play-note summary { min-height: 48px; display: flex; align-items: center; cursor: pointer; }
.play-note a { color: var(--brand-strong); }
a.play-go { display: block; text-align: center; text-decoration: none; line-height: 64px; }
.play-loading, .play-error { color: var(--muted); }
.play-error { color: var(--bad); font-weight: 600; }
.play-skip { min-height: 48px; padding: 6px 16px; border: 1px solid var(--line); background: var(--bg-elev); color: var(--muted); border-radius: 999px; font-size: 0.9em; }
.play-warn { color: var(--warn); background: var(--warn-bg); border-radius: var(--radius-sm); padding: 10px 12px; font-size: 0.9em; }
@media (max-width: 420px) { .play { padding: 14px 12px 32px; font-size: 17px; } .play-prompt { font-size: 1.2em; } }
```

- [ ] **Step 4: 写 `play/app.js`**

```js
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

  async function renderHome() {
    var child = CC.current();
    st.childId = child ? child.id : null;
    var box = el('div', 'play-home');
    if (!child) { setupCard(box, '还没有孩子档案', '请家长先建一份档案，选好教材再开始。'); show(box); return; }
    box.appendChild(childSwitcher());
    box.appendChild(subjectTabs());
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
    try { await PD.loadManifest(); }
    catch (e) { renderError('加载失败，请检查网络', boot); return; }
    var cur = CC.current();
    st.childId = cur ? cur.id : null;
    var s = new URLSearchParams(location.search).get('subject') || lsGet(SUBJECT_KEY) || 'math';
    st.subject = CC.SUBJECTS.indexOf(s) >= 0 ? s : 'math';
    renderHome();
  }

  window.__play = { state: st, boot: boot, start: start, commit: commit, retryNext: retryNext, renderHome: renderHome };
  boot();
})();
```

- [ ] **Step 5: 写 `tests/browser_harness.js`**

```js
'use strict';
/* 浏览器测试共用件：静态服务器 + headless Chrome + 裸 CDP。无 npm 依赖，需 Node 22+（全局 WebSocket/fetch）。 */
const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function until(fn, label) {
  const end = Date.now() + 20000;
  while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(100); }
  throw new Error('Timeout: ' + label);
}

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = [];
    ws.addEventListener('message', e => {
      const m = JSON.parse(e.data);
      if (m.id) {
        const p = this.pending.get(m.id); this.pending.delete(m.id);
        if (m.error) p.reject(new Error(p.method + ': ' + m.error.message)); else p.resolve(m.result);
      } else this.handlers.forEach(fn => fn(m));
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject, method }); this.ws.send(JSON.stringify({ id, method, params })); });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
}

/* opt.stubs: { '/assets/stats-config.js': 'window.CNM_STATS = {};' }
 * opt.notFound: ['/data/bank/questions/math/三上.json']  —— 按 pathname 匹配，忽略 ?v= 查询串
 * hits 记录每个请求的 pathname 与响应字节数，供首屏体积实测。 */
function serve(root, opt) {
  opt = opt || {};
  const stubs = opt.stubs || {};
  const notFound = opt.notFound || [];
  const hits = [];
  const server = http.createServer((req, res) => {
    let file = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (file.endsWith('/')) file += 'index.html';
    const rec = { url: req.url, file, bytes: 0 };
    hits.push(rec);
    if (notFound.indexOf(file) >= 0) { res.writeHead(404); res.end(); return; }
    if (Object.prototype.hasOwnProperty.call(stubs, file)) { res.setHeader('Content-Type', 'text/javascript'); res.end(stubs[file]); return; }
    const full = path.resolve(root, '.' + file);
    if (!full.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
    fs.readFile(full, (err, data) => {
      if (err) { res.writeHead(404); res.end(); return; }
      rec.bytes = data.length;
      res.setHeader('Content-Type', MIME[path.extname(full)] || 'application/octet-stream');
      res.end(data);
    });
  });
  return { server, hits };
}

async function launch(out) {
  const profile = path.join(out, 'profile');
  fs.mkdirSync(profile, { recursive: true });
  const chromePath = [process.env.CHROME,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    (process.env.LOCALAPPDATA || '') + '/Google/Chrome/Application/chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'
  ].find(p => p && fs.existsSync(p));
  if (!chromePath) throw new Error('找不到 Chrome/Chromium，请设置 CHROME 环境变量');
  const chrome = spawn(chromePath, [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-sync', '--disable-extensions', '--disable-component-update',
    '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'
  ], { stdio: ['ignore', 'ignore', fs.openSync(path.join(out, 'chrome.log'), 'w')] });
  const activePort = path.join(profile, 'DevToolsActivePort');
  await until(() => fs.existsSync(activePort), 'Chrome debugger');
  const port = fs.readFileSync(activePort, 'utf8').split('\n')[0];
  async function connect(targetId) {
    const tabs = await fetch('http://127.0.0.1:' + port + '/json').then(r => r.json());
    const tab = targetId ? tabs.find(t => t.id === targetId) : tabs.find(t => t.type === 'page');
    const ws = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', reject); });
    return new CDP(ws);
  }
  return { chrome, port, connect };
}

async function initPage(cdp, errors, viewport) {
  cdp.handlers.push(m => { if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails); });
  await cdp.send('Page.enable'); await cdp.send('Runtime.enable'); await cdp.send('Network.enable');
  await cdp.send('Network.setBypassServiceWorker', { bypass: true });
  await cdp.send('Emulation.setDeviceMetricsOverride', Object.assign({ width: 390, height: 844, deviceScaleFactor: 1, mobile: true }, viewport || {}));
}

module.exports = { serve, until, CDP, launch, initPage, MIME };
```

- [ ] **Step 6: 写失败测试 `tests/test_play_browser.js`（黄金路径）**

```js
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
  console.log('截图与日志：' + out);
  fs.writeFileSync(path.join(out, 'play-done.png'), Buffer.from((await page.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
})().catch(e => { console.error(e.stack); process.exitCode = 1; }).finally(async () => {
  if (page) page.ws.close();
  if (chrome) chrome.kill();
  await new Promise(resolve => server.close(resolve));
});
```

- [ ] **Step 7: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play_browser.js`
Expected: 若 Step 2-6 的文件都已写好，这一步应当**直接通过**；先故意把 `play/index.html` 里 `app.js` 的标签删掉跑一次，确认 FAIL 在 `Timeout: play ready`，再补回标签。这是为了证明测试真的在测孩子端而不是空跑。
（若已经通过，记录「测试对缺失入口敏感」的验证方式：临时改 `play/app.js` 第一行为 `throw new Error('x')` 跑一次应 FAIL，再改回。）

- [ ] **Step 8: 跑测试确认通过 + 诊断页回归**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play_browser.js && node tests/test_children_browser.js && node tests/test_play.js && node tests/test_play_data.js && node tests/test_bank_shards.js && node tests/test_engine.js && node tests/test_children.js`
Expected: 全部通过。`test_children_browser.js` 必须仍绿——`figureEl` 委托与档案表单改动都不能破坏备份往返。
诊断页此时**还没**切分片（Task 8 做），但已加载 `play-data.js`，确认 `diagnose/index.html` 没有 404：`node tests/test_children_browser.js` 的服务器只服务真实文件，若 script 路径写错会在 `errors` 里留下异常。

- [ ] **Step 9: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add assets/figure.js play/index.html play/style.css play/app.js diagnose/app.js diagnose/index.html tests/browser_harness.js tests/test_play_browser.js
git commit -m "feat(play): 孩子端四屏（首页/答题/反馈/完成）+ 共用 SVG 白名单 + 390×844 黄金路径实测"
```

---

## Task 7: 跳过、隐私模式与全部异常态

**Files:**
- Modify: `play/app.js`（加 `addSkipped` / `skipTopic` /  storage 探针 / 答题屏「先跳过」按钮 / `window.__play` 导出）
- Modify: `tests/test_play_browser.js`（追加边界实测）
- Modify: `tests/test_play.js`（追加跳过与存储键断言）

**Interfaces:**
- Consumes: Task 4 `pickTargets` 的 `skipped` 入参、Task 3 `CnmChildren.setVolume`、Task 6 的 `saveProgress` / `renderHome` / `window.__play`。
- Produces: `window.__play.skipTopic()`；存储键 `cnmPlay.skipped.v1.<childId>.<subject>` 的写入语义（去重追加）。

- [ ] **Step 1: 追加失败测试到 `tests/test_play.js`**

在 async IIFE 的收尾 `console.log` **之前**插入：

```js
  await atest('跳过键按 childId × subject 分开，去重追加，不与诊断页 seen 合并', async () => {
    const store = new Map();
    const localStorage = {
      getItem: k => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, v),
      removeItem: k => store.delete(k)
    };
    function lsGet(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
    function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
    const skipKey = (id, s) => 'cnmPlay.skipped.v1.' + id + '.' + s;
    const seenKey = id => 'cnmPlay.seen.v1.' + id;
    function addSkipped(id, s, tid) { const v = lsGet(skipKey(id, s)) || []; if (v.indexOf(tid) < 0) { v.push(tid); lsSet(skipKey(id, s), v); } }
    addSkipped('c1', 'math', 't2'); addSkipped('c1', 'math', 't2'); addSkipped('c1', 'math', 't4');
    addSkipped('c2', 'math', 't9'); addSkipped('c1', 'chinese', 't7');
    assert.deepEqual(lsGet(skipKey('c1', 'math')), ['t2', 't4']);
    assert.deepEqual(lsGet(skipKey('c2', 'math')), ['t9']);
    assert.deepEqual(lsGet(skipKey('c1', 'chinese')), ['t7']);
    lsSet(seenKey('c1'), ['q1']);
    lsSet('cnmDiagnose.seen.v1', ['q2']);
    assert.deepEqual(lsGet(seenKey('c1')), ['q1'], '孩子端 seen 独立');
    assert.deepEqual(lsGet('cnmDiagnose.seen.v1'), ['q2'], '家长端 seen 不被合并');
    const r = D.pickTargets({ topicIds: ['t1', 't2', 't3', 't4', 't5'], volumeOf: () => '三上', volume: '三上', status: {}, skipped: lsGet(skipKey('c1', 'math')), count: 5 });
    assert.deepEqual(r.targets, ['t1', 't3', 't5']);
    assert.deepEqual(r.deferred, ['t2', 't4']);
  });

  await atest('隐私模式：存储写入抛错时静默降级，会话内仍不重复', async () => {
    const localStorage = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('QuotaExceededError'); }, removeItem: () => {} };
    function lsGet(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
    function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
    assert.equal(lsGet('cnmPlay.seen.v1.c1'), null);
    assert.equal(lsSet('cnmPlay.seen.v1.c1', ['q1']), false);
    const topics = [mkTopic('p', '一上')];
    const qs = [mkQ('p_q11', 'p', 'standard'), mkQ('p_q12', 'p', 'challenge'), mkQ('p_q13', 'p', 'challenge'), mkQ('p_q14', 'p', 'challenge')];
    const data = fakeData({ p: '一上' }, { '一上': qs }, topics, []);
    const ctx = S.create(Object.assign({ data }, opts5, { avoid: lsGet('cnmPlay.seen.v1.c1') || [] }));
    await S.open(ctx, ['p']);
    const asked = [];
    while (ctx.item) { asked.push(ctx.item.question.id); await S.answer(ctx, 'correct', 'A'); }
    assert.equal(new Set(asked).size, asked.length, '引擎的 attempts 保证会话内不重复，与存储无关');
  });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play.js`
Expected: 这两条**应当直接通过**（它们锁的是 Task 4/5 已有的语义）。先确认通过，再在 Step 3 把它们要保护的接线加进 app.js。若失败，说明 Task 4/5 有回归，先修。

- [ ] **Step 3: 改 `play/app.js`**

在 `function skippedList(id, s) { … }` 之后插入：

```js
  function addSkipped(id, s, tid) {
    if (!id || !tid) return;
    var v = skippedList(id, s);
    if (v.indexOf(tid) < 0) { v.push(tid); lsSet(skipKey(id, s), v); }
  }
  function probeStorage() {
    try { localStorage.setItem('cnmPlay.probe', '1'); localStorage.removeItem('cnmPlay.probe'); return true; }
    catch (e) { return false; }
  }
```

在 `volumeEnd(wrap)` 之后插入：

```js
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
```

`renderAsk()` 里 `box.appendChild(card);` 之后、`show(box);` 之前插入：

```js
    var skip = el('button', 'play-skip', '先跳过'); skip.type = 'button';
    skip.addEventListener('click', skipTopic);
    box.appendChild(skip);
```

`renderHome()` 里 `box.appendChild(subjectTabs());` 之后插入：

```js
    if (!st.storageOk) {
      box.appendChild(el('p', 'play-warn', '这个浏览器不让保存数据（可能是隐私模式）。这次练习里不会重复出题，但关掉页面后练过哪些题就记不住了，请家长用普通窗口打开。'));
    }
```

`boot()` 里 `renderLoading();` 之后插入 `st.storageOk = probeStorage();`。

文件末尾的导出改成：

```js
  window.__play = { state: st, data: PD, boot: boot, start: start, commit: commit, retryNext: retryNext, renderHome: renderHome, skipTopic: skipTopic };
```

`data: PD` 是给浏览器测试用的：`PD` 是 IIFE 私有变量，测试够不到，必须从这里导出。

- [ ] **Step 4: 追加边界实测到 `tests/test_play_browser.js`**

在黄金路径那一行 `console.log('PASS: 黄金路径 …')` **之后**、`console.log('截图与日志：' + out)` 之前插入：

```js
  // ---- 跳过：记入本册末尾、不改变该点状态、其余目标下次仍在队列 ----
  await page.eval('document.querySelector(".play-go").click()');
  await until(() => page.eval('!!document.querySelector(".play-prompt")'), 'ask again');
  const skipId = await page.eval('__play.state.ctx.item.topicId');
  const before = await page.eval('JSON.stringify(CnmChildren.latestStatus(__play.state.childId, "math"))');
  await page.eval('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "先跳过").click()');
  await until(() => page.eval('!!document.querySelector(".play-title")'), 'home after skip');
  assert.ok(await page.eval(`JSON.parse(localStorage.getItem('cnmPlay.skipped.v1.' + __play.state.childId + '.math')).includes(${JSON.stringify(skipId)})`));
  const after = await page.eval('JSON.stringify(CnmChildren.latestStatus(__play.state.childId, "math"))');
  assert.equal(JSON.parse(after)[skipId], undefined, '跳过不改变该点状态');
  assert.equal(JSON.parse(before)[skipId], undefined);
  const targetsNow = await page.eval(`(() => {
    const st = __play.state;
    const skipped = JSON.parse(localStorage.getItem('cnmPlay.skipped.v1.' + st.childId + '.math')) || [];
    return CnmPlayDispatch.pickTargets({ topicIds: st.topicIds, volumeOf: __play.data.volumeOf, volume: st.cfg.volume,
      status: CnmChildren.latestStatus(st.childId, 'math'), skipped: skipped, count: 5 }).targets;
  })()`);
  assert.equal(targetsNow.indexOf(skipId), -1, '跳过的点不在本次派题里');

  // ---- 切换孩子：seen / skipped / 档案全部按新 childId 读 ----
  await page.eval(`(() => { const r = CnmChildren.add({ name: '小禾', grade: '五年级', textbook: '人教版', subjects: { math: { edition: 'cn_renjiao', volume: '五上', confirm: 5 } } }); if (!r.ok) throw new Error(r.error); })()`);
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
  assert.ok(await page.eval('document.querySelector("a.play-go").href.includes("../children/?from=play&subject=physics")'));
  assert.equal(await page.eval('!!document.querySelector(".play-prompt")'), false);
  await page.eval('Array.from(document.querySelectorAll(".play-subject")).find(b => b.textContent === "数学").click()');
  await playReady();

  // ---- 隐私模式：存储抛错时首页给家长提示，仍能练 ----
  await page.eval(`window.__origSet = Storage.prototype.setItem; window.__origGet = Storage.prototype.getItem;
    Storage.prototype.setItem = function () { throw new DOMException('Quota', 'QuotaExceededError'); };
    Storage.prototype.getItem = function () { throw new DOMException('denied', 'SecurityError'); };`);
  await page.eval('__play.boot()');
  await playReady();
  await until(() => page.eval('!!document.querySelector(".play-warn")'), 'privacy warning');
  assert.ok(await page.eval('document.querySelector(".play-warn").textContent.includes("隐私模式")'));
  await page.eval('Storage.prototype.setItem = window.__origSet; Storage.prototype.getItem = window.__origGet;');

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
```

404 是怎么造出来的：测试文件顶部把 `const notFound = []` 传给 `serve`，harness 里 `const notFound = opt.notFound || []` 持有**同一个数组引用**，所以运行中 `notFound.push(...)` 立即生效，`notFound.length = 0` 立即恢复，不用重启服务器。匹配的是 `decodeURIComponent` 后的 pathname，忽略 `?v=` 查询串，所以中文册名照写。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play.js && node tests/test_play_browser.js`
Expected: `test_play.js` 21 passed；`test_play_browser.js` 两行 PASS，退出码 0。
若册末衔接失败，检查 `CnmChildren.saveRecord` 的 fixture 记录是否被 `MAX_RECORDS=40` 截断，以及 `latestStatus` 是否按 `savedAt` 排序把 fixture 排到了最前（fixture 的 savedAt 由 saveRecord 写成当前时间，一定最新）。

- [ ] **Step 6: 首屏体积实测并记录**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_play_browser.js`
在测试的 `homeHits` 断言之后追加一行体积汇总（Step 4 之外的小改动）：

```js
  const homeBytes = hits.filter(h => h.bytes > 0).reduce((n, h) => n + h.bytes, 0);
  console.log('首屏（首页 → 点开始 → 第一题）传输字节：' + homeBytes + ' B = ' + (homeBytes / 1048576).toFixed(2) + ' MB');
  assert.ok(homeBytes < 3 * 1048576, '首屏必须 < 3 MB，实测 ' + homeBytes);
```

注意 `hits.length = 0` 是在导航到 `/play/` 之前清的，所以这个合计只含孩子端请求。把实测数字写进 Task 9 的 CHANGELOG 条目，对照 spec §6.4 的预算（典型会话 ~1.25 MB / gzip ~0.52 MB）。**若超出预算，先查是不是多取了册，不要直接放宽断言。**

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add play/app.js tests/test_play.js tests/test_play_browser.js
git commit -m "feat(play): 先跳过排到册末 + 隐私模式提示 + 册末衔接与全部异常态实测"
```

---

## Task 8: 家长诊断页切到分片加载

**Files:**
- Modify: `diagnose/app.js:255-283`（`loadData()`）
- Test: `tests/test_diagnose_load.js`（新建，只测 loadData 的取片行为）

**Interfaces:**
- Consumes: Task 2 的 `CnmPlayData.create({base:'../data/bank/'})`；`E.subjectOf`、`E.buildGraph`、`E.parseChapter`。
- Produces: `D = {topics, deps, stdById, graph, tree, aliases, editions}` —— **形状与字段完全不变**，`diagnose/app.js` 其余 1600 行一行不动。

- [ ] **Step 1: 写失败测试 `tests/test_diagnose_load.js`**

`loadData()` 是 IIFE 私有函数，无法直接 require。用 `vm` 抽出函数体来测：把 `diagnose/app.js` 里 `async function loadData() { … }` 到下一个 `function buildTree` 之前的源码切出来，在注入 `fetch` / `E` / `subject` / `D` / `location` / `editionSel` 的上下文里跑。

```js
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
  const ctx = {
    E, subject, D: null, editionSel: '', location: { search: '' }, URLSearchParams,
    CnmPlayData: PD,
    buildTree: () => ({}),
    fetch: async url => {
      calls.push(url);
      const rel = url.replace(/^\.\.\//, '').split('?')[0];
      const full = path.join(ROOT, rel);
      if (!fs.existsSync(full)) return { ok: false, status: 404 };
      return { ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(full, 'utf8')) };
    },
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
  await test('english：九年级全册 与 九全 归一后不产生重复分片', async () => {
    const { D, calls } = await run('english');
    const shardCalls = calls.filter(u => u.includes('data/bank/questions/english/'));
    assert.equal(new Set(shardCalls).size, shardCalls.length);
    assert.ok(shardCalls.some(u => u.includes('九年级全册.json')));
    assert.equal(D.graph.hasBank, true);
  });
  await test('?edition= 仍被采纳，选择器逻辑不受影响', async () => {
    const calls = [];
    const ctx = {
      E, subject: 'math', D: null, editionSel: '', location: { search: '?edition=cn_beishida' }, URLSearchParams,
      CnmPlayData: PD, buildTree: () => ({}),
      fetch: async url => { calls.push(url); const full = path.join(ROOT, url.replace(/^\.\.\//, '').split('?')[0]);
        if (!fs.existsSync(full)) return { ok: false, status: 404 };
        return { ok: true, status: 200, json: async () => JSON.parse(fs.readFileSync(full, 'utf8')) }; },
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_diagnose_load.js`
Expected: FAIL —— 现在的 `loadData()` 里没有 `CnmPlayData`，且第一条断言 `calls.some(u => u.includes('data/questions.json'))` 为 true。

- [ ] **Step 3: 改 `diagnose/app.js` 的 `loadData()`**

把 `:255-283` 整体替换为（**`buildTree` 及其后一行不动**）：

```js
  async function loadData() {
    const data = CnmPlayData.create({ base: '../data/bank/' });
    const urls = ['../data/cn-curriculum-standards.json', '../data/id-aliases.json'];
    const rs = await Promise.all(urls.map(function (u) { return fetch(u); }));
    rs.forEach(function (r, i) { if (!r.ok) throw new Error(urls[i] + ' → HTTP ' + r.status); });
    const js = await Promise.all(rs.map(function (r) { return r.json(); }));
    await data.loadManifest();
    const skeleton = await data.loadGraph(subject);
    // 按学科整取全部册：loadData 只在初始化跑一次，选择器变化不重载数据，
    // 按当前选择器挑册会让之后每次切换都选到空图（plan D4）。整包 16.95 MB → 单学科最大 3.84 MB。
    const volumes = data.volumesOf(subject);
    for (const v of volumes) await data.loadQuestions(subject, v);
    const topics = skeleton.topics;
    const deps = skeleton.deps;
    const stdById = {};
    js[0].items.forEach(function (x) { stdById[x.id] = x; });
    const graph = data.buildGraphFor(subject, volumes, null);   // null = 不过滤题型，家长端仍能用 short/self
    let editions = { versions: [] };
    try {
      const er = await fetch('../data/editions/registry.json');
      if (er.ok) editions = await er.json();
    } catch (e) { editions = { versions: [] }; }
    D = { topics: topics, deps: deps, stdById: stdById, graph: graph, tree: buildTree(topics), aliases: (js[1] && js[1].aliases) || {}, editions: editions };
    const eq = new URLSearchParams(location.search).get('edition');
    if (eq && editions.versions && editions.versions.some(function (v) { return v.id === eq; })) editionSel = eq;
  }
```

确认 `diagnose/index.html` 已在 `app.js` 之前加载 `../assets/play-data.js`（Task 6 Step 1 已加），且 `engine.js` 在 `play-data.js` 之前。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node tests/test_diagnose_load.js`
Expected: `4 passed, 0 failed`。

- [ ] **Step 5: 诊断页浏览器冒烟（手动，必须做）**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node -e "const http=require('http'),fs=require('fs'),path=require('path');const root=process.cwd();const MIME={'.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'};http.createServer((q,s)=>{let f=decodeURIComponent(new URL(q.url,'http://x').pathname);if(f.endsWith('/'))f+='index.html';if(f==='/assets/stats-config.js'){s.setHeader('Content-Type','text/javascript');s.end('window.CNM_STATS = {};');return;}const p=path.resolve(root,'.'+f);fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);s.end();return;}s.setHeader('Content-Type',MIME[path.extname(p)]||'application/octet-stream');s.end(d);});}).listen(8123,'127.0.0.1',()=>console.log('http://127.0.0.1:8123'));"`
（后台跑，`run_in_background: true`。）然后用 browser-use MCP 打开 `http://127.0.0.1:8123/diagnose/?subject=math`，逐项确认：
1. 页面正常渲染，无控制台异常（`list_console_messages`）。
2. 网络请求里**没有** `data/questions.json`，有 `data/bank/graph/math.json` 与 23 个 `data/bank/questions/math/*.json`（`list_network_requests`）。
3. 切换学段/年级/册选择器后列表仍有内容（这是 D4 要防的退化）。
4. 整章浏览模式能列出章节；筛查模式能进入。
5. 随便选一个知识点跑一次诊断，答对答错各一次，结果页与路径图正常。
6. 换 `?subject=english` 与 `?subject=chinese` 各重复 1-3。
7. 带图题（`figure`）仍正常显示——验证 D9 的委托没退化。可搜 `?target=` 一个带 figure 的点，或在整章里找。

**若任何一项失败，停下修复，不要继续 Task 9。** 测完把后台服务器停掉（`TaskStop`）。

- [ ] **Step 6: 跑全部闸门**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 STRICT_STANDARDS=1 python scripts/validate.py && PYTHONIOENCODING=utf-8 python scripts/verify_questions.py && PYTHONIOENCODING=utf-8 python scripts/version_gate.py && node tests/test_engine.js && node tests/test_children.js && node tests/test_children_browser.js && node tests/test_bank_shards.js && node tests/test_play_data.js && node tests/test_play.js && node tests/test_play_browser.js && node tests/test_diagnose_load.js`
Expected: 全部通过。

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add diagnose/app.js tests/test_diagnose_load.js
git commit -m "perf(diagnose): loadData 切到学科骨架 + 册分片，整包 16.95 MB 不再下载"
```

---

## Task 9: 离线缓存、体积测量脚本、文档与总回归

**Files:**
- Modify: `sw.js:6`（VERSION）、`:10-42`（SHELL）、`:44-50`（DATA）
- Create: `scripts/shard_budget.py`
- Modify: `docs/pwa.md`（文末追加）、`CHANGELOG.md`（追加本轮条目）
- Modify: `docs/superpowers/specs/2026-11-08-child-play-ui-design.md`（§10 测量脚本表的状态列）

**Interfaces:**
- Consumes: Task 1-8 的全部产物与实测数字。
- Produces: `scripts/shard_budget.py` → `_scratch/shard_budget.txt`；`sw.js` v6 缓存清单。

- [ ] **Step 1: 写 `scripts/shard_budget.py`**

`_scratch/_s185_shard.py` 用的是自己的正则 `vol_of`（与 `norm_vol` 不一致），提升时改成读**实际产物**，口径才与线上一致：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体积预算：骨架 / 单册分片 / 典型会话首屏，以及扩到 60 题每点后的推算。

读 data/bank/ 的实际产物（口径与线上完全一致），对照 spec §6.4 的预算表。
结果写 _scratch/shard_budget.txt（UTF-8），不打印中文到 stdout。

  python scripts/shard_budget.py
  python scripts/shard_budget.py --per-point 60
"""
from __future__ import annotations

import gzip
import io
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "data", "bank")
MB = 1048576.0


def load(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def bank_bytes(rel):
    with io.open(os.path.join(BANK, rel), "rb") as f:
        raw = f.read()
    return len(raw), len(gzip.compress(raw, 9))


def main():
    per_point = 60
    if "--per-point" in sys.argv:
        per_point = int(sys.argv[sys.argv.index("--per-point") + 1])
    m = load("data/bank/manifest.json")
    topics = load("data/topics.json")
    questions = load("data/questions.json")
    out = ["buildId=%s 真源 topics=%d questions=%d" % (m["buildId"], len(topics), len(questions)), ""]

    out.append("--- 骨架（按学科整取，不随题库扩张增长）---")
    sk = []
    for s in sorted(m["subjects"]):
        raw, gz = bank_bytes(m["subjects"][s]["graphFile"])
        sk.append((raw, gz, s))
        out.append("%-10s topics=%4d deps=%5d  %7.1f KB  gzip %6.1f KB" % (
            s, m["subjects"][s]["topics"], len(load("data/bank/" + m["subjects"][s]["graphFile"])["deps"]), raw / 1024.0, gz / 1024.0))
    out.append("骨架最大：%s %.1f KB（gzip %.1f KB）" % (max(sk)[2], max(sk)[0] / 1024.0, max(sk)[1] / 1024.0))
    out.append("")

    out.append("--- 单册题库分片 ---")
    sh = []
    for s in sorted(m["subjects"]):
        for v, info in m["subjects"][s]["shards"].items():
            raw, gz = bank_bytes(info["file"])
            assert raw == info["bytes"], "manifest bytes 与实际不符：%s/%s" % (s, v)
            sh.append((raw, gz, s, v, info["questions"], info["topics"]))
    sh.sort(reverse=True)
    out.append("分片数=%d 最大=%.2f MB 中位=%.2f MB 合计=%.2f MB" % (
        len(sh), sh[0][0] / MB, statistics.median(x[0] for x in sh) / MB, sum(x[0] for x in sh) / MB))
    out.append("top 12：")
    for raw, gz, s, v, nq, nt in sh[:12]:
        out.append("  %-10s %-12s topics=%4d q=%5d %7.1f KB gzip %6.1f KB" % (s, v, nt, nq, raw / 1024.0, gz / 1024.0))
    out.append("")

    out.append("--- 典型会话首屏（manifest + 学科骨架 + 1 个顺序表 + 1 册题库）---")
    man_raw, man_gz = bank_bytes("manifest.json")
    for s in sorted(m["subjects"]):
        biggest = max(m["subjects"][s]["shards"].items(), key=lambda kv: kv[1]["bytes"])
        order_rel = None
        for ed in m["editions"].values():
            if s in ed["subjects"]:
                order_rel = ed["subjects"][s]["orderFile"]
                break
        o_raw, o_gz = bank_bytes(order_rel) if order_rel else (0, 0)
        g_raw, g_gz = bank_bytes(m["subjects"][s]["graphFile"])
        q_raw, q_gz = bank_bytes(biggest[1]["file"])
        total = man_raw + g_raw + o_raw + q_raw
        total_gz = man_gz + g_gz + o_gz + q_gz
        out.append("%-10s 最坏册=%-12s 合计 %6.2f MB  gzip %5.2f MB" % (s, biggest[0], total / MB, total_gz / MB))
    out.append("")

    out.append("--- 扩到 %d 题/点 后的推算 ---" % per_point)
    cur = len(questions) / float(len(topics))
    factor = per_point / cur
    out.append("当前 %.1f 题/点，放大系数 %.2fx" % (cur, factor))
    out.append("最大册分片：%.2f MB → %.2f MB（gzip %.2f MB → %.2f MB）" % (
        sh[0][0] / MB, sh[0][0] * factor / MB, sh[0][1] / MB, sh[0][1] * factor / MB))
    out.append("骨架不变（不含题库），manifest 随分片计量线性微增")
    os.makedirs(os.path.join(ROOT, "_scratch"), exist_ok=True)
    with io.open(os.path.join(ROOT, "_scratch", "shard_budget.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("shards=%d subjects=%d factor=%.2f -> _scratch/shard_budget.txt" % (len(sh), len(m["subjects"]), factor))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 跑体积脚本并核对 spec §6.4**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 python scripts/shard_budget.py`
然后 Read `_scratch/shard_budget.txt`。
Expected: 骨架最大 chinese 约 **900.9 KB**（gzip 约 180 KB）、最大册分片 physics 必修一约 **0.35 MB**、分片数 **117**。
把「典型会话首屏」那一节的实测值与 Task 7 Step 6 的浏览器实测值并列记下来，写进 Step 5 的 CHANGELOG。两者口径不同（脚本算最坏册，浏览器算实际三上），**不要混为一谈**。

- [ ] **Step 3: 改 `sw.js`**

`:6` 的 `var VERSION = 'v5';` 改成 `var VERSION = 'v6';`。
SHELL 数组里 `'children/history.js',` 之后插入：

```js
  'play/',
  'play/app.js',
  'play/dispatch.js',
  'play/session.js',
  'play/style.css',
```

`'assets/children.js',` 之后插入：

```js
  'assets/play-data.js',
  'assets/figure.js',
```

DATA 数组里 `'data/id-aliases.json'` 之后加一行 `'data/bank/manifest.json'`（注意给前一行补逗号）。
**`data/questions.json` 留在 DATA 里不要删**：`assets/home.js` 与 `explore/app.js` 仍在整包取它，删了会让首页与图谱页离线失效。在 DATA 数组上方加一行注释说明：

```js
// questions.json 仍被 assets/home.js 与 explore/app.js 整包使用；diagnose 与 play 已改走 data/bank/ 分片。
// 分片本身不在 DATA 里预缓存：117 册全预取会把安装流量放大，运行时由 staleWhileRevalidate 按需缓存。
```

- [ ] **Step 4: 验证 Service Worker 清单齐全**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && node -e "const fs=require('fs');const s=fs.readFileSync('sw.js','utf8');const list=s.slice(s.indexOf('var SHELL = ['),s.indexOf('function abs('));const paths=Array.from(list.matchAll(/'([^']+)'/g)).map(m=>m[1]).filter(p=>p!=='cnm-pwa-');const missing=paths.filter(p=>!fs.existsSync(p.endsWith('/')?p+'index.html':p));console.log('entries='+paths.length+' missing='+JSON.stringify(missing));process.exit(missing.length?1:0);"`
Expected: `missing=[]`，退出码 0。若缺文件，说明前面某个任务漏建了产物。

- [ ] **Step 5: 追加 `docs/pwa.md` 与 `CHANGELOG.md`**

在 `docs/pwa.md` **文末追加**：

```markdown

## 孩子端 /play/ 的不重样记忆（设备级）

孩子端把「已经出过的题」记在 `localStorage` 的 `cnmPlay.seen.v1.<孩子 id>` 里，按孩子分开。
家长诊断页用的是另一个键 `cnmDiagnose.seen.v1`，两者**不合并**——合并会让家长的精细检查消耗孩子的题。
「先跳过」的知识点记在 `cnmPlay.skipped.v1.<孩子 id>.<学科>`，排到本册末尾，本册其他点取尽后才放回。

边界：

- 全部保存在**当前设备的当前浏览器**里，不上传、没有账号、不做云同步。
- 清除浏览器数据、换设备、换浏览器 → 记忆归零，题目会重新出。换设备前请在档案页「导出全部档案」，
  但**备份只含档案与诊断记录，不含 seen / skipped**，所以不重样进度无法随备份迁移。
- 隐私模式 / 存储被禁用 → 首页给家长提示；本次会话内引擎仍保证不重复出题，跨会话记忆失效。
- 同一设备上两个孩子各自独立，互不消耗对方的题。

离线缓存：`sw.js` 的 SHELL 含 `play/` 全部文件，DATA 含 `data/bank/manifest.json`；
骨架与册分片在第一次访问时由 staleWhileRevalidate 缓存，之后断网可用。
分片 URL 带 `?v=<buildId>`，真源变化 → buildId 变化 → 浏览器与 CDN 自动取新片。
```

在 `CHANGELOG.md` 顶部既有格式之后追加本轮条目（日期用实际执行日）：

```markdown
## 2026-11-09 — 孩子端 /play/ 自动派题 UI + 题库分片

- **新增 `/play/`**：系统按教材顺序自动派 5 个知识点，只出 choice / numeric，四屏（首页 / 答题 / 反馈 / 完成），
  触摸目标 ≥64px，无导航栏、无广告 banner、无倒计时、不显示诊断术语。引擎 `diagnose/engine.js` **一行未改**。
- **档案扩展**：`subjects[学科] = { edition, volume, confirm }`，confirm 开放 2 / 3 / 5（默认 3）。
  备份 `version` 升 2，version 1 仍可导入；旧档案无 `subjects` 时孩子端出「请家长先设置教材」卡片。
- **数据分片**：`scripts/build_bank_shards.py` 产出 `data/bank/` 共 225 个文件（8 学科骨架 + 117 册题库 + 99 版本×学科顺序表 + manifest），
  全部进 git，静态托管直接可用。真源四文件只读不写。
- **懒加载**：骨架按学科整取，题库按册懒取。3504 个点全部有 `diagnostic_question`，`E.buildGraph` 会给未加载册的点塞
  `type:'legacy'` 兜底题、`isTestable` 恒真，所以钩子拦的是 `nextItem` 的**返回值**而不是「bank 是否非空」——
  否则孩子会被派到兜底题。循环用「已取册集合 / 已确认无可出题点集合只增不减」保证终止，不用固定轮次上限（先修闭包实测最多跨 20 册）。
- **家长诊断页**：`loadData()` 改走同一套分片，整包 `data/questions.json`（compact 16.95 MB）不再下载，
  单学科最大 3.84 MB。按学科整取全部册而不是按选择器挑册——`loadData` 只在初始化跑一次，选择器变化不重载数据。
  其余逻辑、整章浏览、筛查模式一行未动。
- **实测数字**：分片 117 册、顺序表 99 个、骨架最大 chinese <填 Step 2 实测> KB、最大册分片 <填实测> MB、
  孩子端首屏（首页→第一题）浏览器实测 <填 Task 7 Step 6 实测> MB。测量脚本 `scripts/shard_budget.py`、`scripts/prereq_closure.py` 可复跑。
- **测试**：新增 `test_bank_shards.js` / `test_play_data.js` / `test_play.js` / `test_diagnose_load.js` / `test_play_browser.js`（390×844 实测黄金路径 + 全部边界）。
  `tests/test_children_browser.js` 补上 Windows Chrome 候选路径（此前本机根本跑不起来）。
- **离线**：`sw.js` v5 → v6，SHELL 加 play/ 与两个新 assets，DATA 加 manifest。`data/questions.json` 保留（home.js / explore 仍在用）。
```

**把三处 `<填实测>` 替换成 Step 2 与 Task 7 Step 6 的真实数字**，不得留占位。

- [ ] **Step 6: 更新 spec §10 的测量脚本状态列**

把 `docs/superpowers/specs/2026-11-08-child-play-ui-design.md` §10 表格里这三行的「状态」列改掉：

| 用途 | 原临时脚本 | 状态 |
| --- | --- | --- |
| 分片体积 | `_s185_shard.py` | **已提升 → `scripts/shard_budget.py`**（改读实际产物，口径与线上一致） |
| 先修闭包 | `_s190_closure.py` / `_s192_clo5.py` | **原临时脚本已随 `_scratch` 清理消失，按 §2 口径重写为 `scripts/prereq_closure.py`** |
| 骨架体积 | `_s191_skeleton.py` | **已并入 `scripts/shard_budget.py`** |

并在 §10 表格下方加一行：`实现与原 spec 的 11 处偏差及理由见 docs/superpowers/plans/2026-11-09-child-play-ui.md 的「与 spec 的偏差与理由」。`

- [ ] **Step 7: 总回归（全部闸门 + 全部测试 + 构建幂等）**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && PYTHONIOENCODING=utf-8 python scripts/build_bank_shards.py --check && PYTHONIOENCODING=utf-8 STRICT_STANDARDS=1 python scripts/validate.py && PYTHONIOENCODING=utf-8 python scripts/verify_questions.py && PYTHONIOENCODING=utf-8 python scripts/version_gate.py && node tests/test_engine.js && node tests/test_children.js && node tests/test_children_browser.js && node tests/test_bank_shards.js && node tests/test_play_data.js && node tests/test_play.js && node tests/test_play_browser.js && node tests/test_diagnose_load.js`
Expected: 全部通过，`--check` 报 `changed=0 stale=0`。题库仍 **35143**、知识点 **3504**（本计划全程不改真源）。

- [ ] **Step 8: 确认工作树只含本计划的改动**

Run: `cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy" && git status --short && git log --oneline -10`
Expected: 工作树干净；能看到 Task 1-8 的 8 个提交。若出现不属于本计划的文件，**不要 `git add -A`**，逐个核对来源（用户长期约束：只 stage 自己的路径）。

- [ ] **Step 9: Commit**

```bash
cd "C:/Users/Bobo/WorkBuddy/2026-11-01-10-05-32/cn-math-taxonomy"
git add sw.js scripts/shard_budget.py docs/pwa.md CHANGELOG.md docs/superpowers/specs/2026-11-08-child-play-ui-design.md
git commit -m "feat(play): sw v6 离线清单 + 体积/闭包测量脚本 + 文档与总回归"
```

- [ ] **Step 10: 向用户报告并请求 push 确认**

报告内容：9 个本地提交、全部闸门与测试绿、首屏实测体积、题库仍 35143。
**明确询问是否 push**（用户长期约束「改文件可以，push 要确认」）。此前还有两个未 push 的提交 `677e295`（spec）与 `5bad929`（摘除 826 + 回捞 37），一并列出供用户决定推送范围。**未经确认不得 push。**

---

## Self-Review

**1. Spec coverage**

| spec 节 | 要求 | 落在哪个任务 |
| --- | --- | --- |
| §3 | 引擎完全不改 | 全局约束 + Task 5 Step 4 的「不要改引擎」+ Task 9 Step 7 回归 |
| §3 | 新增 7 个文件 | Task 1（builder）、2（play-data）、6（index/app/style）、4+5（dispatch/session 拆分，D5）、1+6+7（三个测试文件） |
| §3 | 修改 4 个文件 | Task 3（children.js / page.js / index.html）、Task 8（diagnose loadData） |
| §4 | subjects 字段、edition/volume/confirm 取值、旧档案兼容 | Task 3 Step 1/3 |
| §4 | 备份 v2、v1 可导入 | Task 3 Step 1/3 + 新测试「version 1 备份仍可导入」 |
| §4 | 无配置 → 「请家长先设置教材」卡片 + 链到 `../children/?from=play` | Task 6 `setupCard` + Task 7 边界实测 |
| §5.1 | 六步派题、教材顺序、跳过 mastered、weak/shaky 不跳、limit 公式、题型过滤 | Task 4（1-5 步）+ Task 5（第 6 步 createSession）+ Task 2（题型过滤） |
| §5.2 | 跳过按钮、设备级键、排到本册末尾、不写记录不改状态 | Task 4 `pickTargets` + Task 7 Step 3/4 |
| §5.3 | 册末衔接、册顺序由 registry 首次出现决定、写进 manifest | Task 1（manifest volumes）+ Task 6 `volumeEnd` + Task 7 实测 |
| §5.4 | 四屏、≥64px、无术语、无倒计时、答对 1 秒自动跳、答错需「我懂了」 | Task 6 Step 3/4 + Step 6 断言 |
| §5.5 | limit 用尽 → 「明天继续」，不显示「未测」 | Task 6 `renderDone` + Task 5 测试 + Task 6 浏览器断言 |
| §6.1 | 产物、norm_vol、manifest schema、compact、分片含全部题型 | Task 1（+ D6 顺序表、D11 四文件哈希） |
| §6.2 | 加载器五个方法 | Task 2（+ `loadOrder` / `volumesOf` / `editionsFor` / `editionVolumes`） |
| §6.3 | 懒加载钩子 | Task 5（D1/D2 修正版） |
| §6.4 | 体积预算、buildId 查询串 | Task 2 `versioned()` + Task 7 Step 6 + Task 9 Step 1/2 |
| §6.5 | diagnose loadData 切分片、不过滤题型 | Task 8（D4 修正版） |
| §7 | seen 键、设备级、与诊断页独立、边界写进首页与 docs/pwa.md | Task 6 `markSeen` / `parentNote` + Task 7 测试 + Task 9 Step 5 |
| §8 | 12 行异常表 | 无配置→Task 6；分片404/骨架失败→Task 2 测试 + Task 6 `renderError` + Task 7 实测；本册无可派点/最后一册→Task 6 `volumeEnd` + Task 7；limit→Task 6；懒加载无法推进→Task 5 D2；localStorage 不可用→Task 7；切换孩子→Task 6 `childSwitcher` + Task 7；旧档案→Task 3 + Task 6；分片与真源不一致→Task 1 测试 |
| §10 | test_bank_shards 6 条 | Task 1 Step 1（8 条，含可机判题下限与陈旧产物） |
| §10 | test_play 12 条 | Task 4（派题顺序/mastered/跳过/册末/记录格式）+ Task 5（懒加载不跳过/replay 一致/10 轮不重样/两孩子/题型过滤/limit）+ Task 7（跳过键/隐私模式） |
| §10 | 回归四闸门 + 孩子端两测试 | 每个任务的收尾 Step + Task 9 Step 7 |
| §10 | 浏览器实测 390×844、黄金路径、边界、首屏体积 | Task 6 Step 6 + Task 7 Step 4/6 |
| §10 | 三个测量脚本提升 | Task 5 Step 5（闭包）+ Task 9 Step 1（分片与骨架合并） |
| §11 | 明确不做 | 全局约束最后一条；代码里无账号/积分/倒计时/拍照/语音/per-edition 题库 |

无缺口。

**2. Placeholder scan**

全文扫描 `TBD` / `TODO` / `占位` / `Placeholder`：无遗留。Task 7 Step 4 的浏览器测试代码已直接用真实调用（`__play.data.volumeOf`、`__play.data.editionVolumes(...)`），`window.__play` 在 Step 3 就导出了 `data: PD`；404 用 harness 的 `notFound` 数组引用在运行中注入，不是「假设会失败」。Task 9 Step 5 的三处 `<填实测>` 是**执行时必须用真实测量值替换**的显式指令，不是遗留占位。其余每个代码步都给了完整可跑代码。

**3. Type consistency**

- `volumeOf(topicId) → string|null`：Task 2 定义，Task 4 `pickTargets`/`volumeProgress`、Task 5 `next`/`open`、Task 6/7 调用一致。
- `buildGraphFor(subject, loadedVolumes, types)`：Task 2 定义（`types=null` 不过滤），Task 5 `rebuild` 传 `ctx.types`，Task 8 传 `null`。一致。
- `ctx` 字段 `{data, subject, types, opts, loaded, unaskable, graph, session, item}`：Task 5 定义，Task 6 读 `ctx.item` / `ctx.session.targets` / `ctx.graph.byId`，Task 7 读 `ctx.item.topicId`。一致。
- `S.next(ctx)` / `S.answer(ctx, result, text)` / `S.summary(ctx)` / `S.open(ctx, targets)` / `S.create(opts)`：Task 5 定义，Task 6 `retryNext` 用 `S.next`、`commit` 用 `S.answer`、`renderDone` 用 `S.summary`。一致。
- `D.pickTargets` 返回 `{targets, fresh, deferred, exhausted}`：Task 4 定义，Task 6 用 `.targets` / `.exhausted`，Task 7 用 `.targets`。一致。
- `D.buildRecord({subject,label,session,summary})`：Task 4 定义，Task 6 `saveProgress` 调用一致。
- `CC.setVolume(childId, subject, volume) → boolean`：Task 3 定义，Task 6 `volumeEnd`、Task 7 实测调用一致。
- `CC.SUBJECTS` / `CC.CONFIRM_CHOICES`：Task 3 导出，Task 6 `subjectTabs` 用 `CC.SUBJECTS`。一致。
- 存储键：`cnmPlay.seen.v1.<childId>`、`cnmPlay.skipped.v1.<childId>.<subject>`、`cnmPlay.subject.v1`、探针键 `cnmPlay.probe`。Task 6 定义前三个，Task 7 加写入与探针，Task 9 文档写前两个。一致。
- `window.__play`：Task 6 导出 `{state,boot,start,commit,retryNext,renderHome}`，Task 7 追加 `skipTopic` 与 `data`。测试用的成员都在导出表里。
- `figureEl(svg)` → `CnmFigure.el(svg, cls)`：Task 6 Step 1 委托保留类名 `q-figure`，孩子端传 `play-figure`。一致。
- manifest 字段 `buildId / subjects.{graphFile,topics,volumes,shards.{file,topics,questions,bytes}} / editions.{label,subjects.{label,topics,volumes,orderFile}} / topicVolume`：Task 1 生成，Task 1 测试、Task 2 加载器、Task 3 档案表单、Task 9 体积脚本全部按这套字段读。一致。