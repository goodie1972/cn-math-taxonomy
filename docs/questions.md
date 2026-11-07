# 题库说明（data/questions.json）

给每个正式知识点建的小题库，供 `diagnose/` 诊断工具按「每个知识点最多 2 题」的规则出题。现在共 **3504** 个正式知识点、**35967** 题，八个学科（数学、英语、语文、物理、科学、道德与法治、历史、地理）都在同一个总题库 `data/questions.json` 里。**题目只挂 `topicId`，不挂教材版本**：同一知识点不管在哪本书、哪个省出现，用的都是同一批题；版本 / 册次只是知识点的切片，不是「每套教材一份题库」。

下面「统计」「核验方法」里标成第五轮的数字只计当时的 1407 道初中题。各轮批次数字见文末分节，全库最新口径见「全库现状（2026-11-06）」。

## 格式

`data/questions.json` 是一个 JSON 数组，每题一个对象：

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | `<topicId>_q<N>`，如 `cnm_221_q2`；`_q1` 由 `topics.json` 的 `diagnostic_question` 迁移而来（题干以原题文字开头，必要时在后面追加答案格式说明） |
| `topicId` | 是 | 知识点 id，必须是正式知识点 |
| `difficulty` | 是 | `basic` 基础（直接套定义 / 一步计算）、`standard` 提高（课本例题水平，2–3 步）、`challenge` 拓展（综合、多步或易错点）。`advanced` 是 `challenge` 的旧名，两者同档，诊断页都显示「拓展」 |
| `type` | 是 | `numeric` 数值题、`choice` 选择题、`short` 短答题、`self` 开放题（必须自评） |
| `prompt` | 是 | 中文题干，自包含（几何条件用文字、长度、角度、坐标写全，不看图也能读懂条件）。单位写在题干里，答案不带单位。需要看形状时另有可选的 `figure` |
| `answer` | 是 | 字符串。numeric：一个数（整数 / 小数 / 分数 `a/b` / 负数），多个答案用全角「，」分隔；choice：正确选项字母；short：标准短答案；self：参考答案 |
| `choices` | choice 必填 | `[{"key":"A","text":"…"}, …]`，3–4 个选项，key 依次为 A、B、C、D，选项文字互不相同。选项可以另有 `figure`（内联 SVG） |
| `figure` | 否 | 题干配图，内联 SVG 字符串（只含 `viewBox`，用 `currentColor`，不引用外网）。诊断页和知识图谱样题会画在题干下面 |
| `hideChoiceText` | 否 | 仅选择题，且为 `true`。每个选项都有 `figure` 时，页面只显示图形、不显示选项名称（名称仍留在 `text` 里，用来判分和显示参考答案）。用于「下面哪一个是长方体」这类题，避免名称直接泄题 |
| `accept` | 否 | short（也可用于 numeric）的等价答案列表 |
| `explanation` | 是 | 1–3 句中文解析，答题后显示 |
| `verify` | 否 | 一个 Python 表达式字符串，用于机器核验 `answer`（见下） |
| `unordered` | 否 | numeric 且多个答案顺序无关时为 `true`（如方程的两个根）；没有这个字段的多答案题按顺序比较 |
| `fixed_from_source` | 否 | 迁移 `diagnostic_question` 时补充了条件（原题有歧义）才有，写明原因。目前 3 题：`cnm_061_q1`、`cnm_070_q1`、`cnm_253_q1` |

`topics.json` 里的 `diagnostic_question` 原样保留（兼容；题库缺失时诊断工具回退到它）。

## 全库现状（2026-11-06）

**35967 题 / 3504 个正式知识点 / 5233 条先修边**，八科同库（题只挂 `topicId`）。口径由 `validate.py`、`verify_questions.py`、`version_gate.py` 与 `scripts/build_inventory.py` 的输出互相对过：

| 学科 | 知识点 | 题数 | 平均每点 |
|---|---|---|---|
| 数学 `cnm_` | 870 | 9683 | 11.13 |
| 英语 `cne_` | 791 | 9007 | 11.39 |
| 语文 `cnc_` | 795 | 7459 | 9.38 |
| 物理 `cnp_` | 269 | 2797 | 10.40 |
| 科学 `cns_` | 360 | 3132 | 8.70 |
| 道德与法治 `cnd_` | 226 | 1705 | 7.54 |
| 历史 `cnh_` | 134 | 1474 | 11.00 |
| 地理 `cng_` | 59 | 710 | 12.03 |

