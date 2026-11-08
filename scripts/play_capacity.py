#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""孩子端 /play/ 的题量容量基线。

与 scripts/capacity_gap.py 的区别：那个是 diagnose/ 家长端的历史口径
（confirm=3、全题型、40 题/点）；本脚本是孩子端口径——只派 choice + numeric
（孩子不自评 short/self），confirm 由家长在档案里设（2/3/5）。

引擎规则见 diagnose/engine.js:237-278：难度优先于「没出过」，避让只在同档内
生效，所以不重样轮次由档位数量决定，不是由总题数决定。
  全对路径每轮吃 1 standard + (confirm-1) challenge
  薄弱路径每轮吃 1 standard + 1 basic
两条路径都要撑满 R 轮 => basic R / standard R / challenge (confirm-1)*R。

用法（Windows / Git Bash）：
  PYTHONIOENCODING=utf-8 python scripts/play_capacity.py --confirm 5 --out _scratch/play_capacity.txt
"""
import argparse
import collections
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECT = {"cnm": "math", "cne": "english", "cnc": "chinese", "cnp": "physics",
           "cns": "science", "cnd": "morality", "cnh": "history", "cng": "geography"}
AUTO = ("choice", "numeric")
ROUNDS = 10


def load(name):
    obj = json.load(io.open(os.path.join(ROOT, "data", name), encoding="utf-8"))
    if isinstance(obj, list):
        return obj
    return obj.get("topics") or obj.get("nodes") or obj.get("questions")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", type=int, default=5, choices=(2, 3, 5),
                    help="连续答对几道判掌握；决定 challenge 档需要 (confirm-1)*10 道")
    ap.add_argument("--all-types", action="store_true",
                    help="把 short/self 也算进容量（孩子端默认不算）")
    ap.add_argument("--out", help="写入 UTF-8 文本报告；省略则打印")
    ap.add_argument("--json", help="同时写出逐点明细 JSON")
    args = ap.parse_args()

    topics, questions = load("topics.json"), load("questions.json")
    keep = None if args.all_types else set(AUTO)
    target = {"basic": ROUNDS, "standard": ROUNDS, "challenge": (args.confirm - 1) * ROUNDS}

    tiers = collections.defaultdict(lambda: collections.defaultdict(list))
    for q in questions:
        tiers[q["topicId"]][q["difficulty"]].append(q)

    rows = []
    for t in topics:
        if t.get("external"):
            continue
        d = tiers[t["id"]]
        have, gap = {}, {}
        for tier, n in target.items():
            qs = d.get(tier, [])
            if keep is not None:
                qs = [q for q in qs if q["type"] in keep]
            have[tier] = len(qs)
            gap[tier] = max(0, n - len(qs))
        rows.append({
            "id": t["id"], "name": t.get("name", ""),
            "subject": t.get("subject") or SUBJECT.get(t["id"].split("_")[0], "?"),
            "grade": t.get("grade"), "chapter": t.get("chapter", ""),
            "have": have, "gap": gap, "gap_total": sum(gap.values()),
            "rounds_allcorrect": min(have["standard"],
                                     have["challenge"] // (args.confirm - 1)),
            "rounds_weak": min(have["standard"], have["basic"]),
        })

    lines = []

    def e(text=""):
        lines.append(text)

    total_have = collections.Counter()
    total_gap = collections.Counter()
    for r in rows:
        total_have.update(r["have"])
        total_gap.update(r["gap"])
    per_point = sum(target.values())

    e("孩子端 /play/ 题量容量基线")
    e("confirm=%d  题型=%s  不重样轮次=%d" % (
        args.confirm, "全题型" if args.all_types else "choice+numeric", ROUNDS))
    e("知识点 %d · 题库 %d 题（其中计入容量 %d 题）" % (
        len(rows), len(questions), sum(total_have.values())))
    e("目标 %d 题/点 = basic %d + standard %d + challenge %d；终态题库 %d 题" % (
        per_point, target["basic"], target["standard"], target["challenge"],
        len(rows) * per_point))
    e()
    e("== 分档缺口（各档独立算 max(0, 目标-现有)，一档 surplus 不能抵另一档）==")
    for tier in ("basic", "standard", "challenge"):
        e("%-9s 现有 %6d  目标 %6d  缺 %6d" % (
            tier, total_have[tier], target[tier] * len(rows), total_gap[tier]))
    e("合计缺口 %d 道；达标点数 %d / %d" % (
        sum(total_gap.values()), sum(1 for r in rows if r["gap_total"] == 0), len(rows)))
    e()
    e("== 按学科 ==")
    e("学科 | 点数 | 现有计入 | basic缺 | standard缺 | challenge缺 | 合计缺")
    agg = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for r in rows:
        a = agg[r["subject"]]
        a[0] += 1
        a[1] += sum(r["have"].values())
        for i, tier in enumerate(("basic", "standard", "challenge"), 2):
            a[i] += r["gap"][tier]
        a[5] += r["gap_total"]
    for k, a in sorted(agg.items()):
        e(" | ".join([k] + [str(x) for x in a]))
    e("合计 | " + " | ".join(str(sum(a[i] for a in agg.values())) for i in range(6)))
    e()
    e("== confirm 敏感度（%s，10 轮）==" % ("全题型" if args.all_types else "choice+numeric"))
    for cf in (2, 3, 5):
        tg = {"basic": ROUNDS, "standard": ROUNDS, "challenge": (cf - 1) * ROUNDS}
        g = collections.Counter()
        for r in rows:
            for tier, n in tg.items():
                g[tier] += max(0, n - r["have"][tier])
        e("confirm=%d → %d 题/点，终态 %d，缺 %d（basic %d / standard %d / challenge %d）" % (
            cf, sum(tg.values()), len(rows) * sum(tg.values()), sum(g.values()),
            g["basic"], g["standard"], g["challenge"]))

    text = "\n".join(lines) + "\n"
    if args.out:
        p = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
        io.open(p, "w", encoding="utf-8").write(text)
        print("written: %s" % p)
    else:
        print(text)
    if args.json:
        p = os.path.join(ROOT, args.json) if not os.path.isabs(args.json) else args.json
        io.open(p, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("written: %s" % p)


if __name__ == "__main__":
    main()