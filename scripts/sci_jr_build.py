#!/usr/bin/env python3
"""把初中科学（沪六五四制 + 浙 7~9）草稿编译进 data/topics.json、dependencies.json、questions.json、课标文件。

可以重复运行：先去掉已有的 cns_j 知识点和 css- 课标条目，再按脚本重新写入。
与 scripts/sci_build.py（小学科学，cns_p）互不覆盖：本脚本只碰 cns_j，小学科学 cns_p 原样保留。

用法：python3 scripts/sci_jr_build.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sci_jr_g6  # noqa: E402,F401
import sci_jr_g7  # noqa: E402,F401
import sci_jr_g8  # noqa: E402,F401
import sci_jr_g9  # noqa: E402,F401
import sci_jr_edges  # noqa: E402,F401
from sci_jr_lib import HARD, CODE_OF, STANDARD_ROWS, TOPICS, chapter, check_question, materialise_questions, stage_label  # noqa: E402
from build_merge import merge_generated  # noqa: E402
from verify_questions import verify_all  # noqa: E402

CHAPTER_RE = re.compile(r"^([一二三四五六七八九])年级([上下全])册 (第\d+章|第\d+单元|预备单元\d) (.+)$")
VOLUMES = ["6上", "6下", "7上", "7下", "8上", "8下", "9上", "9下"]
# 每册点数上下界（按 _scratch/junior_toc/sci_junior.json 的双源目录逐节登记）。
BOUNDS = {
    "6上": (13, 13), "6下": (12, 12),
    "7上": (17, 17), "7下": (18, 18),
    "8上": (21, 21), "8下": (20, 20),
    "9上": (17, 17), "9下": (20, 20),
}


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


def dump(name, data):
    path = os.path.join(ROOT, "data", name)
    with open(path, "w", encoding="utf-8") as f:
        if name == "questions.json":
            json.dump(data, f, ensure_ascii=False, indent=1)
            return
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_jr_id(tid):
    return str(tid).startswith("cns_j")


def reaches(adj, src, dst, hard_only):
    seen = {src}
    stack = [src]
    while stack:
        node = stack.pop()
        for pre, strength in adj.get(node, []):
            if hard_only and strength != "hard":
                continue
            if pre == dst:
                return True
            if pre not in seen:
                seen.add(pre)
                stack.append(pre)
    return False


def reduce_jr(edges):
    """只删除初中科学知识点上的冗余边。hard 仅当另有全 hard 路径时删；soft 只要另有路径就删。"""
    adj = defaultdict(list)
    for e in edges:
        adj[e["topicId"]].append([e["prerequisiteId"], e["strength"]])
    kept = []
    dropped = 0
    for e in edges:
        if not is_jr_id(e["topicId"]):
            kept.append(e)
            continue
        lst = adj[e["topicId"]]
        idx = next(i for i, (p, s) in enumerate(lst)
                   if p == e["prerequisiteId"] and s == e["strength"])
        lst.pop(idx)
        if reaches(adj, e["topicId"], e["prerequisiteId"], e["strength"] == "hard"):
            dropped += 1
            continue
        lst.append([e["prerequisiteId"], e["strength"]])
        kept.append(e)
    return kept, dropped


def build_standards():
    counters = {}
    id_of = {}
    items = []
    for symbol, level, code, section, text in STANDARD_ROWS:
        domain = CODE_OF[code]
        key = (level, code)
        counters[key] = counters.get(key, 0) + 1
        sid = "css-2022:%s.%s.%02d" % (level, code, counters[key])
        id_of[symbol] = sid
        items.append({
            "id": sid,
            "domain": domain,
            "section": section,
            "clause": "(%d)" % counters[key],
            "text": text,
            "page_or_ref": "待核",
            "verbatim": False,
            "text_status": "公开转述，未与《义务教育科学课程标准（2022年版）》逐页核对",
        })
    return id_of, items


def build_question(tid, index, made, slot):
    qid = "%s_q%d" % (tid, index)
    texts = list(made["w"])
    texts.insert(slot % 4, made["a"])
    keys = list("ABCD")
    pos = texts.index(made["a"])
    return {
        "id": qid,
        "topicId": tid,
        "difficulty": made["d"],
        "type": "choice",
        "prompt": made["p"],
        "choices": [{"key": keys[i], "text": texts[i]} for i in range(4)],
        "answer": keys[pos],
        "explanation": made["e"],
        "verify": json.dumps(made["a"], ensure_ascii=False),
    }, made["a"]


def rank_of(spec):
    return spec["grade"] * 2 + (1 if spec["semester"] == "下" else 0)


def main():
    topics = load("topics.json")
    deps = load("dependencies.json")
    questions = load("questions.json")
    standards = load("cn-curriculum-standards.json")

    order = {t["key"]: i for i, t in enumerate(TOPICS)}
    TOPICS.sort(key=lambda t: (rank_of(t), t["unit"], order[t["key"]]))
    pre = defaultdict(set)
    for src, dst, _r in HARD:
        pre[src].add(dst)
    placed, out = set(), []
    pending = list(TOPICS)
    while pending:
        for j, t in enumerate(pending):
            if all(d in placed or d not in order for d in pre[t["key"]] if d in {x["key"] for x in pending}):
                out.append(pending.pop(j))
                placed.add(t["key"])
                break
        else:
            print("硬先修成环", file=sys.stderr)
            return 1
    TOPICS[:] = out
    by_vol = Counter("%d%s" % (t["grade"], t["semester"]) for t in TOPICS)
    for k in VOLUMES:
        n = by_vol[k]
        lo, hi = BOUNDS[k]
        if n < lo or n > hi:
            print("%s 有 %d 个知识点，每册应为 %d–%d" % (k, n, lo, hi), file=sys.stderr)
            return 1
    keys = [t["key"] for t in TOPICS]
    if len(set(keys)) != len(keys):
        print("知识点 key 重复", file=sys.stderr)
        return 1

    base_topics = [t for t in topics if not is_jr_id(t.get("id"))]
    base_deps = [e for e in deps if not is_jr_id(e.get("topicId")) and not is_jr_id(e.get("prerequisiteId"))]
    base_questions = [q for q in questions if not is_jr_id(q.get("topicId"))]
    base_items = [it for it in standards.get("items", [])
                  if not str(it.get("id", "")).startswith("css-2022:4.")]
    if any(is_jr_id(t.get("id")) for t in base_topics):
        print("剥离初中科学知识点失败", file=sys.stderr)
        return 1

    id_of_std, new_items = build_standards()
    used_std = {t["std"] for t in TOPICS}
    missing_std = [row[0] for row in STANDARD_ROWS if row[0] not in used_std]
    if missing_std:
        print("课标条目没有被任何知识点引用：%s" % "、".join(missing_std), file=sys.stderr)
        return 1
    index = {t["key"]: i for i, t in enumerate(TOPICS)}
    by_key = {t["key"]: t for t in TOPICS}
    names = {t["key"]: t["name"] for t in TOPICS}
    hard_pairs = {}
    for src, dst, reason in HARD:
        if src not in index or dst not in index:
            print("硬先修指向未登记的知识点：%s → %s" % (src, dst), file=sys.stderr)
            return 1
        if index[dst] >= index[src]:
            print("硬先修不早于后续：%s 依赖 %s" % (src, dst), file=sys.stderr)
            return 1
        if rank_of(by_key[dst]) > rank_of(by_key[src]):
            print("硬先修册次更晚：%s 依赖 %s" % (src, dst), file=sys.stderr)
            return 1
        if (src, dst) in hard_pairs:
            print("重复硬边 %s → %s" % (src, dst), file=sys.stderr)
            return 1
        hard_pairs[(src, dst)] = reason

    new_topics = []
    new_questions = []
    id_of = {}
    for i, spec in enumerate(TOPICS, start=1):
        tid = "cns_j%03d" % i
        id_of[spec["key"]] = tid
        if spec["std"] not in id_of_std:
            print("%s 课标 %s 不存在" % (spec["key"], spec["std"]), file=sys.stderr)
            return 1
        made = materialise_questions(spec)
        for q in made:
            check_question(spec["key"], q)
        built = []
        diag_answer = None
        for n, item in enumerate(made, start=1):
            q, shown = build_question(tid, n, item, slot=i + n)
            built.append(q)
            if n == 1:
                diag_answer = shown
        ch = chapter(spec["grade"], spec["semester"], spec["unit"])
        if not CHAPTER_RE.match(ch):
            print("%s 章节格式无法按册浏览：%s" % (spec["key"], ch), file=sys.stderr)
            return 1
        ref = {"id": id_of_std[spec["std"]], "confidence": spec["conf"]}
        if spec.get("note"):
            ref["note"] = spec["note"]
        topic = {
            "id": tid,
            "name": spec["name"],
            "domain": spec["domain"],
            "grade": spec["grade"],
            "semester": spec["semester"],
            "chapter": ch,
            "type": spec["type"],
            "description": spec["description"],
            "mastery_criteria": spec["mastery_criteria"],
            "diagnostic_question": {"question": built[0]["prompt"], "answer": diag_answer},
            "external": False,
            "subject": "science",
            "standards": [ref],
        }
        if i == 1:
            topic["root_reason"] = "初中科学从沪六上册认识物质的性质开始，前面没有更早的初中科学知识点。"
        new_topics.append(topic)
        new_questions.extend(built)

    raw = []
    for i in range(1, len(TOPICS)):
        cur = TOPICS[i]["key"]
        prev = TOPICS[i - 1]["key"]
        if (cur, prev) in hard_pairs:
            continue
        reason = "按初中科学的常见教学顺序，先学「%s」，再学「%s」。" % (names[prev], names[cur])
        raw.append((cur, prev, "soft", reason))
    for src, dst, reason in HARD:
        raw.append((src, dst, "hard", reason))

    new_edges = []
    seen = set()
    for src, dst, strength, reason in raw:
        if index[dst] >= index[src]:
            print("先修不早于后续：%s 依赖 %s" % (src, dst), file=sys.stderr)
            return 1
        if rank_of(by_key[dst]) > rank_of(by_key[src]):
            print("先修年级更晚：%s 依赖 %s" % (src, dst), file=sys.stderr)
            return 1
        key = (id_of[src], id_of[dst])
        if key in seen:
            print("重复边 %s → %s" % key, file=sys.stderr)
            return 1
        seen.add(key)
        new_edges.append({
            "topicId": id_of[src],
            "prerequisiteId": id_of[dst],
            "strength": strength,
            "reason": reason,
        })

    merged_deps, dropped = reduce_jr(base_deps + new_edges)
    jr_edges = [e for e in merged_deps if is_jr_id(e["topicId"])]
    if any(not is_jr_id(e["prerequisiteId"]) for e in jr_edges):
        print("初中科学边连到了其他学科", file=sys.stderr)
        return 1
    if any(is_jr_id(e["topicId"]) or is_jr_id(e["prerequisiteId"]) for e in base_deps):
        print("剥离后的依赖里仍有初中科学边", file=sys.stderr)
        return 1
    covered = {e["topicId"] for e in jr_edges}
    missing = [t["id"] for t in new_topics if t["id"] != "cns_j001" and t["id"] not in covered]
    if missing:
        print("约简后仍无先修：%s" % "、".join(missing), file=sys.stderr)
        return 1

    checked = verify_all(new_questions)
    if checked["mismatch"] or checked["unverifiable"]:
        for m in checked["mismatch"][:40]:
            print("题目核对失败 %s：%s" % (m["id"], m.get("detail")), file=sys.stderr)
        print("题目核对未通过：mismatch %d，unverifiable %d" % (
            len(checked["mismatch"]), len(checked["unverifiable"])), file=sys.stderr)
        return 1

    kept_std = {k: v for k, v in standards.items() if k != "items" and k != "science"}
    standards_out = dict(standards)
    standards_out["items"] = list(base_items) + new_items
    standards_out["science"] = {
        "title": "义务教育科学课程标准（2022年版）",
        "issuer": "中华人民共和国教育部",
        "year": 2022,
        "stage": "第1至第4学段（1–2、3–4、5–6、7–9 年级）",
        "note": "条目是对科学课标第四学段（7~9 年级）内容要求的公开转述，不是逐页核对的原文。verbatim 为 false，page_or_ref 为「待核」。编号 css-2022 是本图谱编的，不是教育部原编号。初中科学池以浙教版（2024 修订版）7~9 年级为主体，另含沪科技版（五四制）六年级（上海 2026 秋起七年级不再开设科学，六年级属初中段）；华东师大版（宁波已停用）、武汉版（现况未核到）暂不建池。",
    }
    for k, v in kept_std.items():
        standards_out[k] = v

    n_hard = sum(1 for e in jr_edges if e["strength"] == "hard")
    n_soft = sum(1 for e in jr_edges if e["strength"] == "soft")
    by_dom = Counter(t["domain"] for t in new_topics)
    print("初中科学知识点 %d" % len(new_topics))
    for k in VOLUMES:
        print("  %s %d" % (k, by_vol[k]))
    for k, v in by_dom.most_common():
        print("  %s %d" % (k, v))
    print("初中科学边写入 %d（约简删去 %d）；hard %d，soft %d" % (len(jr_edges), dropped, n_hard, n_soft))

    dropped_topics = ({t["id"] for t in topics if is_jr_id(t.get("id"))}
                      - {t["id"] for t in new_topics})
    topics_out, _ = merge_generated(topics, new_topics, lambda t: t["id"],
                                    lambda t: is_jr_id(t.get("id")))
    gen_qids = {q["id"] for q in new_questions}
    questions_out, dropped_questions = merge_generated(
        questions, new_questions, lambda q: q["id"],
        lambda q: q["id"] in gen_qids or q.get("topicId") in dropped_topics)
    lost = [q["id"] for q in dropped_questions if q.get("topicId") not in dropped_topics]
    if lost:
        print("重写题库时丢了 %d 道已有题目：%s" % (len(lost), "、".join(lost[:10])), file=sys.stderr)
        return 1
    deps_out, _ = merge_generated(
        deps, jr_edges, lambda e: (e["topicId"], e["prerequisiteId"]),
        lambda e: is_jr_id(e.get("topicId")) or is_jr_id(e.get("prerequisiteId")))
    if {(e["topicId"], e["prerequisiteId"]) for e in deps_out} != \
       {(e["topicId"], e["prerequisiteId"]) for e in merged_deps}:
        print("原地合并后的先修图与约简结果不一致", file=sys.stderr)
        return 1
    items_out, _ = merge_generated(standards.get("items", []), new_items, lambda i: i["id"],
                                   lambda i: str(i.get("id", "")).startswith("css-2022:4."))
    standards_out["items"] = items_out
    n_extra = sum(1 for q in questions_out
                  if q["id"] not in gen_qids and is_jr_id(q.get("topicId")))
    print("题目 %d（生成器写 %d，保留本科补题 %d）" % (len(questions_out), len(new_questions), n_extra))
    print("课标条目 %d" % len(items_out))

    dump("topics.json", topics_out)
    dump("dependencies.json", deps_out)
    dump("questions.json", questions_out)
    dump("cn-curriculum-standards.json", standards_out)

    again_t = load("topics.json")
    again_d = load("dependencies.json")
    again_q = load("questions.json")
    again_s = load("cn-curriculum-standards.json")
    again_topics = [t for t in again_t if not is_jr_id(t.get("id"))]
    again_deps = [e for e in again_d if not is_jr_id(e.get("topicId")) and not is_jr_id(e.get("prerequisiteId"))]
    again_qs = [q for q in again_q if not is_jr_id(q.get("topicId"))]
    again_items = [it for it in again_s.get("items", []) if not str(it.get("id", "")).startswith("css-")]
    if again_topics != base_topics or again_deps != base_deps or again_qs != base_questions or again_items != base_items:
        print("其他学科数据在写回后发生了变化", file=sys.stderr)
        return 1
    if len(again_q) != len(questions_out):
        print("写回后的题目条数与合并结果不一致（%d ≠ %d）" % (len(again_q), len(questions_out)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