- 按 type：numeric 5535，choice 24929，short 5496，self 7；**numeric + choice 占 84.7%**（30464 道）。
- 按 difficulty：basic 20267，standard 10865，challenge 4835，`advanced` 0。
- 每知识点题数：最少 4、最多 60、平均 10.26，**无 challenge 的知识点 0 个**（本轮补 305 道后全 3504 点均含 challenge）。
- 自动核验：`verify_questions.py` 全库 **auto_verified 30464，mismatch 0**，unverifiable 5503（short 5496 + self 7）。带 `verify` 字段的题 35938 / 35967 = **99.92%**（本轮新写的 30 道 short 题里 29 道未带 verify，1 道带）。
- 选择题正确选项分布：A 6266，B 6270，C 6247，D 6146（24929 道，极差 124 道 ≈ 0.5 个百分点）。3 选项 314 道、4 选项 24615 道。
- 带配图（内联 SVG）的题 243 道。
- 重复题：按「题干 + 选项文字 / 答案」**完全相同的组 0 组 / 多余 0 条**。

### 这一轮做了什么（305 点各补 1 道 challenge，2026-11-06）

1. **背景**：`build_inventory.py` 的「拓展档缺口」表在挂载 302 初中语文点时列出了 305 个无 challenge 的知识点；用户裁定「每点补 1 道 challenge（+305 题）」，本轮一次性闭合。全库 challenge 档从 4530 → **4835**，题库从 35662 → **35967**。
2. **批次构成**：8 个碎片文件走 `qgen_lint → qgen_spread → qgen_merge` 流水线 —— 初中语文 8 批（`chinese_junior_01` ~ `chinese_junior_08`，7 批各 40 + 1 批 22，共 302 题）、小学英语 1 题（`cne_p226`）、小学道法 2 题（`cnd_p153` / `cnd_p154`）。题型 275 choice + 30 short，全部 `difficulty=challenge`，`answer` 按 `qgen_spread.py` 铺平（正确选项全库 A/B/C/D 各 ≈ 1/4，本轮 305 道内 70/69/68/68）。
3. **写作规范**：语文题题干与解析里的拉丁字母连续 3 位以上一律替换为中文标点或汉字；选项文字里的引号、反斜杠改写成「」《》；`verify` 字段必须是「正确选项文字」的 `json.dumps(ensure_ascii=False)` 字面量，机器可验证；short 题在 30 道里 29 道省略 `verify`（短答案机器核验意义有限），`cnc_j007_q5` 例外保留 verify；challenge 层级只考「写法 / 结构 / 比较 / 推断」，不再出套一层的死记题。
4. **盲解复核**：`qgen_blind.py prepare` 出的 305 道独立盲解表拆成 7 份紧凑表（每份 40 行）供作者本人在 40 分钟窗口内独立作答，275 choice 全部作答、30 short 与 7 self 按既往口径不入盲解（short 是开放简答、self 是自评）。比对结果 `blind_mismatches.json` = **0 处不一致**（275 道全对）。诚实口径：盲解由作者本人完成，非独立第三方；且「正确项几乎总是最详实的一条」这一构造特征使盲解偏易。
5. **闸门全绿**：`validate.py` VALIDATION PASSED、`verify_questions.py` VERIFICATION PASSED（auto_verified 30464 / mismatch 0 / unverifiable 5503）、`version_gate.py` `blocks=99 dangling=0 ext=0 below=0 dup=0`、`node tests/test_engine.js` 93 passed / 0 failed、`build_inventory.py` `no_challenge=0`。
6. **同步修订**：CHANGELOG、本文件的「全库现状」「局限」两节均按 35967 / 99.92% verify 覆盖 / 314+24615 选项 / 243 图 重新校准；旧文里「全库 100% 带 verify」的结论已过时，实际 35938 / 35967 = 99.92%。本地提交，未推送。

### 上一轮做了什么（对抗审核修复 C：转义塌缩止血 + verify 重同步 + 解析字母）

