#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本级达标核验：registry 每个版本块挂载的点，是否都在池子里、且题量/题型达标。

达标线同 tests/test_engine.js / scripts/bank_gap.py：
  正式点 ≥3 题、含 basic、含 standard、basic ≥2 道；物理 ≥10 题且三档齐全。
另查：挂载 id 在 topics.json 里不存在（dangling）、点在池子里是 external、
      同一点在某版本块里重复登记。
输出 _scratch/version_gate.txt（UTF-8）。bar_ok 可被其他脚本 import 复用。
"""
import collections
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bar_ok(tid, mine, subj):
    if not mine:
        return "零题"
    d = set(q.get("difficulty") for q in mine)
    if len(mine) < 3:
        return "不足3题"
    if "basic" not in d:
        return "缺basic"
    if "standard" not in d:
        return "缺standard"
    if sum(1 for q in mine if q.get("difficulty") == "basic") < 2:
        return "basic只1道"
    if subj == "physics":
        if len(mine) < 10:
            return "物理不足10题"
        if not {"basic", "standard", "challenge"} <= d:
            return "物理三档不齐"
    return ""


def main():
    registry = json.load(io.open(os.path.join(ROOT, "data/editions/registry.json"), encoding="utf-8"))
    topics = json.load(io.open(os.path.join(ROOT, "data/topics.json"), encoding="utf-8"))
    topics = topics if isinstance(topics, list) else topics["topics"]
    qs = json.load(io.open(os.path.join(ROOT, "data/questions.json"), encoding="utf-8"))
    qs = qs if isinstance(qs, list) else qs["questions"]
    tmap = {t["id"]: t for t in topics}
    bank = collections.defaultdict(list)
    for q in qs:
        bank[q.get("topicId")].append(q)

    out = io.open(os.path.join(ROOT, "_scratch/version_gate.txt"), "w", encoding="utf-8")
    w = out.write
    w("# 版本级达标核验\n\n")
    w("版本块总数：%d（%d 个版本）\n\n" % (
        sum(len(v.get("subjects") or {}) for v in registry["versions"]), len(registry["versions"])))
    w("%-30s %-10s %6s %6s %6s %6s %8s %8s\n" % ("版本", "学科", "挂载", "在池", "dangling",
                                                 "external", "未达标", "题数"))
    tot = collections.Counter()
    bad_rows = []
    for v in registry["versions"]:
        for subj, e in (v.get("subjects") or {}).items():
            ids = e.get("topicIds") or []
            dup = [i for i, c in collections.Counter(ids).items() if c > 1]
            in_pool = [i for i in ids if i in tmap]
            dangling = [i for i in ids if i not in tmap]
            ext = [i for i in in_pool if tmap[i].get("external")]
            below = []
            nq = 0
            for i in in_pool:
                mine = bank.get(i, [])
                nq += len(mine)
                why = bar_ok(i, mine, subj)
                if why:
                    below.append((i, len(mine), why))
            tot["块"] += 1
            tot["挂载"] += len(ids)
            tot["dangling"] += len(dangling)
            tot["external"] += len(ext)
            tot["未达标"] += len(below)
            tot["重复登记"] += len(dup)
            w("%-30s %-10s %6d %6d %6d %6d %8d %8d%s\n" % (
                v["label"][:28], subj, len(ids), len(in_pool), len(dangling), len(ext), len(below), nq,
                "  DUP=%s" % dup[:3] if dup else ""))
            if dangling or ext or below or dup:
                bad_rows.append((v["label"], subj, dangling[:5], ext[:5], below[:8], dup[:5]))
    w("\n合计：%d 块 / 挂载 %d 次 / dangling %d / external %d / 未达标 %d / 重复登记 %d\n" % (
        tot["块"], tot["挂载"], tot["dangling"], tot["external"], tot["未达标"], tot["重复登记"]))
    w("\n== 有问题的版本块明细 ==\n")
    if not bad_rows:
        w("（无）\n")
    for label, subj, dangling, ext, below, dup in bad_rows:
        w("%s / %s：dangling=%s external=%s dup=%s 未达标=%s\n" % (label, subj, dangling, ext, dup, below))
    out.close()
    print("blocks=%d dangling=%d ext=%d below=%d dup=%d" % (
        tot["块"], tot["dangling"], tot["external"], tot["未达标"], tot["重复登记"]))


if __name__ == "__main__":
    main()
