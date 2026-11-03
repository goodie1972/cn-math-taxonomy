# -*- coding: utf-8 -*-
"""把批量补题的碎片合并进总题库 data/questions.json。

题目只挂 topicId：一个总题库，教材版本只是切片，所以这里不写任何版本字段。
碎片放 _scratch/qgen/out/*.json，元素形如
  {topicId, difficulty, type, prompt, answer, explanation, verify?, choices?, accept?, unordered?}

合并前逐条卡格式（与 tests/test_engine.js、scripts/verify_questions.py 同一口径），
不合格的落到 _scratch/qgen/rejected.json 并写明原因，不进题库。
"""
import io
import json
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "_scratch", "qgen", "out")
REG_DIR = os.path.join(ROOT, "_scratch", "qgen")
QUESTIONS = os.path.join(ROOT, "data", "questions.json")
TOPICS = os.path.join(ROOT, "data", "topics.json")

DIFF = ("basic", "standard", "challenge", "advanced")
TYPE = ("numeric", "choice", "short", "self")
PUNCT = re.compile(r"[\s，。、；：！？“”‘’（）《》,.;:!?'\"()\[\]{}\-—…]+")


def norm(s):
    return PUNCT.sub("", str(s or "")).lower()


def load(p):
    d = json.load(io.open(p, encoding="utf-8"))
    return d if isinstance(d, list) else d["questions"] if isinstance(d, dict) and "questions" in d else list(d)


def main(dry_run=False, only=None):
    topics = load(TOPICS)
    formal = {t["id"]: t for t in topics if not t.get("external")}
    need_of = {}
    manifest = os.path.join(REG_DIR, "manifest.json")
    if os.path.exists(manifest):
        batch_files = [e["file"] for e in json.load(io.open(manifest, encoding="utf-8"))]
    else:  # 没有清单时按目录里的批次文件认，账本文件一律排除
        ledger = {"manifest.json", "rejected.json", "duplicates.json", "tier_warn.json", "accepted.json"}
        batch_files = [f for f in os.listdir(REG_DIR)
                       if f.endswith(".json") and f not in ledger and not f.startswith("_")]
    for fn in batch_files:
        p = os.path.join(REG_DIR, fn)
        if not os.path.exists(p):
            continue
        for x in json.load(io.open(p, encoding="utf-8")):
            need_of[x["topicId"]] = set(x.get("need") or [])

    qs = load(QUESTIONS)
    by_topic = collections.defaultdict(list)
    ids = set()
    for q in qs:
        by_topic[q["topicId"]].append(q)
        ids.add(q["id"])

    accepted, rejected, dup, tier_warn = [], [], [], []
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".json") and not f.startswith("_")) \
        if os.path.isdir(SRC) else []
    if only:
        files = [f for f in files if f in only]
    if not files:
        print("no fragments in _scratch/qgen/out")
        return
    for fn in files:
        for raw in json.load(io.open(os.path.join(SRC, fn), encoding="utf-8")):
            tid = raw.get("topicId")
            why = []
            if tid not in formal:
                rejected.append({"file": fn, "item": raw, "why": ["topicId 不是正式知识点"]})
                continue
            ex = by_topic.get(tid, [])
            if norm(raw.get("prompt")) in set(norm(q.get("prompt")) for q in ex):
                dup.append({"topicId": tid, "file": fn, "prompt": raw.get("prompt")})
                continue
            if raw.get("difficulty") not in DIFF:
                why.append("difficulty 非法")
            if raw.get("type") not in TYPE:
                why.append("type 非法")
            if not str(raw.get("prompt") or "").strip():
                why.append("prompt 为空")
            if not str(raw.get("answer") or "").strip():
                why.append("answer 为空")
            if not str(raw.get("explanation") or "").strip():
                why.append("explanation 为空")
            t = raw.get("type")
            if t == "choice":
                ch = raw.get("choices") or []
                if not isinstance(ch, list) or not (3 <= len(ch) <= 4):
                    why.append("choice 需要 3-4 个选项")
                else:
                    keys = [c.get("key") for c in ch]
                    if keys != ["A", "B", "C"][:len(ch)] and keys != list("ABCD")[:len(ch)]:
                        why.append("选项 key 必须从 A 起依次")
                    if len(set(norm(c.get("text")) for c in ch)) != len(ch):
                        why.append("选项文字重复")
                    if str(raw.get("answer")).strip() not in keys:
                        why.append("answer 不在选项 key 里")
            if t == "numeric":
                if not re.match(r"^-?\d+(\.\d+)?(/-?\d+)?$", str(raw.get("answer")).strip().split("，")[0].strip()):
                    why.append("numeric 答案不是数/分数")
            if why:
                rejected.append({"file": fn, "item": raw, "why": why})
                continue
            nd = need_of.get(tid)
            if nd and raw.get("difficulty") not in nd:
                # 档位对不上只记账，不写进题库：validate.py 不接受 note 这类额外字段。
                tier_warn.append({"topicId": tid, "file": fn, "difficulty": raw.get("difficulty"),
                                  "need": sorted(nd)})
            n = max([int(m.group(1)) for q in ex for m in [re.search(r"_q(\d+)$", q["id"])] if m] + [0]) + 1
            qid = "%s_q%d" % (tid, n)
            while qid in ids:
                n += 1
                qid = "%s_q%d" % (tid, n)
            item = {"topicId": tid, "difficulty": raw["difficulty"], "type": raw["type"],
                    "prompt": raw["prompt"].strip(), "answer": str(raw["answer"]).strip(),
                    "explanation": raw["explanation"].strip(), "id": qid}
            for k in ("choices", "accept", "verify", "unordered", "figure", "hideChoiceText"):
                if raw.get(k) is not None:
                    item[k] = raw[k]
            item["source"] = raw.get("source") or "llm"
            accepted.append(item)
            ids.add(qid)
            by_topic[tid].append(item)

    before = len(qs)
    if dry_run:
        print("DRY RUN：不写 data/questions.json")
    else:
        json.dump(qs + accepted, io.open(QUESTIONS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    # 单批次预检把账本写到各自目录，多个出题任务并行时不会互相覆盖
    led = REG_DIR
    if dry_run and only and len(only) == 1:
        led = os.path.join(REG_DIR, "check", only[0].replace(".json", ""))
    if not os.path.isdir(led):
        os.makedirs(led)
    for name, data in (("rejected", rejected), ("duplicates", dup), ("tier_warn", tier_warn),
                       ("accepted", accepted)):
        json.dump(data, io.open(os.path.join(led, name + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("账本：%s" % led)
    print("bank %d -> %d (+%d) rejected=%d dup=%d tier_warn=%d" % (
        before, before + len(accepted), len(accepted), len(rejected), len(dup), len(tier_warn)))
    per = collections.Counter(a["difficulty"] for a in accepted)
    print("by difficulty: " + ", ".join("%s %d" % (k, per[k]) for k in DIFF if per[k]))


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    only = [os.path.basename(a) for a in sys.argv[1:] if not a.startswith("--")] or None
    main(dry_run=dry, only=only)