1. **破损根因**：早期批次把 LaTeX 命令当 Python / JSON 字符串字面量写，`\t` `\b` `\f` `\r` 这些转义序列在生成时被**整体吃掉**，留下三种形态——控制字节（0x08/0x09/0x0c 顶掉「反斜杠 + 首字母」）、缺首字母的裸词（`imes`、`ext{`、`rac{`、`riangle`、`igcirc`、`ightarrow`、`ig竞`）、以及字面 `\t` 的四字符残骸。所以「147 项 LaTeX 破损」是**低估**：全库实际 900+ 处、覆盖 1200 余个字段。
2. **修复方式**：按形态分轮收敛（控制字节 → 反斜杠、裸词 → 补回命令名、`\t\triangle` 这类疤 → 单条规则），choices 与 verify 字段同批处理；不重写题干文字，只还原符号。终态复扫 13 个破损类别（控制字符、字面 `x08`、`imes`、`ext{`、`rac{`、`dot{`、`riangle`、`igcirc`、`bigcirc` 裸形、`ightarrow`、`lacksquare`、`ig竞`、`\t\triangle`）**全部为 0**，复跑脚本 `_scratch/_s10z_final.py`。
3. **verify 重同步 12623 条**：选择题的字符串引用型 `verify` 必须等于「正确选项文字」的 `json.dumps` 形式。符号修复后旧引用（单反斜杠、单引号包裹）会与实际文字错配，因此统一按 `json.dumps(正确选项文字, ensure_ascii=False)` 重写；重同步后 `mismatch 0`。
4. **单题硬伤 7 处**：3 处符号残骸（`cnm_p179_q13` 裸 `angle`→`∠1`、`cnm_p191_q20` 多余的「反斜杠+空格」、`cnm_p030_q17` 坏掉的 `\text{ }` 占位符→`\bigcirc`）+ 4 处内容错误（`cne_h190_q10` 答案字母指向「抽象的」而句意要 canvas＝画布；`cnm_p152_q21` 三视图「最多」应是 6+1＝7 个不是 9 个；`cnm_p060_q41` 题干是 `(25+15)×8` 却答 5，且该点考点是「变化规律」，已按考点重写成数列题；`cnm_p050_q26` 题干 `6000 - 2000` 答案标成 400）。
5. **新增可复跑体检**：`_scratch/_s14_arith.py`（题干即算式 → 用 `Fraction` 精确求值比对答案，119 道，不一致 1 道＝`cnm_p050_q26`）与 `_scratch/_s10z_final.py`（破损类别复扫）。`_scratch/_s17_expl.py`（解析末句结果 vs 标注答案）试过但**噪声太大**（4956 道里 652 道命中，绝大多数是解析里的中间步骤），不作为闸门，只当人工抽查的线索清单。
6. **解析字母一致性（订正旧结论）**：复跑 `scripts/qgen_letter_audit.py` 得 `choice_items=24654，suspects=14`——旧条目里那句「suspects=0」不成立，14 条全在小学语文 `cnc_` 池。症状统一：解析描述的选项文字就是 `answer` 那一栏，但句中写的字母挪了位（如 `cnc_p248_q12` 答案 C「瓣 辫 辩 辩」，解析却写「D正确」）。12 条按「解析里字母的双射」整体换回；`cnc_p038_q12`（汉字结构分类）和 `cnc_p469_q12`（错别字）是解析内容本身写坏，整段重写——后者原 B 项「掩面叹息」其实没有错别字，与 C「荒凉忧伤」构成双解，改成「全神惯注」（应为「全神贯注」）后唯一答案才成立。修完复跑 `suspects=0`。
7. **反向扫描（新增闸门）**：`qgen_letter_audit.py` 只认解析里「X 正确」这一侧，看不见解析把**正确项说成干扰项**（「B 错 / A 说反了 / 排除 C」）。新增 `scripts/qgen_letter_pair_audit.py` 双向判定、有疑点退出码 1，可直接接进流水线；它扫出 5 道（`cnc_p172_q17`、`cnc_p190_q13`、`cnc_p245_q13`、`cnc_p439_q17`、`cnc_p401_q14`），同样按双射换回字母，现在 `suspects=0`。
8. **这条闸门的可见范围（诚实口径）**：24654 道选择题里，解析真的点了字母的只有 **正确侧 112 道 + 干扰侧 24 道（约 0.5%）**——绝大多数语文题的解析是纯文字讲解，不写字母。所以「字母 0 疑点」说的是这一小片可见切片：切片内 19/112 有缺陷（约 17%），剩下 24500 余道**这条检查看不见**，不能外推成「解析全对」。
9. **另两项复跑**：verify 约定普查——choice 里 24566 道用「正确选项文字的 json 引用」当 `verify`、88 道用真实计算表达式（`Fraction(9,10)`、`144/2` 这类，会同时触发双解检查）、0 道用裸字母，两种约定都被 `verify_questions.py` 的 `compare_choice` 接住；`_scratch/_s14_arith.py`（题干即算式 → `Fraction` 精确求值比对答案）119 道复跑 `mismatch=0`。
10. **闸口全绿**：`validate.py` VALIDATION PASSED、`verify_questions.py` VERIFICATION PASSED（mismatch 0）、`version_gate.py` `blocks=99 dangling=0 ext=0 below=0 dup=0`、`node tests/test_engine.js` 93 passed / 0 failed；两条字母审计（`qgen_letter_audit.py`、`qgen_letter_pair_audit.py`）均 `suspects=0`。**题量与结构未变**（35662 / 3504 / 5233），这一轮只改内容。本地提交，未推送、未部署。

### 这一轮做了什么（对抗审核修复 C 续：题目↔知识点错挂 309 道）

