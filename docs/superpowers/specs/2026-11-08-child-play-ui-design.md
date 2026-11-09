# 孩子端 /play/ 自动派题 UI — 设计规格

日期：2026-11-08
状态：待用户审阅
范围：四个子项目中的第 1 项（孩子端 UI）及其必需的前置改造（数据分片）。第 2/3/4 项见文末「下游子项目」。

## 1. 背景与已定决策

现有 `diagnose/` 是家长工具：进入要先选学段、搜索或按册浏览知识点、设题量上限和确认题数（[diagnose/app.js:543](../../../diagnose/app.js#L543)）。孩子无法独立使用。

用户 2026-11-08 定案（逐条对应本文各节）：

| 决策 | 选定值 | 影响节 |
| --- | --- | --- |
| 入口模型 | 独立 `/play/`，系统自动派题；`diagnose/` 保留给家长 | §3 |
| 派题策略 | 教材顺序优先（同步练习），跳过已掌握 | §5 |
| 进度游标 | 档案补设精确教材版本 + 册次 + 学科 | §4 |
| `confirm` | 开放 5，家长在档案里设（2/3/5） | §4、§9 |
| 每次练习量 | 5 个知识点，约 15–25 题 | §5 |
| 数据加载 | 按学科×册分片（方案 A） | §6 |
| 题型范围 | 孩子端只派 choice + numeric | §5、§9 |
| 不重样记忆 | 设备级 localStorage，10 次不重样为基础，不能省，全部知识点覆盖 | §7、§9 |

## 2. 问题陈述与实测约束

三个实测事实决定了设计形状，全部可复跑（脚本见 §10）。

**首屏体积**：`diagnose/app.js:263` 整包 fetch `data/questions.json`（compact 16.95 MB，磁盘 21.4 MB），再在内存按学科过滤。加 topics 2.47 MB、dependencies 0.85 MB，首屏 **20.28 MB**（均为 compact JSON 字节数）。扩池后不可行。

**先修闭包很大**：整册的先修闭包最多跨 20 册（chinese 九下 → 17 册 / 751 点）。即使只取 5 个目标点，闭包中位数仍是 9 册 / 134 点。**预加载闭包等于没分片**。

**图骨架很小**：topics + deps 按学科切，最大 chinese 900.9 KB（gzip 约 180 KB）。骨架不随题库扩张增长。

结论：**骨架按学科整取，题库按册懒取，且只在引擎真的要跨册时才取下一片。**

## 3. 架构

引擎 `diagnose/engine.js` **完全不改**。难度阶梯、回溯、判定语义全部沿用。

新增文件：

```
play/index.html                  孩子端入口（无 site-nav、无广告 banner）
play/app.js                      派题 + 四屏状态机 + 懒加载驱动
play/style.css                   儿童化视觉，沿用 assets/site.css 的 CSS 变量
assets/play-data.js              分片加载器（孩子端与家长诊断页共用）
scripts/build_bank_shards.py     构建分片 + manifest
tests/test_play.js               派题 / 衔接 / 不重样 / 懒加载
tests/test_bank_shards.js        分片完整性
```

修改文件：

```
assets/children.js               档案加 subjects 字段（§4）
children/page.js                 档案表单加学科 / 版本 / 册次 / confirm
children/index.html              表单新增控件
diagnose/app.js                  仅 loadData() 切到分片加载（§6）
```

`data/questions.json`、`data/topics.json`、`data/dependencies.json` 保持为**唯一真源**，分片是构建产物，进 git，静态托管直接可用，无后端。

## 4. 档案扩展

`assets/children.js` 的 `clean()` 增加 `subjects`，旧档案缺该字段时视为空对象，不报错：

```js
{
  name, grade, textbook,          // 现有字段，语义与取值不变
  subjects: {                     // 新增
    math:    { edition: 'cn_renjiao',  volume: '三上', confirm: 3 },
    chinese: { edition: 'cn_tongbian', volume: '三上', confirm: 3 }
  }
}
```

- `edition`：`data/editions/registry.json` 的真实版本 id（51 个）。档案表单按学科过滤可选版本（该版本的 `subjects` 含该学科才列出）。
- `volume`：`gen_registry.norm_vol()` 归一后的册键（`一上`…`九下`、`九全`、`高一`、`高二`、`必修一`…`选必四`）。表单按该版本该学科实际挂载的册列出。
- `confirm`：∈ {2, 3, 5}，默认 3。用 `E.clampConfirm` 校验。
- 现有 `textbook`（7 个粗值）保留不动，避免破坏旧档案和 `children/history` 页面；新逻辑一律读 `subjects[subject].edition`。

`exportBackup()` / `importBackup()` 的 `version` 升到 2，`clean()` 与校验函数接受 `subjects`；version 1 的备份仍可导入（`subjects` 补空）。

孩子端首页若当前孩子没有当前学科的配置，显示「请家长先设置教材」卡片 + 链到 `../children/?from=play`，不进入答题。

## 5. 派题逻辑与屏幕

### 5.1 派题（不存游标，每次推导）

不新增游标存储，避免游标与诊断记录不一致：

1. 读档案 `subjects[subject]` → `{ edition, volume, confirm }`。
2. 取 `registry.versions[edition].subjects[subject].topicIds`。**已实测该数组就是教材顺序**（`cn_renjiao` math：`cnm_p001 → cnm_p002 → … → cnm_017 七上`）。
3. 过滤：`norm_vol(topic.chapter 首段) === volume`，保持数组原顺序。
4. 用 `CnmChildren.latestStatus(childId, subject)` 取状态，**跳过 `mastered`**，再排除本册已跳过列表（§5.2）中的点。
5. 取前 **5 个**作为 `targets`。
6. `E.createSession(graph, targets, { limit: 5 * (confirm + 2), confirm, seed, avoid: seenList(childId) })`。

`weak` / `shaky` **不跳过**——不会的点会反复练到掌握，这是同步练习的预期行为。

`limit = 5 × (confirm + 2)`：confirm=3 → 25，confirm=5 → 35。留出答错与回溯的余量。引擎只夹 `limit ≥ 1`（[diagnose/engine.js:177](../../../diagnose/engine.js#L177)），`LIMIT_MAX = 30` 是 `diagnose/app.js` 的 UI 约束，不适用于 play。

**题型过滤**：交给引擎的 `graph.bank` 只含 `type ∈ {choice, numeric}` 的题。已实测 3504 个点全部有 ≥3 道可机判题，无零题点。short / self 仍留在真源与家长诊断页。

### 5.2 跳过按钮

孩子端答题屏有「先跳过」小按钮。点击后：
- 当前点立即停止出题，记入 `cnmPlay.skipped.v1.<childId>.<subject>`（数组，设备级）。
- 该点排到**本册末尾**：§5.1 第 4 步先排除已跳过点；当本册未跳过且未掌握的点取尽时，再把跳过列表按教材顺序放回队列。
- 跳过不写诊断记录，不改变该点状态。

### 5.3 册末衔接

本册既无可派点、跳过列表也已取尽 → 显示「这册学完了」→ 按该版本该学科的册顺序取下一册 → 回写档案 `subjects[subject].volume` → 回首页。若已是最后一册，显示「这一科学完了」并链到家长诊断页做综合复查。

册顺序**由数据决定，不在运行时猜测**：取该版本该学科 `registry.topicIds` 中每个册键的**首次出现顺序**。已实测这就是教材顺序，且天然处理各学科编码差异：

- `cn_renjiao/math` → 一上…九下、高一、高二、选必一、选必二、选必三（23 册）
- `cn_renjiao/english` → 三上…九下、九年级全册、必修一…必修三、选必一…选必四（21 册）
- `cn_renjiao/physics` → 八上、八下、九全、必修一…必修三、选必一…选必三（9 册）

构建时把该顺序写入 manifest 的 `volumes` 数组。

### 5.4 四屏

| 屏 | 内容 | 关键约束 |
| --- | --- | --- |
| 首页 | 当前孩子名 + 学科切换 + 「今天练 5 个知识点」+ 本册进度条 + 大「开始」按钮 | 无导航栏、无搜索、无广告 banner |
| 答题 | 大字题干、选项按钮触摸目标 ≥64px、顶部 5 个点的进度格子、「先跳过」 | 不显示「先修 / 不稳 / 置信度 / 拓扑」等术语 |
| 反馈 | 答对：绿勾 + 短鼓励，1 秒后自动下一题。答错：红叉 + 正确答案 + 一句解析 + 「我懂了」按钮才继续 | 无倒计时、无扣分 |
| 完成 | 5 个点各自结果（学会 / 还要练）+ 本册进度 + 「明天再来」 | 结果写入 `CnmChildren.saveRecord`，与诊断页共用记录格式 |

字号比诊断页大一号；沿用 `assets/site.css` 的 CSS 变量，不引入框架或新设计系统。

### 5.5 题量上限的处理

若 `limit` 用尽仍有点未判定，完成屏显示「今天练完了，剩下的明天继续」，**不显示「未测」**。这些点状态仍为 unknown，下次派题自然还在队列里，自愈。

## 6. 数据分片与懒加载

### 6.1 构建产物

`scripts/build_bank_shards.py` 读真源三文件 + registry，产出：

```
data/bank/manifest.json
data/bank/graph/<subject>.json          8 个：{ topics: [...], deps: [...] }
data/bank/questions/<subject>/<volume>.json   117 个：{ questions: [...] }
```

- 册键用 `gen_registry.norm_vol()` 归一（**必须**：数学写「七上」、语文写「七年级上册」、物理写「必修一」「九全」，不归一会产生重复分片）。
- `manifest.json`：`{ buildId, subjects: { <subject>: { graphFile, volumes: [有序册键], shards: { <volume>: { file, topics, questions, bytes } } } } }`。`volumes` 按 §5.3 的首次出现顺序。`buildId` 取真源三文件内容的 SHA-256 前 12 位，用于缓存失效。
- 分片内 JSON 用 `separators=(',', ':')`、`ensure_ascii=False`，无缩进。
- 分片只含 `choice` / `numeric`？**不**——分片含全部题型，题型过滤在客户端建图时做。这样家长诊断页仍能用 short/self，且分片不必因题型策略变化而重建。

### 6.2 加载器 `assets/play-data.js`

```
loadManifest()                       → manifest（内存缓存）
loadGraph(subject)                   → { topics, deps }（内存缓存）
loadQuestions(subject, volume)       → questions[]（内存缓存）
buildGraphFor(subject, loadedVolumes) → E.buildGraph(topics, deps, 已加载册的题，仅 choice/numeric)
volumeOf(topicId)                    → 册键（查 manifest 反查表）
```

### 6.3 懒加载钩子（关键设计）

`nextQuestion` 按 `session.stack` 顺序返回第一个 `!session.status[id]` 且 `isTestable` 的点（[diagnose/engine.js:330](../../../diagnose/engine.js#L330)）。`isTestable` 要求 `graph.bank[id]` 非空（[:135](../../../diagnose/engine.js#L135)）。**若题库未加载，该点会被静默跳过**——这是必须防住的行为退化。

因此 play/app.js 在**每次调用 `E.nextItem` 之前**执行：

```
ensureBankForNext(session):
  id = session.stack 中第一个 !session.status[id] 的点   // 不看 isTestable
  if id 不存在 → 返回（会话真的结束）
  if graph.bank[id] 非空 → 返回
  vol = volumeOf(id)
  await loadQuestions(subject, vol)
  graph = buildGraphFor(subject, 已加载册集合)
  session = E.replay(graph, session.targets, session.answers, opts)   // 确定性重建
  重复上述检查（最多 5 轮，防环）
```

这样只在引擎真的要跨册时才多取一片。典型会话（5 点同册、全对）= **1 片**。答错回溯才触发额外片，且只取实际走到的那一册。

`E.replay` 由作答记录确定性重建会话（[diagnose/engine.js:346](../../../diagnose/engine.js#L346)），seed 不变则重建后出题序列一致，已有 `tests/test_engine.js` 覆盖。

### 6.4 体积预算

| 项 | 现在 | 扩到 60 题/点后 | gzip 后 |
| --- | --- | --- | --- |
| 骨架（最大 chinese） | 900.9 KB | 900.9 KB（不随题库长） | ~180 KB |
| 单册题库（最大 physics 必修一） | 0.35 MB | 2.06 MB | ~0.34 MB |
| 典型会话首屏合计 | ~1.25 MB | ~2.96 MB | **~0.52 MB** |

骨架与分片都带 `buildId` 查询串，浏览器/CDN 缓存跨天复用；次日起增量只有新册。

### 6.5 家长诊断页

`diagnose/app.js` 的 `loadData()`（[:255](../../../diagnose/app.js#L255)）改为：`loadGraph(subject)` + 按当前 `editionSel` / 年级范围确定册集合 + `loadQuestions` 逐册取 + 建图时**不过滤题型**。其余逻辑不动。整章浏览、筛查模式因此仍可用。

## 7. 不重样记忆

- 键：`cnmPlay.seen.v1.<childId>`，值为已出题 id 数组。沿用 `diagnose/app.js:221` 的 `markSeen` 语义（去重追加）。
- **设备级 localStorage**，不做账号、不上传。同一设备两个孩子各自独立，互不消耗对方的题。
- 清缓存 / 换设备 → 归零。这个边界写进孩子端首页的家长说明链接和 `docs/pwa.md`。
- 家长诊断页的 `cnmDiagnose.seen.v1` 保持独立，不与孩子端合并（两者用途不同，合并会让家长的精细检查消耗孩子的题）。

## 8. 异常与边界

| 场景 | 行为 |
| --- | --- |
| 档案无当前学科配置 | 首页出「请家长先设置教材」卡片 + 链到档案页，不进入答题 |
| 分片 404 / 网络失败 | 显示「加载失败，请检查网络」+「重试」按钮；不静默降级到 `diagnostic_question`（孩子端不接受单题兜底） |
| 骨架加载失败 | 同上，整页错误态 |
| 本册无可派点 | 走 §5.3 册末衔接 |
| 该学科最后一册学完 | 「这一科学完了」+ 链到家长诊断页 |
| `limit` 用尽仍有点未判定 | §5.5，显示「明天继续」，不显示「未测」 |
| 懒加载 5 轮后仍无可出题点 | 结束会话，完成屏说明「今天练完了」；把该点留在队列里 |
| localStorage 不可用（隐私模式） | 沿用 `lsGet/lsSet` 的 try/catch 静默降级；本次会话内仍不重复，跨会话记忆失效，首页提示家长 |
| 同一设备切换孩子 | 首页顶部孩子切换器；切换后 seen / skipped / 档案全部按新 childId 读 |
| 旧档案（无 subjects） | 视为空配置，走「请家长先设置教材」 |
| 分片与真源不一致 | `tests/test_bank_shards.js` 在 CI 拦住；运行时不校验 |

## 9. 下游子项目（不在本 spec 实现范围）

本 spec 的决策把第 4 项的目标数字锁定了，记录在此供其独立 spec 引用。

**第 2 项：删 863 道错挂疑点题 —— 已于 2026-11-08 执行完毕。** 筛查固化为 `scripts/mismount_review.py`，复跑得 863 道（basic 641 / standard 176 / challenge 46）。按 `version_gate.bar_ok` 的真实语义（遍历 registry 33730 个「版本×学科×点」对）模拟，仅 2 个点破闸门（多版本挂载表现为 26 个版本块）：`cnm_223`（basic 只 1 道）、`cnp_h044`（物理不足 10 题），各补 1 道 basic 后 `below=0`；无点被删空。

**执行中发现筛查精度按难度档剧变，据此回捞**：`version_gate` 只对物理拦 challenge 缺失，摘除后闸门全绿却使 `no_challenge` 从 0 回退到 33。把 46 道被摘的 challenge **全量逐条读完**，只有 5 道确属错挂，**35 道挂载正确**（《池上》《赵州桥》《我的战友邱少云》课文原句、《父爱之舟》原文情节、教材 400m 跑道设计原题、child→children），另 4 道存疑、2 道挂载对但题目有硬伤。原因是拓展题刻意用新材料/类文迁移，字面重叠天然低，n-gram 恰好惩罚了它该奖励的题型。用户裁定「恢复已证实误报」，`--restore=false_positive` 放回 37 道（35 challenge + 2 basic），`no_challenge` 降到 5。**净变化 35967 − 826 + 2 = 35143。**

证据落在 **`data/mismount-review.json`（纳入 git，946 KB）**，不再是 gitignored 的 `_scratch` 临时文件：逐题存完整原题 + 考点上下文 + n-gram 分值 + 人工 verdict/note。863 条中 73 条已裁定（37 误报 / 27 确错 / 7 存疑 / 2 待修），**790 条 pending**。3 道有答案/题干硬伤须先订正再谈恢复：`cng_j007_q11`（漏太平洋）、`cnp_046_q12`（问功却算功率）、`cnm_p247_q28`（115% 误标 15%）。

**第 3 项：扩池子（知识点 + 对应内容）。** 三维盘点里 253 格 `no_point` 是建点缺口，与第 4 项的题量缺口是两件事。

**第 4 项：容量补齐。** 目标 = 每点 **60 道可机判题**（basic 10 + standard 10 + challenge 40），支撑 confirm=5 时 10 轮不重样。**第 2 项执行后**实测（`scripts/play_capacity.py --confirm 5`，与独立实现 `_scratch/_s198_stats.py` 互验一致）：

| 口径 | 计入题 | 缺口 | basic | standard | challenge |
| --- | --- | --- | --- | --- | --- |
| 全题型 60/点 | 35,143 | 177,146 | 17,452 | 24,358 | 135,336 |
| **仅可机判 60/点（终态）** | **29,877** | **181,351** | **20,225** | **25,502** | **135,624** |

终态题库 **210,240 道**（3504 × 60），需新写 **181,351 道**，其中挑战档占 75%。按学科：数学 45,195 / 语文 41,965 / 英语 39,694 / 科学 19,094 / 物理 13,823 / 道法 12,110 / 历史 6,612 / 地理 2,858。按学段：小学 73,687（1458 点）/ 初中 70,766（1339 点）/ 高中 36,898（707 点）。

缺口 **不等于** `210240 − 29877 = 180363`：目标按**档位**分别计（10/10/40），某点某档的富余不能抵另一档的不足，逐档取 `max(0, 目标 − 现有)` 再求和得 181,351。

confirm 敏感性（仅可机判、第 2 项执行后）：confirm=2 → 缺口 76,231；confirm=3 → 111,271；confirm=5 → 181,351。**若日后改 confirm 上限，只需改这一个参数重算。**

`docs/question-capacity-plan.md` 的旧数字（106,749 / 176,829）是**家长端 confirm=3 全题型**口径，已于 2026-11-08 在该文档顶部标注口径分裂与快照过期，不替换本文数字——两套口径并存，各自复跑各自的脚本。

## 10. 测试与验证

**新增单测**（Node，沿用 `tests/test_engine.js` 的零依赖断言风格）：

`tests/test_bank_shards.js`
- 每道题恰好出现在一个分片；分片并集 == 真源题库（按 id 集合相等）
- 每个知识点恰好出现在一个骨架文件；骨架并集 == 真源 topics
- 册名归一后无重复分片、无遗漏（117 册）
- manifest 的 `topics` / `questions` / `bytes` 与分片实际内容一致
- `volumes` 数组顺序 == registry `topicIds` 中册键的首次出现顺序
- `buildId` 随真源变化而变化

`tests/test_play.js`
- 派题顺序 == registry `topicIds` 顺序（过滤册次与 mastered 后）
- `mastered` 被跳过，`weak` / `shaky` 不被跳过
- 跳过按钮把该点排到本册末尾，且不写诊断记录
- 册末自动衔接下一册并回写档案
- 最后一册学完显示终止态
- 懒加载钩子：栈顶点题库未加载时先取该片再出题，**不静默跳过**
- 懒加载前后 `E.replay` 重建的出题序列一致
- 同一孩子 10 轮不重样（用 60 题/点的 fixture）
- 两个孩子 seen 互不干扰
- 题型过滤：孩子端建图后 bank 内无 short / self
- `limit` 用尽时未判定点保持 unknown，下次仍在队列

**回归**：四闸门照跑（`scripts/validate.py`、`scripts/verify_questions.py`、`scripts/version_gate.py`、`node tests/test_engine.js`）+ `node tests/test_children.js` + `node tests/test_children_browser.js`（档案字段扩展后必须仍通过）。

**浏览器实测**（chrome-devtools MCP，手机视口 390×844）：
- 黄金路径：首页 → 开始 → 答对 → 答错 → 反馈 → 完成 → 记录写入档案
- 边界：档案未设置、分片 404、断网、册末衔接、切换孩子、隐私模式
- 首屏网络体积实测并记录，对照 §6.4 预算

**测量脚本**（本文所有数字的来源，执行时须从 `_scratch/` 提升为 `scripts/` 下的可复跑脚本）：

| 用途 | 原临时脚本 | 状态 |
| --- | --- | --- |
| 删 863 影响 + 摘除/恢复 | `_s183_drop_impact.py` | **已提升 → `scripts/mismount_review.py`**（2026-11-08，含 `--apply` / `--regrade` / `--restore[=verdict]`） |
| 可机判容量 | `_s188_capacity_auto.py` | **已提升 → `scripts/play_capacity.py`**（2026-11-08，`--confirm` / `--all-types` / `--json`） |
| 分片体积 | `_s185_shard.py` | **已提升 → `scripts/shard_budget.py`**（改读实际产物，口径与线上一致） |
| 先修闭包 | `_s190_closure.py` / `_s192_clo5.py` | **原临时脚本已随 `_scratch` 清理消失，按 §2 口径重写为 `scripts/prereq_closure.py`** |
| 骨架体积 | `_s191_skeleton.py` | **已并入 `scripts/shard_budget.py`** |

实现与原 spec 的 11 处偏差及理由见 `docs/superpowers/plans/2026-11-09-child-play-ui.md` 的「与 spec 的偏差与理由」。

## 11. 明确不做

账号与云同步、积分商城等 gamification、倒计时压力、拍照批改、语音朗读、把引擎改成「没出过优先」（用户已定「不能省」，难度阶梯保持）、per-edition 题库（用户长期约束：题目只挂 topicId，一个总题库）。

## 12. 未决事项

无。本文所有设计选择均已由用户 2026-11-08 选定或由实测数据唯一确定。第 9 节三个下游子项目各自需要独立 spec。