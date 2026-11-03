# -*- coding: utf-8 -*-
"""题库达标盘点：按「一个总题库、题目挂知识点」的口径统计缺口。

达标线取 tests/test_engine.js 的断言：正式知识点（非 external）每题池
  ≥3 题、含 basic、含 standard；再补一条「除 q1 外至少还有一道 basic」。
advanced 只做统计，不作硬门槛（诊断页到拓展档才用）。

输出 _scratch/bank_gap.md（人读）与 _scratch/bank_gap.json（机读，待补题清单）。
"""
import io
import json
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJ_BY_PREFIX = {"cnm": "数学", "cne": "英语", "ch": "语文", "phy": "物理",
                  "sci": "科学", "mor": "道法", "his": "历史", "geo": "地理"}
STAGE = lambda g: "小学" if g and g <= 6 else ("初中" if g and g <= 9 else ("高中" if g else "未标"))


def subject_of(t):
    s = t.get("subject")
    if s:
        return s
    return SUBJ_BY_PREFIX.get(t["id"].split("_")[0], t["id"].split("_")[0])


def main():
    topics = json.load(io.open(os.path.join(ROOT, "data/topics.json"), encoding="utf-8"))
    topics = topics if isinstance(topics, list) else topics["topics"]
    qs = json.load(io.open(os.path.join(ROOT, "data/questions.json"), encoding="utf-8"))
    qs = qs if isinstance(qs, list) else qs["questions"]

    by_topic = collections.defaultdict(list)
    for q in qs:
        by_topic[q.get("topicId")].append(q)

    formal = [t for t in topics if not t.get("external")]
    ext = [t for t in topics if t.get("external")]

    rows = []
    todo = []
    stat = collections.defaultdict(lambda: collections.Counter())
    for t in formal:
        s = subject_of(t)
        mine = by_topic.get(t["id"], [])
        d = set(q.get("difficulty") for q in mine)
        st = stat[s]
        st["点数"] += 1
        st["题数"] += len(mine)
        if not mine:
            st["零题"] += 1
        if len(mine) < 3:
            st["不足3题"] += 1
        if "basic" not in d:
            st["缺basic"] += 1
        if "standard" not in d:
            st["缺standard"] += 1
        if "advanced" not in d and "challenge" not in d:
            st["缺拓展档"] += 1
        basics = [q for q in mine if q.get("difficulty") == "basic"]
        if mine and len(basics) < 2:
            st["basic只1道"] += 1
        bad = (not mine) or len(mine) < 3 or "basic" not in d or "standard" not in d or len(basics) < 2
        if bad:
            rows.append((s, STAGE(t.get("grade")), t["id"], t.get("name"), len(mine),
                         "/".join(sorted(d)) or "—", t.get("grade")))
            todo.append({"topicId": t["id"], "subject": s, "name": t.get("name"),
                         "grade": t.get("grade"), "semester": t.get("semester"),
                         "n": len(mine), "have": sorted(d),
                         "need": [x for x in ("basic", "standard", "advanced") if x not in d] or ["补至3题"]})

    orphans = sorted(set(by_topic) - set(t["id"] for t in topics))
    ext_with_q = [t["id"] for t in ext if by_topic.get(t["id"])]

    out = ["# 题库达标盘点", "",
           "总题库 %d 题 / %d 知识点（正式 %d + 外部 %d）。达标线：正式知识点 ≥3 题且含 basic+standard，且除 q1 外再有一道 basic。"
           % (len(qs), len(topics), len(formal), len(ext)), ""]
    cols = ["学科", "点数", "题数", "零题", "不足3题", "缺basic", "缺standard", "basic只1道", "缺拓展档"]
    out.append("| " + " | ".join(cols) + " |")
    out.append("|" + "---|" * len(cols))
    for s in sorted(stat, key=lambda x: -stat[x]["零题"] - stat[x]["不足3题"]):
        st = stat[s]
        out.append("| " + " | ".join([s] + [str(st[c]) for c in cols[1:]]) + " |")
    total = collections.Counter()
    for s in stat:
        total.update(stat[s])
    out.append("| **合计** | " + " | ".join("**%d**" % total[c] for c in cols[1:]) + " |")
    out += ["", "## 未达标的点（%d 个）" % len(rows), ""]
    out.append("| 学科 | 学段 | id | 知识点 | 现有题 | 现有档位 |")
    out.append("|---|---|---|---|---|---|")
    for s, stage, tid, name, n, have, _g in rows[:400]:
        out.append("| %s | %s | %s | %s | %d | %s |" % (s, stage, tid, name, n, have))
    if len(rows) > 400:
        out.append("| … | | | 其余 %d 个见 _scratch/bank_gap.json | | |" % (len(rows) - 400))
    out += ["", "## 一致性", "",
            "挂在不存在知识点上的题：%d%s" % (len(orphans), ("（" + ", ".join(orphans[:10]) + "）") if orphans else ""),
            "外部节点却有题（断言要求无题）：%d%s" % (len(ext_with_q), ("（" + ", ".join(ext_with_q[:10]) + "）") if ext_with_q else ""),
            "无 subject 字段、按 id 前缀归学科的点数：%d" % sum(1 for t in formal if not t.get("subject")), ""]
    io.open(os.path.join(ROOT, "_scratch", "bank_gap.md"), "w", encoding="utf-8").write("\n".join(out))
    json.dump(todo, io.open(os.path.join(ROOT, "_scratch", "bank_gap.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("formal=%d below=%d orphans=%d ext_with_q=%d" % (len(formal), len(rows), len(orphans), len(ext_with_q)))


if __name__ == "__main__":
    main()
