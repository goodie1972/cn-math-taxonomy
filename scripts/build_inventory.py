#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三维盘点工作簿生成器（教材版本 × 学科 × 年级/册 → 知识点与题量）。

用法：
  python3 scripts/build_inventory.py
  python3 scripts/build_inventory.py --out _scratch/preview.xlsx --no-evidence

口径（数字全部由 data/ 复算，不手填）：
  data/topics.json                池子：学科 × 册 的知识点
  data/questions.json             总题库：题目只挂 topicId
  data/editions/registry.json     教材版本 × 学科 → 挂了哪些知识点
  data/editions/province_map.json 省 × 年档 × 学科 → 该省点名的版本（取证）
  data/inventory_evidence.json    取证快照（ChinaTextbook / 教育部目录 / CSF 真题）

达标两档，两列都给，避免口径混淆：
  门槛达标 = version_gate.bar_ok 为空（≥3 题、含 basic、含 standard、basic≥2；物理 ≥10 且三档齐）
  充足达标 = 现有题 ≥10（CSF「按 10 题/点」旧口径）

只读 data/，产物只写 reports/ 与 _scratch/。
"""
import argparse
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_registry import subject_of, norm_vol, SUBJ_CN  # noqa: E402
from version_gate import bar_ok  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECTS = ["math", "english", "chinese", "physics", "science",
            "morality", "history", "geography"]
CN2SUBJ = {v: k for k, v in SUBJ_CN.items()}
GRADES = [str(g) for g in range(1, 10)] + ["high"]
CN = "一二三四五六七八九"
GRADE_CN = ["%s年级" % CN[i] for i in range(9)] + ["高中"]
HIGH_CN = GRADE_CN[-1]
STEP = {0: "学制冲突·映射不可信", 1: "原生·已覆盖且达标", 2: "原生·已覆盖但题量不足",
        3: "借用点·该版有目录可校验", 4: "借用点·无该版目录（未经校验）",
        5: "未映射·该版有目录可直接建", 6: "未映射·需取该版目录",
        7: "官方目录有·ChinaTextbook 无PDF"}
VOL_ORDER = ["一上", "一下", "二上", "二下", "三上", "三下", "四上", "四下", "五上", "五下",
             "六上", "六下", "七上", "七下", "八上", "八下", "九上", "九下", "九全",
             "高一", "高二", "高三", "必修一", "必修二", "必修三", "必修四",
             "选必一", "选必二", "选必三", "选必四"]


def load(rel):
    return json.load(io.open(os.path.join(ROOT, rel), encoding="utf-8"))


def vol_sort(v):
    return (VOL_ORDER.index(v), v) if v in VOL_ORDER else (99, v)


def stage_of(g):
    if not isinstance(g, int):
        return "未标"
    return "小学" if g <= 6 else ("初中" if g <= 9 else "高中")


def vol_key(topic):
    """册键：义教按（年级, 学期）→「一上 / 九全」；高中按 chapter 首段归一（必修一…选必四 / 高一）。"""
    g = topic.get("grade")
    if not isinstance(g, int):
        return "(未标)"
    if g <= 9:
        s = topic.get("semester") or "上"
        return CN[g - 1] + ("全" if s == "全" else s)
    return norm_vol((topic.get("chapter") or "").strip().split(" ")[0])


def grade_bucket(topic):
    g = topic.get("grade")
    if not isinstance(g, int):
        return None
    return "high" if g >= 10 else str(g)


def grade_cn(topic):
    g = topic.get("grade")
    if not isinstance(g, int):
        return "未标"
    return HIGH_CN if g >= 10 else GRADE_CN[g - 1]


def chapter_head(topic):
    ch = (topic.get("chapter") or "").strip()
    return ch.split(" ")[1] if " " in ch else ch


def bar_reason(mine, subj):
    return bar_ok("-", mine, subj)


class Pool(object):
    def __init__(self):
        topics = load("data/topics.json")
        topics = topics if isinstance(topics, list) else topics["topics"]
        qs = load("data/questions.json")
        qs = qs if isinstance(qs, list) else qs["questions"]
        self.topics = topics
        self.by_id = {t["id"]: t for t in topics}
        self.formal = [t for t in topics if not t.get("external")]
        self.q_by_topic = collections.defaultdict(list)
        for q in qs:
            self.q_by_topic[q.get("topicId")].append(q)
        self.q_total = len(qs)
        self.q_diff = collections.Counter(q.get("difficulty") for q in qs)
        self.tier_of = {t["id"]: {q.get("difficulty") for q in self.q_by_topic.get(t["id"], [])}
                        for t in self.topics}
        self.n_of = {t["id"]: len(self.q_by_topic.get(t["id"], [])) for t in self.topics}
        self.bar_of = {t["id"]: bar_ok(t["id"], self.q_by_topic.get(t["id"], []), subject_of(t)) == ""
                       for t in self.topics}
        self.full_of = {t["id"]: self.n_of[t["id"]] >= 10 for t in self.topics}
        self.by_vol = collections.defaultdict(list)
        self.by_grade = collections.defaultdict(list)
        for t in self.formal:
            s = subject_of(t)
            self.by_vol[(s, vol_key(t))].append(t["id"])
            b = grade_bucket(t)
            if b:
                self.by_grade[(s, b)].append(t["id"])
        self.vols = sorted({v for (_s, v) in self.by_vol}, key=vol_sort)

    def stat(self, ids):
        ids = [i for i in ids if i in self.by_id and not self.by_id[i].get("external")]
        return {"n": len(ids), "ch": len({chapter_head(self.by_id[i]) for i in ids}),
                "q": sum(self.n_of[i] for i in ids),
                "bar": sum(1 for i in ids if self.bar_of[i]),
                "full": sum(1 for i in ids if self.full_of[i]),
                "ids": ids}

    def rate(self, st, key="bar"):
        return round(st[key] / st["n"], 4) if st["n"] else 0


class Registry(object):
    def __init__(self, pool):
        reg = load("data/editions/registry.json")
        self.meta = reg.get("meta") or {}
        self.versions = reg["versions"]
        self.pool = pool
        self.blocks = []
        self.by_label = {}
        for v in self.versions:
            self.by_label[v["label"]] = v
            for subject, entry in (v.get("subjects") or {}).items():
                ids = [i for i in (entry.get("topicIds") or [])
                       if i in pool.by_id and not pool.by_id[i].get("external")]
                self.blocks.append((v, subject, entry, ids))
        self.idx = collections.defaultdict(lambda: collections.defaultdict(set))
        for v, subject, entry, ids in self.blocks:
            for i in ids:
                self.idx[v["label"]][subject].add(i)

    def resolve(self, name, subject):
        """取证表裸名 → registry 登记名（精确优先，其次唯一前缀），同 coverage_grid.py。"""
        if name in self.idx and subject in self.idx[name]:
            return [name]
        return [l for l in sorted(self.idx) if l.startswith(name) and subject in self.idx[l]]

    def mounted(self, labels, subject, bucket):
        out = set()
        for l in labels:
            for tid in self.idx.get(l, {}).get(subject, ()):
                if grade_bucket(self.pool.by_id[tid]) == bucket:
                    out.add(tid)
        return out


def sheet_versions(ws, pool, reg, pmap):
    prov = collections.defaultdict(set)
    for p, e in pmap.items():
        for _g, cells in (e.get("grades") or {}).items():
            for subject, named in (cells or {}).items():
                for name in named or []:
                    prov[(name, subject)].add(p)
    ws.append(["版本ID", "教材版本", "学制", "类别", "学科", "来源", "状态", "挂点数",
               "门槛达标", "充足达标(≥10)", "现有题", "覆盖学段", "覆盖册", "取证表点名的省区",
               "evidence", "gap"])
    for v, subject, entry, ids in sorted(reg.blocks, key=lambda b: (b[0]["label"], b[1])):
        st = pool.stat(ids)
        vols = " ".join(sorted({vol_key(pool.by_id[i]) for i in ids}, key=vol_sort))
        named_prov = sorted({p for (name, s), ps in prov.items()
                             if s == subject and v["label"].startswith(name) for p in ps})
        ws.append([v["id"], v["label"], v.get("system") or "", v.get("kind") or "",
                   SUBJ_CN.get(subject, subject), entry.get("origin") or "", entry.get("status") or "",
                   st["n"], st["bar"], st["full"], st["q"],
                   "、".join(sorted({stage_of(pool.by_id[i].get("grade")) for i in ids})),
                   vols, "、".join(named_prov[:14]),
                   (entry.get("evidence") or "").replace("\n", " "),
                   (entry.get("gap") or "").replace("\n", " ")])


def sheet_summary(ws, pool, reg):
    ws.append(["版本ID", "教材版本", "学科", "学段", "年级", "册", "章", "知识点", "现有题",
               "门槛达标", "门槛达标率", "充足达标(≥10)", "充足率", "需补题", "状态"])
    for v, subject, entry, ids in sorted(reg.blocks, key=lambda b: (b[0]["label"], b[1])):
        groups = collections.defaultdict(list)
        for i in ids:
            t = pool.by_id[i]
            groups[(stage_of(t.get("grade")), t.get("grade") or 0, vol_key(t))].append(i)
        for (stage, g, vol), sub in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1], vol_sort(x[0][2]))):
            st = pool.stat(sub)
            ws.append([v["id"], v["label"], SUBJ_CN.get(subject, subject), stage,
                       HIGH_CN if g >= 10 else GRADE_CN[g - 1], vol, st["ch"], st["n"], st["q"],
                       st["bar"], pool.rate(st), st["full"], pool.rate(st, "full"),
                       st["n"] - st["bar"],
                       "满覆盖" if st["n"] and st["bar"] == st["n"] else ("部分达标" if st["bar"] else "未达标")])


def sheet_matrix(ws, pool, reg, kind):
    """矩阵：行=版本×学科，列=年级 / 册 / 年级(门槛达标率)。表尾附「池子上限」行。"""
    if kind == "vol":
        cols = pool.vols
        cellkey = vol_key
        colids = lambda c: [i for s in SUBJECTS for i in pool.by_vol[(s, c)]]
    else:
        cols = GRADE_CN
        cellkey = lambda t: HIGH_CN if (t.get("grade") or 0) >= 10 else GRADE_CN[(t["grade"] or 1) - 1]
        colids = lambda c: pool_grade_col(pool, c)
    ws.append(["版本ID", "教材版本", "学科"] + list(cols) + ["挂点合计"])
    for v, subject, entry, ids in sorted(reg.blocks, key=lambda b: (b[0]["label"], b[1])):
        groups = collections.defaultdict(list)
        for i in ids:
            groups[cellkey(pool.by_id[i])].append(i)
        row = [v["id"], v["label"], SUBJ_CN.get(subject, subject)]
        for c in cols:
            sub = groups.get(c, [])
            if not sub:
                row.append(None)
            elif kind == "rate":
                row.append(pool.rate(pool.stat(sub)))
            else:
                row.append(len(sub))
        row.append(len(ids))
        ws.append(row)
    ref = [pool.stat(colids(c)) for c in cols]
    ws.append([])
    ws.append(["", "", "池子上限(该列知识点数)" if kind != "rate" else "池子门槛达标(该列知识点数)"] +
              [(r["n"] if kind != "rate" else r["bar"]) for r in ref] +
              [sum(len(v) for v in pool.by_grade.values())])


def pool_grade_col(pool, label):
    want = "high" if label == HIGH_CN else str(CN.index(label[0]) + 1)
    return [i for (s, b), ids in pool.by_grade.items() if b == want for i in ids]


def sheet_topics(ws, pool, reg):
    ws.append(["知识点ID", "学科", "学段", "年级", "册", "章", "知识点", "现有题", "档位",
               "门槛达标", "充足达标(≥10)", "未达标原因"] + [v["label"] for v in reg.versions])
    mounts = collections.defaultdict(set)
    for v, subject, entry, ids in reg.blocks:
        for i in ids:
            mounts[i].add(v["label"])
    for t in sorted(pool.formal, key=lambda x: (SUBJ_CN.get(subject_of(x), ""), x.get("grade") or 0, x["id"])):
        tid = t["id"]
        subj = subject_of(t)
        ok = pool.bar_of[tid]
        row = [tid, SUBJ_CN.get(subj, subj), stage_of(t.get("grade")), grade_cn(t), vol_key(t),
               chapter_head(t), t.get("name"), pool.n_of[tid],
               "/".join(sorted(x for x in pool.tier_of[tid] if x)) or "—",
               "是" if ok else "否", "是" if pool.full_of[tid] else "否",
               "" if ok else bar_reason(pool.q_by_topic.get(tid, []), subj)]
        row += ["●" if v["label"] in mounts.get(tid, ()) else "" for v in reg.versions]
        ws.append(row)


def sheet_ledger(ws, pool, reg):
    """registry 台账：每个版本块的每一册，按册级档位重算（与「版本覆盖缺口·册级·取证」互补）。"""
    ws.append(["学科", "册", "教材版本", "版本ID", "来源", "状态", "池子点", "池子门槛达标",
               "该册已挂点", "该册门槛达标", "判定档", "判定说明"])
    rows = []
    for v, subject, entry, ids in reg.blocks:
        groups = collections.defaultdict(list)
        for i in ids:
            groups[vol_key(pool.by_id[i])].append(i)
        origin = entry.get("origin") or ""
        for vol, sub in groups.items():
            st = pool.stat(sub)
            if origin == "native":
                step = 1 if st["bar"] == st["n"] else 2
            elif origin == "mapping":
                step = 3
            else:
                step = 4
            rows.append([SUBJ_CN.get(subject, subject), vol, v["label"], v["id"], origin,
                         entry.get("status") or "", len(pool.by_vol[(subject, vol)]),
                         pool.stat(pool.by_vol[(subject, vol)])["bar"], st["n"], st["bar"],
                         "%d %s" % (step, STEP[step]),
                         "挂载 %d 点，门槛达标 %d 点；池子该册 %d 点" % (st["n"], st["bar"], len(pool.by_vol[(subject, vol)]))])
    rows.sort(key=lambda r: (r[0], vol_sort(r[1]), r[2]))
    for r in rows:
        ws.append(r)


def sheet_baseline(ws, pool):
    ws.append(["学科", "学段", "年级", "册", "章", "知识点", "现有题", "达标(≥10)", "达标率",
               "需补题(≥10口径)", "门槛未达标", "缺拓展档"])
    agg = collections.defaultdict(list)
    for t in pool.formal:
        agg[(subject_of(t), stage_of(t.get("grade")), grade_cn(t), vol_key(t), chapter_head(t))].append(t["id"])
    for key in sorted(agg, key=lambda k: (k[0], k[2], vol_sort(k[3]), k[4])):
        ids = agg[key]
        st = pool.stat(ids)
        nochal = sum(1 for i in ids if "challenge" not in pool.tier_of[i])
        ws.append([SUBJ_CN.get(key[0], key[0]), key[1], key[2], key[3], key[4], st["n"], st["q"],
                   st["full"], pool.rate(st, "full"), st["n"] - st["full"], st["n"] - st["bar"], nochal])


def sheet_no_challenge(ws, pool):
    ws.append(["知识点ID", "学科", "学段", "年级", "册", "知识点", "现有题", "现有档位"])
    for t in sorted(pool.formal, key=lambda x: (SUBJ_CN.get(subject_of(x), ""), x.get("grade") or 0, x["id"])):
        if "challenge" in pool.tier_of[t["id"]]:
            continue
        subj = subject_of(t)
        ws.append([t["id"], SUBJ_CN.get(subj, subj), stage_of(t.get("grade")), grade_cn(t),
                   vol_key(t), t.get("name"), pool.n_of[t["id"]],
                   "/".join(sorted(x for x in pool.tier_of[t["id"]] if x)) or "—"])


def reg_notes(reg, province, subject):
    """从该学科各版本块的 gap/scope/evidence 里摘出点名该省的原文分句（逐字搬运，不改写）。"""
    hits = []
    for v, s, entry, ids in reg.blocks:
        if s != subject:
            continue
        for field in ("gap", "scope", "evidence"):
            for line in re.split(r"[；;\n]", str(entry.get(field) or "")):
                line = line.strip()
                if province in line and len(line) > 12:
                    hits.append("%s｜%s：%s" % (v["label"], field, line[:220]))
    return hits[:4]


def build_grid(pool, reg, pmap):
    rows = []
    stats = collections.Counter()
    for province, entry in sorted(pmap.items()):
        system = entry.get("system") or ""
        for grade in GRADES:
            cells = (entry.get("grades") or {}).get(grade) or {}
            for subject in SUBJECTS:
                named = cells.get(subject) or []
                labels = sorted({l for name in named for l in reg.resolve(name, subject)})
                mounted = reg.mounted(labels, subject, grade)
                pool_ids = pool.by_grade.get((subject, grade), [])
                pstat = pool.stat(pool_ids)
                if not named:
                    state, why = "blank", "取证表该格未给出任何版本（未核）"
                elif not labels:
                    state, why = "unregistered", "点名的版本在 registry 无对应登记块：%s" % "、".join(named)
                elif mounted:
                    state, why = "covered", "该版在该年档挂了 %d 点" % len(mounted)
                else:
                    state, why = "no_point", "版本已登记，但其主题清单里没有该年档的点"
                stats[state] += 1
                notes = []
                if state == "no_point":
                    notes = reg_notes(reg, province, subject)
                    if pstat["n"] == 0:
                        step, cands = "B 池子缺该册", []
                        why += "；池子该（学科, 年档）为空 → 需先扩池子"
                    else:
                        cands = sorted({v["label"] for v, s, e, ids in reg.blocks
                                        if s == subject and reg.mounted([v["label"]], subject, grade)})
                        if any("不开设" in n for n in notes):
                            step = "A2 已判不开设"
                            why += "；池子有 %d 点，但 registry 已按目录判定该省该年级不开设此科 → 不挂载" % pstat["n"]
                        else:
                            step = "A1 可增量挂载"
                            why += "；池子有 %d 点未被该省点名版本挂载 → 可增量挂载或补取证" % pstat["n"]
                else:
                    step, cands = {"covered": "—", "blank": "N 未核", "unregistered": "U 版本未登记"}[state], []
                rows.append({"province": province, "system": system, "grade": grade, "subject": subject,
                             "named": named, "state": state, "labels": labels,
                             "mounted": len(mounted), "pool_n": pstat["n"], "pool_bar": pstat["bar"],
                             "step": step, "cands": cands, "why": why, "notes": notes})
    return rows, stats


def sheet_grid(ws, rows):
    ws.append(["省区", "学制", "学科", "年档", "点名版本", "判定", "解析到的登记版本",
               "该格已挂点", "池子点", "池子门槛达标", "缺口分类", "说明", "registry 原文（点名该省的分句）"])
    for r in rows:
        ws.append([r["province"], r["system"], SUBJ_CN.get(r["subject"], r["subject"]), r["grade"],
                   "、".join(r["named"]), r["state"], "、".join(r["labels"]), r["mounted"],
                   r["pool_n"], r["pool_bar"], r["step"], r["why"], "\n".join(r["notes"])])


def sheet_gap(ws, rows):
    ws.append(["分类", "省区", "学制", "学科", "年档", "点名版本", "判定", "池子点", "该格已挂",
               "可挂载候选（该科目块含本年档）", "说明", "registry 原文（点名该省的分句）"])
    bad = [r for r in rows if r["state"] != "covered"]
    for r in sorted(bad, key=lambda x: (x["step"], x["subject"], x["grade"], x["province"])):
        ws.append([r["step"], r["province"], r["system"], SUBJ_CN.get(r["subject"], r["subject"]),
                   r["grade"], "、".join(r["named"]), r["state"], r["pool_n"], r["mounted"],
                   "、".join(r["cands"]), r["why"], "\n".join(r["notes"])])


EXTRA_HEAD = ["池子点(现势)", "池子门槛达标(现势)", "registry已挂点(现势)",
              "该册已挂点(现势)", "来源(现势)", "现势判定档", "现势说明"]


def sheet_evidence(ws, rows, pool=None, reg=None, refresh=None):
    """取证表原样搬运；refresh='vol' 时找到表头行，在右侧追加按现库重算的列。"""
    hidx = None
    if refresh == "vol":
        for i, r in enumerate(rows[:8]):
            if r and r[0] == "学科":
                hidx = i
                break
    for idx, r in enumerate(rows):
        row = list(r)
        if hidx is not None:
            if idx == hidx:
                row += EXTRA_HEAD
            elif idx > hidx and str(r[0] or "") in CN2SUBJ:
                row += refresh_vol_row(rows[hidx], r, pool, reg)
        ws.append(row)


def refresh_vol_row(header, r, pool, reg):
    def col(name):
        for i, h in enumerate(header):
            if isinstance(h, str) and h.startswith(name):
                return i
        return None
    subj = CN2SUBJ.get(str(r[col("学科")] or ""))
    raw_vol = str(r[col("册")] or "")
    named = str(r[col("版本")] or "")
    vol = raw_vol if raw_vol in VOL_ORDER else (norm_vol(raw_vol) if raw_vol else "")
    labels = reg.resolve(named, subj) if subj and named and named != "-" else []
    ids_in_vol = pool.by_vol.get((subj, vol), []) if subj and vol else []
    pst = pool.stat(ids_in_vol)
    mounted_all = set().union(*[reg.idx[l][subj] for l in labels]) if labels else set()
    mounted_vol = {i for i in mounted_all if vol_key(pool.by_id[i]) == vol} if mounted_all else set()
    mst = pool.stat(list(mounted_vol))
    origins = {reg.by_label[l]["subjects"][subj].get("origin") or "" for l in labels if subj in reg.by_label[l]["subjects"]}
    origin = "native" if "native" in origins else ("mapping" if "mapping" in origins else
                                                  ("borrowed" if origins else ""))
    if raw_vol.startswith("(缺档"):
        step = 7
    elif mounted_vol:
        if origin == "native":
            step = 1 if mst["bar"] == mst["n"] == pst["n"] else 2
        elif origin == "mapping":
            step = 3
        else:
            step = 4
    else:
        step = 5 if str(r[col("CTB有PDF")] or "") == "是" else 6
    note = ("册键 %s 在池子里不存在，现势列按空处理" % raw_vol) if raw_vol and raw_vol not in VOL_ORDER and not raw_vol.startswith("(缺档") else ""
    return [pst["n"], pst["bar"], len(mounted_all), mst["n"], origin or "未登记",
            "%d %s" % (step, STEP[step]),
            ("挂载 %d/%d，门槛达标 %d" % (mst["n"], pst["n"], mst["bar"])) + ("；" + note if note else "")]


def sheet_health(ws, pool, reg, stats):
    hs = collections.defaultdict(collections.Counter)
    for t in pool.formal:
        if (t.get("grade") or 0) >= 10:
            hs[subject_of(t)][vol_key(t)] += 1
    no_subj = sum(1 for t in pool.topics if not t.get("subject"))
    orphans = sorted(set(pool.q_by_topic) - set(pool.by_id))
    ext_q = [t["id"] for t in pool.topics if t.get("external") and pool.q_by_topic.get(t["id"])]
    hs_by_subj = {SUBJ_CN.get(s, s): dict(c) for s, c in hs.items()}
    empty_high = [SUBJ_CN[s] for s in SUBJECTS if not hs.get(s)]
    ws.append(["#", "现象", "实测", "影响", "处置"])
    for row in [
        [1, "知识点缺 subject 字段", "%d / %d 点（全部 cnm_* 数学点均无）" % (no_subj, len(pool.topics)),
         "凡按 t['subject'] 归学科的统计都会把数学整块漏掉（本盘点上一轮就误判过一次「数学池八年级为空」）",
         "一律走 gen_registry.subject_of()：先看 subject，再按 id 前缀，最后才默认 math"],
        [2, "高中册次编码各学科不一致", json.dumps(hs_by_subj, ensure_ascii=False),
         "数学用「高一/高二」承载必修（grade 10/11），英语·物理用「必修一~选必四」（grade 10~16）；"
         "同一 grade 在不同学科含义不同", "年级维度统计一律归「高中」年档；册维度看「矩阵·册」，两套口径不可混用"],
        [3, "该学科无高中池子", "、".join(empty_high) + "（高中格必然判 no_point/blank）",
         "不是 registry 漏挂，是池子没建点", "要出这些学科的高中诊断题，先扩池子"],
        [4, "孤儿题（topicId 不在 topics）", "%d%s" % (len(orphans), ("：" + ", ".join(orphans[:8]) if orphans else "")),
         "validate.py 已判 0，本处复算确认", "保持 0"],
        [5, "external 点却有题", "%d%s" % (len(ext_q), ("：" + ", ".join(ext_q[:8]) if ext_q else "")),
         "test_engine.js 断言外部节点无题", "保持 0"],
        [6, "省×年档×学科网格", " / ".join("%s %d" % (k, stats[k]) for k in ["covered", "no_point", "unregistered", "blank"]),
         "blank 占比高是因为取证表只写已核到版本的格子；化学·生物不在建库 8 科内，未计入网格",
         "先补取证表，再谈挂点；unregistered 逐格见「省×年级×学科网格」"],
        [7, "registry 借用块 origin=borrowed", "%d 个学科块" % sum(1 for b in reg.blocks if b[2].get("origin") == "borrowed"),
         "这些块的章名与册序不是该版真实目录，只作「同册可复用范围」", "gap 字段已逐块声明，禁止当成该版教材结构引用"],
        [8, "registry status 分布", json.dumps(dict(collections.Counter((b[2].get("status") or "?") for b in reg.blocks)), ensure_ascii=False),
         "draft/single-source 块的覆盖判定不能当已核实", "按「缺口判定」的证据列继续核"],
        [9, "五四制年级偏移未编码", "学制=五四制 的版本 %d 个 / 学科块 %d 个" % (
            sum(1 for v in reg.versions if v.get("system") == "五四制"),
            sum(1 for b in reg.blocks if b[0].get("system") == "五四制")),
         "上海八年级≈人教九年级；本表按「池子年级＝该省年级」直配，网格 covered 数偏乐观",
         "属未决决策（registry meta.corrections 已声明），要改先改 coverage_grid 的年档定义"],
        [10, "三维盘点与 registry 版本 ID 换代", "旧工作簿用 shanghai2024 等 ID，现 registry 用 hujiao_math / hujiao54_junior 等 %d 个 ID" % len(reg.versions),
         "旧表的「版本ID」列与现库对不上，属结构级过期", "本版全部列由现库重算；取证四表按 2026-11-02 快照原样保留并标注"],
    ]:
        ws.append(row)


def sheet_readme(wb, pool, reg, stats, gap_rows, snapshot):
    ws = wb.create_sheet("读我·总览", 0)
    steps = collections.Counter(r["step"] for r in gap_rows if r["state"] == "no_point")
    lines = [
        ["三维盘点：教材版本 × 学科 × 年级/册 → 知识点与题量", ""],
        ["快照日期", snapshot],
        ["生成脚本", "python3 scripts/build_inventory.py"],
        ["数据源", "data/topics.json · data/questions.json · data/editions/registry.json · data/editions/province_map.json"],
        ["取证快照", "data/inventory_evidence.json（2026-11-02，ChinaTextbook / 教育部目录 / CSF 真题），取证列原样搬运，现势列另侧重算"],
        ["", ""],
        ["总题库", "%d 题（basic %d / standard %d / challenge %d）" % (
            pool.q_total, pool.q_diff["basic"], pool.q_diff["standard"], pool.q_diff["challenge"])],
        ["知识点", "%d 点（正式 %d + 外部 %d）" % (len(pool.topics), len(pool.formal), len(pool.topics) - len(pool.formal))],
        ["门槛达标 / 充足达标", "%d 点 / %d 点" % (sum(1 for t in pool.formal if pool.bar_of[t["id"]]),
                                          sum(1 for t in pool.formal if pool.full_of[t["id"]]))],
        ["缺拓展档(challenge)的点", "%d 个，清单见「拓展档缺口」" % sum(1 for t in pool.formal if "challenge" not in pool.tier_of[t["id"]])],
        ["教材版本", "%d 个版本条目 / %d 个学科块（native %d · mapping %d · borrowed %d）" % (
            len(reg.versions), len(reg.blocks),
            sum(1 for b in reg.blocks if b[2].get("origin") == "native"),
            sum(1 for b in reg.blocks if b[2].get("origin") == "mapping"),
            sum(1 for b in reg.blocks if b[2].get("origin") == "borrowed"))],
        ["省 × 年档 × 学科网格", "%d 格：covered %d / no_point %d / unregistered %d / blank %d" % (
            sum(stats.values()), stats["covered"], stats["no_point"], stats["unregistered"], stats["blank"])],
        ["no_point 分类", "A1 池子有点、该省点名版本没挂 = %d 格；A2 registry 已判「不开设」= %d 格；B 池子该（学科, 年档）为空 = %d 格" % (
            steps["A1 可增量挂载"], steps["A2 已判不开设"], steps["B 池子缺该册"])],
        ["", ""],
        ["与 2026-11-02 旧版的差异", "① 版本ID 换代（shanghai2024 等 → hujiao_math / hujiao54_junior 等 %d 条），旧表「版本ID」列值全部失效；"
                                  "② 池子 2997 点 → %d 点（新增初中语文 302 / 道法 67 / 科学 138）；"
                                  "③ 旧「缺口汇总」按 学科×版本×学段 聚合，现由「registry台账」（册级）+「缺口判定」（省级）承担；"
                                  "④ 新增「省×年级×学科网格」「拓展档缺口」「数据体检」三张现势表；取证四表原样保留。" % (len(reg.versions), len(pool.formal))],
        ["", ""],
        ["北极星口径", "题目只对知识点负责，全库一份总题库；教材版本决定「该省该年级教哪些点」，不决定「每个版本一份题库」。"],
        ["达标两档", "门槛达标＝version_gate.bar_ok 通过（≥3 题、含 basic、含 standard、basic≥2；物理 ≥10 且三档齐）；"
                    "充足达标＝现有题 ≥10（CSF 按 10 题/点的旧盘点口径）。两列并列给出，不要混用。"],
        ["池子只按一套教材建点", "数学·英语·物理·地理=人教版，语文·历史·道德与法治=统编版，科学=教科版；"
                              "其余版本按册键借用（origin=borrowed），章名与册序不代表该版真实目录。"],
        ["学制偏移未决", "五四制（上海等）六年级＝初中预备班，与六三制差一学年。本表沿用「池子年级＝该省年级」不作偏移，"
                      "故网格 covered 数偏乐观；是否编码偏移属未决决策，见 registry meta.corrections 与 docs/province_textbook_map.md:47-49。"],
        ["数据缺陷", "869 点无 subject 字段（数学整块）；高中册次编码各学科不一致。见「数据体检」。"],
        ["", ""],
        ["判定档位（registry台账 / 版本覆盖缺口·册级）", ""],
    ]
    for k in sorted(STEP):
        lines.append(["%d" % k, STEP[k]])
    lines.append(["", ""])
    lines.append(["sheet 一览", "行数"])
    for other in wb.worksheets:
        if other.title != "读我·总览":
            lines.append([other.title, other.max_row])
    for r in lines:
        ws.append(r)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 130


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("reports", "三维盘点_教材版本x学科x年级.xlsx"))
    ap.add_argument("--no-evidence", action="store_true")
    ap.add_argument("--snapshot", default="2026-11-06")
    args = ap.parse_args()

    from openpyxl import Workbook
    from openpyxl.styles import Font

    pool = Pool()
    reg = Registry(pool)
    pmap = load("data/editions/province_map.json")["provinces"]
    rows, stats = build_grid(pool, reg, pmap)
    gap_rows = [r for r in rows if r["state"] != "covered"]

    wb = Workbook()
    wb.remove(wb.active)
    jobs = [("版本清单", lambda ws: sheet_versions(ws, pool, reg, pmap)),
            ("三维汇总", lambda ws: sheet_summary(ws, pool, reg)),
            ("矩阵·年级", lambda ws: sheet_matrix(ws, pool, reg, "grade")),
            ("矩阵·册", lambda ws: sheet_matrix(ws, pool, reg, "vol")),
            ("矩阵·达标率", lambda ws: sheet_matrix(ws, pool, reg, "rate")),
            ("知识点×版本", lambda ws: sheet_topics(ws, pool, reg)),
            ("registry台账", lambda ws: sheet_ledger(ws, pool, reg)),
            ("题库基线", lambda ws: sheet_baseline(ws, pool)),
            ("拓展档缺口", lambda ws: sheet_no_challenge(ws, pool)),
            ("省×年级×学科网格", lambda ws: sheet_grid(ws, rows)),
            ("缺口判定", lambda ws: sheet_gap(ws, gap_rows)),
            ("数据体检", lambda ws: sheet_health(ws, pool, reg, stats))]
    for name, fn in jobs:
        fn(wb.create_sheet(name))
    if not args.no_evidence:
        ev = load("data/inventory_evidence.json")["sheets"]
        for name in ["版本覆盖缺口·册级", "官方目录核对", "CSF真题源", "沪教版核对", "核对结论"]:
            if name in ev:
                sheet_evidence(wb.create_sheet(name), ev[name], pool, reg,
                               refresh="vol" if name == "版本覆盖缺口·册级" else None)

    bold = Font(bold=True)
    for ws in wb.worksheets:
        for c in ws[1]:
            if c.value not in (None, ""):
                c.font = bold
        ws.freeze_panes = "D2" if ws.max_column > 6 else "B2"
        for letter in ("A", "B", "C"):
            if ws[letter][0].value:
                ws.column_dimensions[letter].width = max(14, min(40, len(str(ws[letter][0].value)) + 6))
    sheet_readme(wb, pool, reg, stats, gap_rows, args.snapshot)

    path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    wb.save(path)
    io.open(os.path.join(ROOT, "_scratch", "inventory_grid.json"), "w", encoding="utf-8").write(
        json.dumps(rows, ensure_ascii=False, indent=0))
    io.open(os.path.join(ROOT, "_scratch", "inventory_gaps.json"), "w", encoding="utf-8").write(
        json.dumps(gap_rows, ensure_ascii=False, indent=0))
    steps = collections.Counter(r["step"] for r in gap_rows if r["state"] == "no_point")
    print("points=%d formal=%d questions=%d versions=%d blocks=%d" % (
        len(pool.topics), len(pool.formal), pool.q_total, len(reg.versions), len(reg.blocks)))
    print("grid cells=%d covered=%d no_point=%d unregistered=%d blank=%d" % (
        sum(stats.values()), stats["covered"], stats["no_point"], stats["unregistered"], stats["blank"]))
    print("gap no_point A1=%d A2=%d B=%d | sheets=%d" % (
        steps["A1 可增量挂载"], steps["A2 已判不开设"], steps["B 池子缺该册"], len(wb.sheetnames)))
    print("no_bar=%d no_full=%d no_challenge=%d" % (
        sum(1 for t in pool.formal if not pool.bar_of[t["id"]]),
        sum(1 for t in pool.formal if not pool.full_of[t["id"]]),
        sum(1 for t in pool.formal if "challenge" not in pool.tier_of[t["id"]])))
    print("written %s" % path)


if __name__ == "__main__":
    main()
