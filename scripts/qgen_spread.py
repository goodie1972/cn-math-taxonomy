# -*- coding: utf-8 -*-
"""打散选择题的正确答案位置（防止「全选 A」猜中）。

两种用法：
  python3 scripts/qgen_spread.py --file _scratch/qgen/out/xxx.json   # 改碎片（未入库的用这个）
  python3 scripts/qgen_spread.py --ids-from _scratch/qgen/blind/xxx.json  # 按 blind 里的 id 改总库

规则：按题目顺序遍历，把占比超过均值 1.3 倍的选项位置挪到当前最少的字母上；
只动 choices 顺序、answer 字母，`verify` 是选项文字字面量所以不受影响。
解析里点了选项字母的题（改了会解释不通）一律跳过并列出，交回人工重写解析。
"""
import argparse
import collections
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS = os.path.join(ROOT, "data", "questions.json")
KEYS = "ABCD"
# 独立的 A–D 字母（前后不接其它拉丁字母），选项指代就是这个写法
LET_RE = re.compile(r"(?<![A-Za-z])([ABCD])(?![A-Za-z])")


def load(p):
    d = json.load(io.open(p, encoding="utf-8"))
    return d if isinstance(d, list) else d["questions"]


def mentioned_letters(q):
    """解析里以「独立字母」形式出现的选项指代。"""
    return set(LET_RE.findall(str(q.get("explanation") or "")))


def letter_of(q):
    return str(q.get("answer") or "").strip().upper()


def remap_letters(text, mapping):
    """把解析里的选项字母按 mapping 换掉；用占位符避免 A→B、B→A 互相吃掉。"""
    out = LET_RE.sub(lambda m: "\x00%s\x00" % mapping.get(m.group(1), m.group(1)), text)
    return out.replace("\x00", "")


def spread(items, verbose=True):
    """就地改 items（含 choices/answer 的题目 dict）。返回 (改动数, 跳过列表)。

    解析常写「A 正确，B 错在…」，所以换位置时要把解析里的字母一起映射过去；
    题干里也出现 A–D 的（几何「△ABC」这类）分不清是选项还是点名，一律不动。
    """
    ch = [q for q in items if q.get("type") == "choice" and q.get("choices")]
    if not ch:
        return 0, []
    cnt = collections.Counter(letter_of(q) for q in ch)
    n = len(ch)
    target = n / 4.0
    moved, skipped = 0, []
    for q in ch:
        old = letter_of(q)
        if cnt[old] <= target * 1.3:
            continue
        k = len(q["choices"])
        if LET_RE.search(str(q.get("prompt") or "")) or k > 4 or old not in KEYS[:k]:
            skipped.append(q.get("id") or q.get("topicId"))
            continue
        new = min(KEYS[:k], key=lambda x: (cnt.get(x, 0), KEYS.index(x)))
        if new == old:
            continue
        ordered = sorted(q["choices"], key=lambda c: c["key"])
        texts = [c["text"] for c in ordered]
        right = texts[KEYS.index(old)]
        distract = [t for t in texts if t != right]
        if len(distract) != k - 1:  # 选项文字有重复，位置对不上，不动
            skipped.append(q.get("id") or q.get("topicId"))
            continue
        # 正确项放到 new，其余按原顺序填空位
        slots = [None] * k
        slots[KEYS.index(new)] = right
        pool = [i for i in range(k) if slots[i] is None]
        for i, t in zip(pool, distract):
            slots[i] = t
        mapping = {KEYS[j]: KEYS[slots.index(texts[j])] for j in range(k)}
        q["choices"] = [{"key": KEYS[i], "text": slots[i]} for i in range(k)]
        q["answer"] = new
        if mentioned_letters(q):
            q["explanation"] = remap_letters(str(q["explanation"]), mapping)
        cnt[old] -= 1
        cnt[new] = cnt.get(new, 0) + 1
        moved += 1
    if verbose:
        print("choice=%d moved=%d skipped=%d dist=%s" % (
            n, moved, len(skipped), dict(sorted(cnt.items()))))
        if skipped:
            print("skipped(解析点了字母): " + " ".join(str(s) for s in skipped))
    return moved, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--ids-from")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.file:
        items = load(a.file)
        moved, _ = spread(items)
        if moved and not a.dry_run:
            json.dump(items, io.open(a.file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("written " + a.file)
    elif a.ids_from:
        ids = [x["id"] for x in load(a.ids_from)]
        bank = load(QUESTIONS)
        idx = {q["id"]: q for q in bank if q["id"] in set(ids)}
        moved, _ = spread(list(idx.values()))
        if moved and not a.dry_run:
            json.dump(bank, io.open(QUESTIONS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("written %s (+%d moved)" % (QUESTIONS, moved))
    else:
        ap.error("要 --file 或 --ids-from")


if __name__ == "__main__":
    main()
