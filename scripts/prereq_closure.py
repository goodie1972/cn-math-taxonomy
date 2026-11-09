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