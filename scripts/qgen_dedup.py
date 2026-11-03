"""同知识点重复题清理：内容全同（题干 + 选项文字 / 答案）的一组只留一条。

保留优先级：
1) 带 verify 的（能被机器核验）；
2) 该档位（difficulty）在删完后知识点里会缺失的——即组内唯一一条某档位的题；
3) id 序号最小的（保持 q1、q2 靠前，题目顺序稳定）。

删完后必须仍满足诊断口径：每个知识点 >=3 题、含 basic 与 standard、q1 之外还有一道 basic。
本脚本先用同一规则做一遍「预演」，任何知识点不达标就整体不写盘。
"""
import argparse
import collections
import io
import json
import os
import re

def _find_root(start):
    p = os.path.abspath(start)
    while p != os.path.dirname(p):
        if os.path.exists(os.path.join(p, "data", "questions.json")):
            return p
        p = os.path.dirname(p)
    raise SystemExit("找不到 data/questions.json")


ROOT = _find_root(os.path.dirname(__file__))
BANK = os.path.join(ROOT, "data", "questions.json")


def norm(s):
    return re.sub(r"[\s，。、；：「」『』（）()《》?!？！.,;:_＿_]", "", (s or "")).lower()


def content_key(q):
    ch = q.get("choices")
    if ch:
        return "%s|%s" % (norm(q["prompt"]), "|".join(sorted(norm(c.get("text")) for c in ch)))
    return "%s|%s" % (norm(q["prompt"]), norm(q.get("answer")))


def order(q):
    return int(re.search(r"_q(\d+)$", q["id"]).group(1))


def pick_keeper(group, outside_counts):
    """在一组内容全同的题里挑一条留下。

    outside_counts：本组之外（该知识点里不参与任何重复组的题）各档位的题数。
    优先留「档位唯一」的那条：组外缺这个档位、且组内这个档位只有它，删掉就丢档位。
    其次留带 verify 的，最后留序号最小的。
    """
    tier_in = collections.Counter(q.get("difficulty") for q in group)

    def key(q):
        tier = q.get("difficulty")
        sole_tier = 1 if (outside_counts.get(tier, 0) == 0 and tier_in[tier] == 1) else 0
        return (sole_tier, bool(q.get("verify")), -order(q))

    return max(group, key=key)


def check_bar(qs, tid, errors):
    tiers = collections.Counter(q.get("difficulty") for q in qs)
    if len(qs) < 3:
        errors.append("%s 删后只剩 %d 题" % (tid, len(qs)))
    if not tiers.get("basic"):
        errors.append("%s 删后没有 basic" % tid)
    if not tiers.get("standard"):
        errors.append("%s 删后没有 standard" % tid)
    extra_basic = [q for q in qs if q.get("difficulty") == "basic" and q["id"] != tid + "_q1"]
    if not extra_basic:
        errors.append("%s 删后 q1 之外没有第二道 basic" % tid)
    if not any(q["id"] == tid + "_q1" for q in qs):
        errors.append("%s 删掉了 q1" % tid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真正写盘（默认只做预演）")
    args = ap.parse_args()

    bank = json.load(io.open(BANK, encoding="utf-8"))
    by_topic = collections.defaultdict(list)
    for q in bank:
        by_topic[q["topicId"]].append(q)

    drop_ids = set()
    kept_info = []
    errors = []
    for tid, qs in by_topic.items():
        groups = collections.defaultdict(list)
        for q in qs:
            groups[content_key(q)].append(q)
        dup_groups = [g for g in groups.values() if len(g) > 1]
        if not dup_groups:
            continue
        # 组外各档位题数
        in_dup = {id(q) for g in dup_groups for q in g}
        outside = collections.Counter(q.get("difficulty") for q in qs if id(q) not in in_dup)
        for g in dup_groups:
            keep = pick_keeper(g, outside)
            for q in g:
                if q is not keep:
                    drop_ids.add(q["id"])
            kept_info.append((tid, keep["id"], [q["id"] for q in g if q is not keep]))
        remaining = [q for q in qs if q["id"] not in drop_ids]
        check_bar(remaining, tid, errors)

    lines = []
    lines.append("dup_groups=%d to_drop=%d topics_affected=%d" % (len(kept_info), len(drop_ids), len(set(t for t, _, _ in kept_info))))
    if errors:
        lines.append("BAR VIOLATIONS (%d):" % len(errors))
        lines += ["  " + e for e in errors]
    else:
        lines.append("bar check: OK（所有知识点删后仍达标）")
    lines.append("")
    for tid, keep, dropped in sorted(kept_info, key=lambda x: -len(x[2])):
        lines.append("%s 留 %s 删 %s" % (tid, keep, " ".join(dropped)))

    out = os.path.join(ROOT, "_scratch", "qgen", "_tmp", "dedup_report.txt")
    io.open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("to_drop=%d violations=%d" % (len(drop_ids), len(errors)))

    if args.write:
        if errors:
            raise SystemExit("仍有达标冲突，拒绝写盘")
        backup = os.path.join(ROOT, "_scratch", "questions.before_dedup.json")
        if not os.path.exists(backup):
            io.open(backup, "w", encoding="utf-8").write(json.dumps(bank, ensure_ascii=False, indent=1))
        new_bank = [q for q in bank if q["id"] not in drop_ids]
        io.open(BANK, "w", encoding="utf-8").write(json.dumps(new_bank, ensure_ascii=False, indent=1))
        print("bank %d -> %d" % (len(bank), len(new_bank)))


if __name__ == "__main__":
    main()