1. **缺陷形态**：同一单元内的题目按**位置**而不是按**知识点 id** 配给知识点，于是出现整段平移——语文六上第一单元「草原 ↔ 丁香结 ↔ 宿建德江 ↔ 西江月夜行黄沙道中」四点的题互相串位；小学数学六上「分数乘法的应用 cnm_p179 ↔ 用方向和距离确定位置 cnm_p180」两段题号（q15–q31 / q18–q35）互换，另有比例尺、扇形统计图、数与形、百分率、比的意义各吃到别人的题；初中数学「科学记数法 cnm_022」里混着有理数加减与乘方题，初中地理「地球的宇宙环境 cng_j001」里混着经纬线与自转题。这类缺陷**四道闸门全都看不见**（题量、档位、id 前缀、占比都成立），只能靠内容级体检暴露——而它恰恰直接违反北极星口径「题目是对应知识点的」。
2. **可证的判据（三把尺子）**：① 语文——题干**主语位置**出现《课文名》（`阅读《X》` / `下列关于《X》`），且该篇名在全库只对应一个知识点，同时排除「和 / 跟 / 与 / 比较 / 异同 / 本文」这类**对比型**题干（对比题 legitimately 提两篇）；② 数学与地理——把题干与候选知识点的名称、 mastery_criteria 做 n-gram 比对，只采信**人工逐条读过题干**能点出考点的那批；③ 第三方证据——`_scratch/csf_import/*.json` 每条教材题自带 `knowledge_point` 标签，归一化题干后与库内比对，816 条 CSF 题匹配到 704 道库内题，其中标签名与知识点名**完全一致**（score ≥ 0.9）的错挂 2 道，已修。
3. **改了多少**：**309 道重新挂**（语文 212 + 45 + 1 + 2、数学与地理 47 + 2）、**6 道就地重写**、**2 处课文名错字订正**（《狼山五壮士》→《狼牙山五壮士》、《在那牛肚子里的旅行》→《在牛肚子里旅行》）。6 道重写挑的是「挂在哪儿都说不过去」的：`cnm_p180_q26`（原为分数题）改成方向相对性题、`cnm_p179_q20` 原题只写「计算：180 − 60 = ?」补上北偏东情境后转挂 cnm_p180、`cnm_p180_q18` 同理想通后转回 cnm_p179、`cnm_018_q11`（化简 3a−(2a−1) 是有理数运算点的题）换成四则混合运算、`cnm_022_q15`（−2³ 与科学记数法无关）改为「3.2×10⁸ 原数几位整数」、`cng_j001_q8`（地球自转方向属「地球的运动」）换成小行星带位置。这 6 道顺带清掉了全库最后 **4 组跨知识点真重复**（4→0）。
4. **转挂必须换 id**：`validate.py:1189` 要求 `id` 前缀等于 `topicId`，所以每道移动的题都重编号成 `<目标点>_q<N>`（N 取该点现有最大号 +1 并避开已用号）；两处硬闸不许触碰结构——**`_q1` 永不移动**（q1 题干必须等于该知识点的 `diagnostic_question`），**移动后源点仍须 ≥3 题且 basic 与 standard 俱全**（`_s44`/`_s47`/`_s62` 每条都带 `tier_breakers=0` 断言）。语文那两波还同步把解析里的「本课」改成具体篇名，避免移动后解析指错课文。
5. **精度靠全量读题，不靠抽样**：三波候选分别 244 / 45 / 1 条，全部**逐条读完题干**才放行；过程中按新证据收紧过三次判据，因此被规则丢掉的量很大（`obj_position` 24、`compare_tail` 5、`ambiguous` 6、`multi` 9、`unmapped` 87），第一版宽判据会误动 315 道、其中 2 道会打崩档位——这些是规则演化出来的原因，不是事后找补。
6. **复跑结果**：语文错挂屏 `keep=0`；CSF 强证据屏 `strong=0`（错字修好后 `cnc_p173_q5`、`cnc_p414_q5` 才第一次被机器认出，随即转挂）；篇名—知识点不一致屏 `_s38_title_mismatch` 从 **413 → 162**（其余是同一篇课内多义、或题干合法引用别篇课文，逐条不可证）；`qgen_dedup` `to_drop=0 violations=0`；字母双向审计 `right_claims=112 wrong_claims=24 suspects=0`。四道闸门全绿：`validate.py` PASSED、`verify_questions.py` `auto_verified 30189 / mismatch 0`、`version_gate.py` `blocks=99 dangling=0 ext=0 below=0 dup=0`、`node tests/test_engine.js` 93 passed / 0 failed。**题量与知识点数不变**（35662 / 3504）。
7. **订正两条旧结论**：① 之前「题目↔知识点匹配」没有作为独立维度体检过，本库里**确实存在整段错挂**，不能再说「挂载正确」；② `_s37_mismatch.py` 的 `suspects` 在转挂前后（898/7205 → 863/7427）**不可直接比较**——重编号改变了「q11+」这批题的构成，只说明规模量级没变，不是修复率。

### 上一轮做了什么（初中道德与法治，2026-11-04）

