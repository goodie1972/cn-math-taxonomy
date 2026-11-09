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