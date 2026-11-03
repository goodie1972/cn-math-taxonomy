# -*- coding: utf-8 -*-
"""新补题目的独立盲解复核（沿用 docs/questions.md 里 A/B 轮的做法）。

    python3 scripts/qgen_blind.py prepare [批次文件.json ...]   # 只出题干和选项
    python3 scripts/qgen_blind.py compare [批次文件.json ...]   # 比对 _scratch/qgen/solved/ 里的答案

prepare 把题目去掉 answer / explanation / verify / accept，写到 _scratch/qgen/blind/，
解题者只能读 blind 文件；compare 再和题库（或批次文件）里的答案逐题对照。
不传批次文件名就处理 _scratch/qgen/accepted.json。
"""
import io
import json
import os
import re
import sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QG = os.path.join(ROOT, "_scratch", "qgen")
BLIND = os.path.join(QG, "blind")
SOLVED = os.path.join(QG, "solved")
PUNCT = re.compile(r"[\s，。、；：！？“”‘’（）,.;:!?'\"()\[\]{}\-—…]+")


def load(path):
    d = json.load(io.open(path, encoding="utf-8"))
    return d if isinstance(d, list) else d["questions"]


def num_list(s):
    out = []
    for p in re.split(r"[，,]", str(s or "")):
        p = p.replace(" ", "")
        if not p:
            continue
        out.append(Fraction(p) if "/" in p else Fraction(float(p)) if "." in p else Fraction(p))
    return out


def resolve(n):
    if os.path.isabs(n):
        return n
    for cand in (os.path.join(ROOT, n), os.path.join(QG, n), n):
        if os.path.exists(cand):
            return cand
    sys.exit("找不到批次文件：%s" % n)


def key(path):
    """blind / solved 文件按批次命名。单批次预检产物统一叫 accepted.json，
    这时用它的上级目录（check/<批次>）认名字；平铺在 qgen 根下时仍用 accepted。"""
    b = os.path.basename(path).replace(".json", "")
    parent = os.path.basename(os.path.dirname(path))
    if b == "accepted" and parent and parent != os.path.basename(QG):
        return parent
    return b


def prepare(names):
    if not os.path.isdir(BLIND):
        os.makedirs(BLIND)
    for n in names:
        src = resolve(n)
        blind = []
        for q in load(src):
            item = {"id": q["id"], "type": q["type"], "prompt": q["prompt"]}
            if q["type"] == "choice":
                item["choices"] = [{"key": c["key"], "text": c["text"]} for c in q.get("choices") or []]
            blind.append(item)
        dst = os.path.join(BLIND, key(src) + ".json")
        json.dump(blind, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("blind %s -> %d 题（不含答案）" % (dst, len(blind)))


def compare(names):
    bank = {q["id"]: q for q in load(os.path.join(ROOT, "data", "questions.json"))}
    problems, checked = [], 0
    for n in names:
        src = resolve(n)
        sol_path = os.path.join(SOLVED, key(src) + ".json")
        if not os.path.exists(sol_path):
            print("缺少独立解答：%s" % sol_path)
            continue
        # 碎片原文没有 id（合并时才分配），所以只认带 id 的源；纯靠 bank 的 id 也能比上
        mine = {q["id"]: q for q in load(src) if q.get("id")}
        for s in load(sol_path):
            qid = s.get("id")
            q = bank.get(qid) or mine.get(qid)
            if not q:
                problems.append({"id": qid, "why": "题库里找不到这个 id"})
                continue
            checked += 1
            ours_raw = str(q.get("answer") or "").strip()
            theirs_raw = str(s.get("answer") or "").strip()
            t = q["type"]
            if t == "choice":
                ok = theirs_raw.upper() == ours_raw.upper()
                if not ok and len(theirs_raw) == 1 and theirs_raw.upper() in "ABCD":
                    ok = False
            elif t == "numeric":
                try:
                    a, b = num_list(ours_raw), num_list(theirs_raw)
                    ordered = q.get("unordered") is not True
                    if len(a) == len(b):
                        pairs = zip(a, b) if ordered else zip(sorted(a), sorted(b))
                        ok = all(abs(x - y) < Fraction(1, 10 ** 9) for x, y in pairs)
                    else:
                        ok = False
                except Exception:
                    ok = False
            else:
                ok = PUNCT.sub("", ours_raw) == PUNCT.sub("", theirs_raw) or \
                    any(PUNCT.sub("", x) == PUNCT.sub("", theirs_raw) for x in q.get("accept") or [])
            if not ok:
                problems.append({"id": qid, "topicId": q.get("topicId"), "difficulty": q.get("difficulty"),
                                 "type": t, "prompt": q["prompt"], "bank": ours_raw, "solver": theirs_raw,
                                 "note": s.get("note") or ""})
    out = os.path.join(QG, "blind_mismatches.json")
    json.dump(problems, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("比对 %d 题，不一致 %d 处，明细见 %s" % (checked, len(problems), out))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    names = [a for a in sys.argv[2:] if not a.startswith("--")] or ["accepted.json"]
    if cmd == "prepare":
        prepare(names)
    elif cmd == "compare":
        compare(names)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