1. **初中道法建池**：按统编初中目录逐课建点 `cnd_j001`–`cnd_j067`（67 点，一课一点：七上 13、七下 11、八上 12、八下 14、九上 10、九下 7），每点 4 道选择题共 268 题，另加第四学段课标条目 15 条（`cds-2022:4.*`）与初中先修边 97 条（hard 55，其中 15 条从初中点回指小学点）。道法因此从 159 点 / 1749 题变 **226 点 / 2017 题**。内容在 `scripts/mor_g7.py`、`mor_g8.py`、`mor_g9.py`，初中先修在 `scripts/mor_j_edges.py`，由 `scripts/mor_build.py` 编译。
2. **目录依据与逐课比对**：六册目录来自 `_scratch/junior_toc/mor_junior.json`（逐册双源以上），`_scratch/junior_toc/_cross_mor_jr.py` 把「已登记的课名 / 单元号 / 单元名」与证据逐条对照，结果 **mismatch=0**（七上 13、七下 11、八上 12、八下 14 全为修订版目录；九上用 2026 秋修订目录 4 单元 10 课；九下修订版列入教育部 2024 年目录但未出版，仍按现行 2018 年 12 月第 1 版 3 单元 7 课）。
3. **构建边界改成精确课数**：`JUNIOR_BOUNDS` 按各册课数写死上下界（如 `9上: (10, 10)`），多一课少一课都构建失败——不再允许「先建着再说」。
4. **内容体检**：`_scratch/junior_toc/_check_mor_jr.py` 校验每题 4 个选项、干扰项是平铺的 3 项、无空字段、无英文残留、选项互不相同，结果 `problems=0`。

### 更早一轮做了什么（补题批次 + 清重复，2026-11-02～03）

1. **按知识点补齐**：清单 `_scratch/qgen/manifest.json` 的 808 个缺口（781 道拓展 + 27 道基础）全部闭合，逐批过四道闸口：`qgen_lint.py`（内容体检）→ `qgen_merge.py --dry-run`（格式 + 同知识点查重）→ `verify_questions.py --file`（自动核验）→ 中心真合并；合并后再跑 `validate.py` + `node tests/test_engine.js`，并交独立盲解（`qgen_blind.py prepare/compare`）。
2. **清掉同知识点重复题 377 道**：历史上有多轮「凑题量」把同一知识点的题干 + 选项（或答案）原样写了两遍，诊断时会出现「同一道题再问一次」。`scripts/qgen_dedup.py` 按「题干 + 选项文字 / 答案」分组，每组只留一条（优先留带 `verify` 的、以及删掉会让某档位缺失的那条），删前预演确认每个知识点仍达标。清理后 `dup_groups=0`。
3. **重复题清理后回补**：高中物理 6 个知识点（`cnp_h044`、`cnp_h074`、`cnp_h133`、`cnp_h135`、`cnp_h143`、`cnp_h147`）因删重落到 9 题，测试要求每个物理知识点 ≥10 题，已新写 6 道带 `verify` 的题补回（`_scratch/qgen/merged/physics_refill_01.json`）。
4. **选项字母一致性审计**：`scripts/qgen_letter_audit.py` 全库扫描「解析里断言的选项字母必须等于 `answer`」，当时报 `choice_items=23075，suspects=0`。**订正（2026-11-06）**：同一脚本对现库跑出 14 条疑点，那句结论已过时（且脚本只看「X 正确」一侧）；逐条裁决与修复见上一节第 6～8 点。

## 统计（第五轮，只计初中 1407 题）

- 当时总数 **1407** 题，覆盖全部 315 个初中知识点；每个知识点 4 题（168 个）或 5 题（147 个），最少 4、最多 5、平均 4.47。这些题后来没有改写。
- 按 type：numeric 903，choice 475，short 23，self 6；**numeric + choice 占 97.9%**。
- 按 difficulty：basic 591，standard 537，advanced 279。每个知识点都含 basic 和 standard，并且除 q1 之外至少还有一道 basic（诊断时「第二题优先出 basic」要用）。
- choice 的正确选项分布：A 124，B 126，C 126，D 99；101 题 3 个选项，374 题 4 个选项。

## 核验方法

### 1. 自动核验：`python3 scripts/verify_questions.py`

numeric 和 choice 题可以带 `verify` 表达式，脚本在**受限环境**里求值（Python `ast` 白名单：四则运算、`**`、`//`、`%`、比较、列表 / 元组 / 推导式、下标；只能调用 `Fraction sqrt pi sin cos … comb perm gcd lcm sum min max sorted range ceil floor mean median pvariance …`，外加 `solve2`（解二元一次方程组，精确分数）、`roots2`（一元二次方程实根）；没有 import、属性访问、赋值，单次求值 2 秒超时），再与 `answer` 比较：

- numeric：结果与 `answer` 逐项比较；整数 / 分数结果**精确比较**，浮点结果容差 1e-9；多个答案按 `unordered` 决定是否顺序无关；
- choice：结果与**正确选项的内容**比较（选项是数时按数值比较，否则要求文字完全相同），同时要求没有第二个选项与它相同（防双解）。

脚本会同时做格式检查，输出 `auto_verified`（有 verify 且通过）、`mismatch`、`unverifiable`，明细写入 `data/verification_report.json`。第五轮当时（只计初中；全库数字见文末）：

