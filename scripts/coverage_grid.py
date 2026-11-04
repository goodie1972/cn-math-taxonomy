#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""省 × 年级 × 学科 覆盖网格。

格子取自 data/editions/province_map.json（32 省区 × 10 个年档 × 已建库 8 科 = 2560 格），
每格按四类判定：

  covered     该格点名的版本已在 registry 登记，且该版本在该年档确实有知识点
  no_point    版本已登记，但登记的主题清单里没有该年档的点（池子缺该册）
  unregistered 格值点名的版本在 registry 里找不到对应登记块
  blank       取证表该格没有给出任何版本（未核）

省年级用的常是裸名（「沪教版」），registry 里是带限定语的登记名（「沪教版（上海教育出版社）」），
故按「精确名，否则以裸名为前缀的唯一登记名」匹配；前缀命中多个时全部计入。

用法：
  python3 scripts/coverage_grid.py                      # 用当前产物
  python3 scripts/coverage_grid.py --registry X.json    # 换一份 registry 复测
"""
import argparse
import collections
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECTS = ["math", "english", "chinese", "physics", "science",
            "morality", "history", "geography"]
GRADES = [str(g) for g in range(1, 10)] + ["high"]
KEYS = ["covered", "no_point", "unregistered", "blank"]


def load(rel):
    return json.load(io.open(os.path.join(ROOT, rel), encoding="utf-8"))


def grade_of_topic(topic):
    g = topic.get("grade")
    if not isinstance(g, int):
        return None
    return "high" if g >= 10 else str(g)


def build_index(registry, topics):
    grade_of = {}
    for t in topics:
        g = grade_of_topic(t)
        if g:
            grade_of[t["id"]] = g
    index = collections.defaultdict(lambda: collections.defaultdict(set))
    for v in registry["versions"]:
        for subject, entry in (v.get("subjects") or {}).items():
            for tid in entry.get("topicIds") or []:
                g = grade_of.get(tid)
                if g:
                    index[v["label"]][subject].add(g)
    return index


def resolve(name, index, subject):
    """裸名 → 登记名。精确优先，其次唯一前缀。"""
    if name in index and subject in index[name]:
        return [name]
    return [label for label in sorted(index)
            if label.startswith(name) and subject in index[label]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="data/editions/registry.json")
    ap.add_argument("--out", default="_scratch/coverage_grid.txt")
    args = ap.parse_args()

    registry = load(args.registry) if os.path.isabs(args.registry) else load(args.registry)
    province_map = load("data/editions/province_map.json")["provinces"]
    topics = load("data/topics.json")
    topics = topics if isinstance(topics, list) else topics.get("topics")
    index = build_index(registry, topics)

    stats = collections.Counter()
    no_point = collections.Counter()
    unregistered = []
    for province, entry in sorted(province_map.items()):
        for grade in GRADES:
            cells = (entry.get("grades") or {}).get(grade) or {}
            for subject in SUBJECTS:
                named = cells.get(subject)
                if not named:
                    stats["blank"] += 1
                    continue
                labels = [l for name in named for l in resolve(name, index, subject)]
                if not labels:
                    stats["unregistered"] += 1
                    unregistered.append([province, grade, subject, named])
                elif any(grade in index[l][subject] for l in labels):
                    stats["covered"] += 1
                else:
                    stats["no_point"] += 1
                    no_point[(subject, grade)] += 1

    lines = ["registry=%s" % args.registry,
             "cells=%d（%d 省区 × %d 年档 × %d 科）" % (sum(stats.values()), len(province_map),
                                                        len(GRADES), len(SUBJECTS))]
    lines += ["%s = %d" % (k, stats[k]) for k in KEYS]
    lines.append("")
    lines.append("no_point 明细（学科 × 年档）：")
    for (subject, grade), n in sorted(no_point.items(), key=lambda x: (x[0][0], GRADES.index(x[0][1]))):
        lines.append("  %-10s %-5s %d" % (subject, grade, n))
    lines.append("")
    lines.append("unregistered 明细：")
    lines += ["  %s" % json.dumps(u, ensure_ascii=False) for u in unregistered]
    text = "\n".join(lines)
    io.open(os.path.join(ROOT, args.out), "w", encoding="utf-8").write(text + "\n")
    for k in KEYS:
        print("%s=%d" % (k, stats[k]))
    print("written %s" % args.out)


if __name__ == "__main__":
    main()
