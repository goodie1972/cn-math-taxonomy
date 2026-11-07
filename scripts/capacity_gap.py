#!/usr/bin/env python3
"""复算「一次 3 题 × N 次不重样」的题量缺口。

用法（Windows / Git Bash）：
    PYTHONIOENCODING=utf-8 python scripts/capacity_gap.py --out _scratch/capacity_gap.txt

口径见 docs/question-capacity-plan.md。引擎选题规则见 diagnose/engine.js:237-278：
难度优先于「没出过」，避让只在同难度档内生效，故不重样轮次由档位数量决定，
不是由总题数决定。
"""
import argparse
import collections
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECT = {"cnm": "数学", "cne": "英语", "cnc": "语文", "cnp": "物理",
           "cns": "科学", "cnd": "道法", "cnh": "历史", "cng": "地理"}
PER_ROUND = 3          # confirm 默认值，全对路径一次问 3 题
TARGET_ROUNDS = 10     # 用户要求：10 次出题不重样
FLOOR_ROUNDS = 5       # 题型受限点的下限（15 题）


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        obj = json.load(fh)
    if isinstance(obj, list):
        return obj
    return obj.get("topics") or obj.get("nodes") or obj.get("questions")


def stage(grade):
    return "小学" if grade <= 6 else ("初中" if grade <= 9 else "高中")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="写入 UTF-8 文本报告；省略则打印到 stdout")
    ap.add_argument("--json", help="同时写出逐点明细 JSON")
    args = ap.parse_args()

    topics, questions = load("topics.json"), load("questions.json")
    tiers = collections.defaultdict(collections.Counter)
    for q in questions:
        tiers[q["topicId"]][q["difficulty"]] += 1

    lines = []

    def emit(text=""):
        lines.append(text)

    rows = []
    for t in topics:
        c = tiers[t["id"]]
        basic, standard, challenge = c["basic"], c["standard"], c["challenge"]
        total = basic + standard + challenge
        rows.append({
            "id": t["id"], "name": t["name"],
            "subject": SUBJECT.get(t["id"].split("_")[0], t["id"].split("_")[0]),
            "stage": stage(t["grade"]), "book": "%d%s" % (t["grade"], t.get("semester", "")),
            "total": total, "basic": basic, "standard": standard, "challenge": challenge,
            # 现引擎：全对路径每轮吃 1 standard + 2 challenge
            "rounds_now": min(standard, challenge // 2),
            # 现引擎：薄弱路径每轮吃 1 standard + 1 basic
            "rounds_weak": min(standard, basic),
            # 若改成「没出过优先于难度」：只看总数
            "rounds_fresh": total // PER_ROUND,
            "gap_total30": max(0, PER_ROUND * TARGET_ROUNDS - total),
            "gap_tier30": max(0, TARGET_ROUNDS - standard) + max(0, 2 * TARGET_ROUNDS - challenge),
            "gap_tier40": (max(0, TARGET_ROUNDS - standard) + max(0, 2 * TARGET_ROUNDS - challenge)
                           + max(0, TARGET_ROUNDS - basic)),
            "gap_floor15": max(0, PER_ROUND * FLOOR_ROUNDS - total),
            # 阶段目标：5 轮不重样。全对路径 5 standard + 10 challenge = 15 题；
            # 两条路径都要则再加 5 basic = 20 题。
            "gap_tier15": max(0, FLOOR_ROUNDS - standard) + max(0, 2 * FLOOR_ROUNDS - challenge),
            "gap_tier20": (max(0, FLOOR_ROUNDS - standard) + max(0, 2 * FLOOR_ROUNDS - challenge)
                           + max(0, FLOOR_ROUNDS - basic)),
        })

    emit("题量容量缺口 · 复算报告")
    emit("知识点 %d · 题目 %d" % (len(rows), len(questions)))
    emit("目标 %d 题/点（%d 题/次 × %d 次）；受限点下限 %d 题"
         % (PER_ROUND * TARGET_ROUNDS, PER_ROUND, TARGET_ROUNDS, PER_ROUND * FLOOR_ROUNDS))
    emit()
    emit("== 现状：能支撑几次不重样 ==")
    for key, label in (("rounds_now", "现引擎·全对路径 min(standard, challenge//2)"),
                       ("rounds_weak", "现引擎·薄弱路径 min(standard, basic)"),
                       ("rounds_fresh", "改引擎后 floor(总题数/3)")):
        dist = collections.Counter(r[key] for r in rows)
        emit("%s → 轮次分布 %s" % (label, dict(sorted(dist.items()))))
        for k in (1, 3, 5, TARGET_ROUNDS):
            hit = sum(1 for r in rows if r[key] >= k)
            emit("    ≥%d 轮：%d 点（%.1f%%）" % (k, hit, 100.0 * hit / len(rows)))
    emit()
    emit("== 各口径的补题缺口 ==")
    for key, label in (("gap_total30", "总数补到 30（须先改引擎为没出过优先）"),
                       ("gap_tier30", "10 standard + 20 challenge（现引擎全对路径）"),
                       ("gap_tier40", "10 basic + 10 standard + 20 challenge（两条路径）"),
                       ("gap_floor15", "只补到 15 题下限（仅看总数，现引擎下不改善轮次）"),
                       ("gap_tier15", "阶段目标 5 轮：5 standard + 10 challenge = 15 题/点"),
                       ("gap_tier20", "阶段目标 5 轮两条路径：+5 basic = 20 题/点")):
        emit("%s → 缺 %d 道" % (label, sum(r[key] for r in rows)))
    emit()
    emit("== confirm 敏感度（两条路径 10 轮） ==")
    for cf in (2, 3, 5):
        need = 2 * TARGET_ROUNDS + (cf - 1) * TARGET_ROUNDS
        gap = sum(max(0, TARGET_ROUNDS - r["standard"])
                  + max(0, (cf - 1) * TARGET_ROUNDS - r["challenge"])
                  + max(0, TARGET_ROUNDS - r["basic"]) for r in rows)
        emit("confirm=%d → 每轮 1 standard + %d challenge + 1 basic，需 %d 题/点，缺 %d 道"
             % (cf, cf - 1, need, gap))
    emit()
    emit("== 学科 × 学段 ==")
    emit("学科 | 学段 | 点数 | 现有题 | 缺到30(总数) | 缺到30(分档) | 缺到40 | 缺到15(总数) | 缺到15(分档) | 缺到20(分档)")
    agg = collections.defaultdict(lambda: [0] * 8)
    for r in rows:
        a = agg[(r["subject"], r["stage"])]
        a[0] += 1
        for i, key in enumerate(("total", "gap_total30", "gap_tier30", "gap_tier40",
                                 "gap_floor15", "gap_tier15", "gap_tier20"), 1):
            a[i] += r[key]
    for k, a in sorted(agg.items()):
        emit(" | ".join([k[0], k[1]] + [str(x) for x in a]))
    emit("合计 | - | " + " | ".join(str(sum(a[i] for a in agg.values())) for i in range(8)))
    emit()
    emit("== 缺口最大的 20 册（按缺到 30） ==")
    books = collections.defaultdict(lambda: [0, 0, 0])
    for r in rows:
        b = books[(r["subject"], r["book"])]
        b[0] += 1
        b[1] += r["total"]
        b[2] += r["gap_total30"]
    emit("学科 | 册 | 点数 | 现有题 | 缺到30")
    for k, b in sorted(books.items(), key=lambda kv: -kv[1][2])[:20]:
        emit(" | ".join([k[0], k[1]] + [str(x) for x in b]))
    emit("册数 %d" % len(books))

    text = "\n".join(lines) + "\n"
    if args.out:
        path = os.path.join(ROOT, args.out) if not os.path.isabs(args.out) else args.out
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("written: %s" % path)
    else:
        print(text)
    if args.json:
        path = os.path.join(ROOT, args.json) if not os.path.isabs(args.json) else args.json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        print("written: %s" % path)


if __name__ == "__main__":
    main()