| 项 | 数量 |
|---|---|
| numeric + choice 题 | 1378 |
| **auto_verified**（有 verify 且通过） | **875**（占 numeric + choice 的 63.5%） |
| **mismatch** | **0** |
| unverifiable（无 verify） | 532：choice 464（选项是文字 / 式子，没法用表达式算）、numeric 39（推理型）、short 23、self 6 |

自动核验的局限：`verify` 是出题者自己写的，可能和答案「同源」（算法写错一样会错）；个别题的 verify 只是把常数列出来（出题者在备注里标注过 `cnm_248_q4`、`cnm_093_q5`），这类题的保证主要来自第二遍独立复核。

### 2. 独立第二遍复核：`scripts/second_pass.py`

由**没看到答案**的独立解题者（Claude 子任务）重新解题，再逐题与题库比对：

- 把 numeric / choice / short 题去掉 `answer`、`explanation`、`verify`、`accept`，只留题干和选项，分块给解题者（`second_pass.py prepare`）；解题者只能读自己的那一块，我核对过他们的工具调用记录，没有读过题库或其它文件；
- **A 轮（全量）**：19 个解题者，1401 道题（numeric 903、choice 475、short 23），一次性作答；
- **B 轮（风险题，更仔细）**：16 个解题者，752 道题——所有没有 `verify` 的 numeric / choice / short 题加上全部 `advanced` 题；要求分小批逐题推理、非平凡的计算用 Python 精确算、每题写出推导（`work_b_NN.json`）；
- 解题者的原始答案、推导和存疑备注保留在 `data/_second_pass/`（`ans_NN.json`、`ans_b_NN.json`、`work_b_NN.json`、`notes_NN.json`、`mismatches*.json`），题干分块文件（`blind_*.json`）可随时用 `second_pass.py prepare` 重新生成；
- `second_pass.py compare` 比对：choice 比字母，numeric 比数值（有序 / 无序），short 规范化后比 `answer` + `accept`；不一致的逐条裁决。

结果（详见 `data/verification_report.json` 的 `second_pass` 与 `data/second_pass_log.json`）：

- A 轮 3 处不一致（`cnm_090_q3`、`cnm_213_q4`、`cnm_311_q4`），我用精确计算逐条裁决，**3 处都是解题者算错，题库答案正确**；B 轮 0 处不一致。
- **发现并修正答案错误：0 处**。发现并修正的其它问题 5 处：4 处题干含糊（解题者提示后改写）、1 处解析写错。例：
  - `cnm_133_q2`「到线段 AB 两个端点距离相等的点，一定在：」只在平面内成立 → 补「在同一平面内」；
  - `cnm_053_q3` 题干写「图中……」却没有图 → 删去「图中」；
  - `cnm_306_q2` 样本方差除以 n 还是 n−1 有口径之分 → 写明「各数据与平均数之差的平方的平均数」；
  - `cnm_151_q3` 解析把正确选项 C 写成「没提干净」→ 由「解析里选项字母与答案矛盾」的扫描发现并改正。
- 解题者另外标出 16 条「存疑」，逐条看过：除上面 4 处外，题干条件已足以唯一确定答案，不改。
- 报告里 `mismatch = 0`，`second_pass_mismatch = []`。
- 出题阶段每位出题者交稿前自己跑过 `verify_questions.py --file`（要求 mismatch = 0，格式错误 = 0）；这一步里被他们自己改掉的问题没有留下记录，所以不计入上面的「修正」数字。

### 3. 格式校验：`python3 scripts/validate.py`

题 id 唯一且与 topicId 一致；topicId 存在且不是外部节点；`difficulty` / `type` 合法；choice 有 3–4 个选项、key 依次为 A–D 且不重复、answer 是某个 key、选项文字不重复；numeric 的 answer 能解析成数（含分数、负数、多值）；必填字段非空；没有未知字段；每个正式知识点 ≥ 3 题且含 basic 与 standard；q1 存在且题干以 `diagnostic_question` 开头（或带 `fixed_from_source`）；numeric + choice 占比 ≥ 60%。打印题量统计。

## 局限

- **没有教师审核**；独立复核的解题者与出题者是同一模型家族，如果对某个知识点有共同的误解，这种错误两边都不会暴露。「0 处答案错误」说明没有发现分歧，不是「保证无错」。
- 全库 **35938 / 35967 = 99.92% 带 `verify`**（本轮新增 30 道 short 里 29 道未写 verify）：numeric + choice 30464 道全部机验通过（mismatch 0），short 5496 + self 7 道只能规范化匹配或自评。**verify 覆盖不等于内容正确**——`verify` 是出题者自己写的，算法本身写错时答案与 verify 会一起错；这类残余只能靠人工抽查和独立盲解。
- 题干纯文字，不能画图：几何题用文字描述条件，没有图形题、作图题、证明题（证明思路类用 choice 或 `self`）。
- **选择题干扰项**只对应「典型错误」的猜测，没有真实学生数据校准；难度标注（basic / standard / challenge）是出题者的主观判断，同一难度内也没有区分度数据。
- 每个知识点 4–60 题（平均 10.26）：正好 4 题的点有 279 个，重测几次后仍会重复。**订正（2026-11-07）**：此前这里写「诊断工具优先出没出过的题，出完才重复」，不准确——`diagnose/engine.js:237-278` 是**难度优先于「没出过」**，避让只在同难度档内生效。全对路径每轮吃 1 standard + 2 challenge，所以不重样轮次＝`min(standard, challenge//2)`；实测 **≥3 轮的知识点 0 个**，2544 个点只有 1 道 challenge，第 2 次测评必重复，补 basic 无效。按用户新口径（3 题/次 × 10 次 = 30 题/点，受限点 15 题）现在**远未满足**：≥30 题仅 46 点、≥15 题 395 点。完整问题记档、缺口量化与推迟中的解决方案见 [question-capacity-plan.md](question-capacity-plan.md)，数字复跑 `scripts/capacity_gap.py`。
- **选择题正确选项分布**已铺平：A 6266、B 6270、C 6247、D 6146（极差 124 道 ≈ 0.5 个百分点）。铺平是按批次 `qgen_spread.py` 把「占比超过均值 1.3 倍」的字母挪到最少的那个，不是随机抽样；同一知识点内连续几题的字母仍有规律可循。
- **错挂修复只覆盖了「有字面证据」的一片**：语文靠《课文名》、地理与部分数学靠 CSF 自带的 `knowledge_point`，这两类证据能证多少修多少。数学与科学还有 **863 道**（占 q11+ 补充题 7427 道的 11.6%）n-gram 疑点，题干与考点名没有可判定的字面重叠，本轮**一道未动**——它们要么确实挂对、要么错挂，现有工具无法区分，只能人工读题或教师审核才能闭合。
- **题源标注不全**：35967 道里仍有 14000+ 道没有 `source` 字段，无法区分哪些来自教材原练、哪些是 AI 补写；本轮新增 305 道未回填 source，回填等于编造证据。
- **解析字母这条闸门只覆盖 0.5% 的选择题**：24929 道 choice 里解析写了字母的仅约 100 余道，`suspects=0` 只保证这一小片自相一致。其余解析是否讲得通，仍取决于「同一模型出题、同一模型复核」的天花板。
- numeric 答案限于有理数（含小数），含根号、π 的答案只能做成选择题；short 题（5496 道）和 self 题（7 道）靠规范化精确匹配或自评，等价写法可能被判成「需自评」。
- 初中批次文件合并后已删除。小学批次留在 `data/_qbatches/primary_g1.json` … `primary_g6.json`。要改题直接改 `data/questions.json`（小学题若从批次重编，需按 `scripts/build_primary.py` 的说明先恢复含 `cnm_ext_*` 的依赖再编译），再跑 `verify_questions.py` 和 `validate.py`。

## 小学题（2026-10-19）

每个小学正式知识点 4 题，共 **864** 题，id 形如 `cnm_p001_q1`。字段与初中题相同。q1 的题干等于该知识点 `diagnostic_question.question`；q1 和 q2 都是 basic，另外两道是 standard。没有 short、self、advanced。

| 项 | 小学 864 题 | 全库 2271 题 |
|---|---|---|
| type | numeric 644，choice 220（合计 100%） | numeric 1547，choice 695，short 23，self 6（numeric + choice 占 98.7%） |
| difficulty | basic 433，standard 431 | basic 1024，standard 968，advanced 279 |
| 每知识点 | 正好 4 题；每个点都有 basic 和 standard | 最少 4，最多 5，平均 4.28（4 题 × 384，5 题 × 147） |
| auto_verified | 864（每道 numeric / choice 都有 `verify` 且通过） | **1739** |
| mismatch | 0 | **0** |
| unverifiable | 0 | 532（choice 464、numeric 39、short 23、self 6，都是原来的初中题） |

低年级题用小学生说法，避免还没学过的符号（例如一年级不用字母方程）。numeric 的 `verify` 用 `scripts/verify_questions.py` 同一套受限求值。

独立复核记为 C 轮，写在 `data/second_pass_log.json`，名称是「C：小学题独立复核（primary_recheck，只读题干和选项，不读 answer / verify / explanation）」：`scripts/primary_recheck.py` 只根据题干和选项重算，864 题不一致 **0**。这一轮不是另请一位没看过出题脚本的人逐题手解，而是另一段不读取 `answer` / `verify` / `explanation` 的程序重算；和初中 A/B 轮的盲解不是同一做法。A/B 轮的记录没有改。`second_pass_mismatch` 仍是空数组。

小学题同样没有教师审核。二年级下册等册次目录若以后改了，对应题目的情境不一定要改，但章节归属要跟着教材重核。

## 高中必修题（2026-10-20）

每个人教 A 版（2019）必修知识点 4 题，共 **572** 题，id 形如 `cnm_h001_q1`。字段与小学、初中题相同。q1 的题干等于该知识点 `diagnostic_question.question`；q1 和 q2 都是 basic，另外两道是 standard。没有 short、self、advanced。诊断题的 `answer` 是数值，或正确选项的**文字**（不是 A/B/C/D：选项字母按知识点序号轮换）。

| 项 | 高中 572 题 | 全库 2843 题 |
|---|---|---|
| type | numeric 362，choice 210（合计 100%） | numeric 1909，choice 905，short 23，self 6（numeric + choice 占 99.0%） |
| difficulty | basic 286，standard 286 | basic 1310，standard 1254，advanced 279 |
| 每知识点 | 正好 4 题；每个点都有 basic 和 standard | 最少 4，最多 5，平均 4.22（4 题 × 527，5 题 × 147） |
| auto_verified | 572 | **2311** |
| mismatch | 0 | **0** |
| unverifiable | 0 | 532（仍是原来没有 verify 的初中题） |

可计算的题（计算、化简、求值、解的个数或端点）带 `verify`。不等式的解集如果是区间，改成选择题，或改成问整数解的个数、最小整数解。方差题在题干里写明除以 n，并用 `pvariance`。百分位数题在题干里写了人教教材的位置规则（排序后按 n×p% 取位；不是整数就取下一位，是整数就取相邻两项的平均），并标待核。含 √2、√3/2 这类不能化成简单分数的值做成选择题，或改成平方后的有理数。

`second_pass_log.json` 的 D 轮写明：高中必修题由 `scripts/hs_build.py` 用同一条 `verify` 表达式求出答案再写入，然后 `verify_questions.py` 再比对一次。mismatch 为 0 只说明格式和表达式一致，**不是另一遍独立解题**。没有做初中 A/B 轮那种盲解。概念题的选项文字与 verify 返回的字符串相同。批次在 `data/_qbatches/high.json`。

立体几何的判定、性质是选择题，不要求学生写出证明。高中题同样没有教师审核。

## 高中选择性必修题（2026-10-20）

每个人教 A 版（2019）选择性必修知识点 4 题，共 **512** 题，id 从 `cnm_h144_q1` 起。字段与必修题相同。q1、q2 是 basic，q3、q4 是 standard。题干自包含：不写「同一 / 上题 / 该函数」这类指着别的题的说法，也不问「本知识点 / 课标是否要求」。

| 项 | 选择性必修 512 题 | 全库 3355 题 |
|---|---|---|
| type | numeric 340，choice 172 | numeric 2251，choice 1075，short 23，self 6 |
| difficulty | basic 256，standard 256 | basic 1566，standard 1510，advanced 279 |
| 每知识点 | 正好 4 题 | 最少 4，最多 5 |
| auto_verified | 512 | **2823** |
| mismatch | 0 | **0** |
| unverifiable | 0 | 532（仍是原来没有 verify 的初中题） |

E 轮和 D 轮一样：`scripts/hs_sel_build.py` 用同一条 `verify` 写出答案，再由 `verify_questions.py` 比对，**不是盲解**。批次在 `data/_qbatches/high_sel.json`。

## 高中英语题（2026-10-21）

每个人教版（2019）高中英语知识点 4 题，共 **1036** 题，id 从 `cne_h001_q1` 起。全部是选择题。q1 的题干等于该知识点 `diagnostic_question.question`，答案是正确选项的文字（不是 A/B/C/D）。q1 和 q2 是 basic，q3 和 q4 是 standard。题干自包含：不以「同一 / 上题 / 该题 / 同上」开头，也不出现「本知识点 / 课标 / 是否要求」。短文是新写的，不抄教材原文。没有听力、口语。

小学英语 788 题、初中英语 980 题此前已经入库。全库现在 **6159** 题（数学 3355 + 英语 2804）。`verify_questions.py`：auto_verified **5627**，mismatch **0**，unverifiable **532**（仍是原来没有 verify 的初中数学题）。高中英语的 `verify` 返回正确选项的文字，和出题用的是同一条逻辑，**不是盲解**。生成脚本在 `scripts/enh_b1.py` 到 `enh_s4.py`，由 `scripts/enh_build.py` 写入 `questions.json`。

## 2026-10 英语新版教材

按新版人教 PEP 和 Go for it! 新增 23 个知识点（小学 `cne_p198`–`cne_p208`，初中 `cne_j246`–`cne_j257`），每个 4 道选择题，共 92 题，干扰项是常见错误形式或近形词。全库现在 **6355** 题（数学 3459 + 英语 2896）。`verify_questions.py`：auto_verified **5823**，mismatch **0**，unverifiable **532**（没有变）。
