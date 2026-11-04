#!/usr/bin/env python3
"""把小学语文草稿编译进 data/topics.json、dependencies.json、questions.json、课标文件。

可以重复运行：先去掉已有的 cnc_ 知识点和 ccs- 课标条目，再按脚本重新写入。
不改数学、英语、物理的知识点、先修、题目和课标。先修边只对语文边做传递约简。

用法：python3 scripts/zh_build.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zh_g1  # noqa: E402,F401
import zh_g2  # noqa: E402,F401
import zh_g3  # noqa: E402,F401
import zh_g4  # noqa: E402,F401
import zh_g5  # noqa: E402,F401
import zh_g6  # noqa: E402,F401
import zh_g7a  # noqa: E402,F401
import zh_g7b  # noqa: E402,F401
import zh_g8a  # noqa: E402,F401
import zh_g8b  # noqa: E402,F401
import zh_g9a  # noqa: E402,F401
import zh_edges  # noqa: E402,F401
import zh_j_edges  # noqa: E402,F401
from zh_lib import HARD, STANDARD_ROWS, TOPICS, chapter, check_question, materialise_questions, stage_label  # noqa: E402
from build_merge import merge_generated  # noqa: E402
from verify_questions import verify_all  # noqa: E402

ZH_CODES = {
    "PY": "拼音", "SZ": "识字写字", "CY": "词语", "JZ": "句子",
    "YD": "阅读理解", "GS": "古诗文积累", "XZ": "习作基础",
}
CHAPTER_RE = re.compile(r"^([一二三四五六七八九])年级([上下全])册 (第\d+单元|预备单元\d) (.+)$")
PRIMARY_VOLUMES = ["1上", "1下", "2上", "2下", "3上", "3下", "4上", "4下", "5上", "5下", "6上", "6下"]
JUNIOR_VOLUMES = ["7上", "7下", "8上", "8下", "9上", "9下"]
VOLUMES = PRIMARY_VOLUMES + JUNIOR_VOLUMES
# 每册知识点数上下界。小学十二册按已核对的统编目录填；初中六册的界（JUNIOR_BOUNDS）要等目录
# 双源核对后再填，留空就等于「这一册还没覆盖」，不许凭印象给一个数。
BOUNDS = {k: (30, 48) for k in PRIMARY_VOLUMES}
# 初中各册的点数由目录逐册推导（_scratch/_zhjr_expect.py → _scratch/zh_jr_plan.json）：
# 一课一点、课外古诗一首一点、写作/整本书/专题各一点，每册再加一点「字音字形」；
# 与前面册次重复的篇目（过渡期两册同收）不重复建点。上下界取同值，少一点或多一点都构建失败。
JUNIOR_BOUNDS = {
    "7上": (51, 51),
    "7下": (50, 50),
    "8上": (58, 58),
    "8下": (49, 49),
    "9上": (52, 52),
}
BOUNDS.update(JUNIOR_BOUNDS)


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


def dump(name, data):
    path = os.path.join(ROOT, "data", name)
    with open(path, "w", encoding="utf-8") as f:
        if name == "questions.json":
            # 题库由 scripts/qgen_merge.py 落盘，格式是 indent=1 且没有行尾换行；这里必须跟它一致，
            # 否则单跑一次语文构建就把 79 万行的题库整体重排。
            json.dump(data, f, ensure_ascii=False, indent=1)
            return
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_zh_topic_id(tid):
    return str(tid).startswith("cnc_")


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


def reduce_chinese(edges):
    """只删除语文知识点上的冗余边。hard 仅当另有全 hard 路径时删；soft 只要另有路径就删。"""
    adj = defaultdict(list)
    for e in edges:
        adj[e["topicId"]].append([e["prerequisiteId"], e["strength"]])
    kept = []
    dropped = 0
    for e in edges:
        if not is_zh_topic_id(e["topicId"]):
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
    for symbol, level, code, domain, section, text in STANDARD_ROWS:
        if domain != ZH_CODES[code]:
            raise SystemExit("课标领域不一致：%s" % symbol)
        key = (level, code)
        counters[key] = counters.get(key, 0) + 1
        sid = "ccs-2022:%s.%s.%02d" % (level, code, counters[key])
        id_of[symbol] = sid
        items.append({
            "id": sid,
            "domain": domain,
            "section": section,
            "clause": "(%d)" % counters[key],
            "text": text,
            "page_or_ref": "待核",
            "verbatim": False,
            "text_status": "公开转述，未与《义务教育语文课程标准（2022年版）》逐页核对",
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

    by_vol = Counter("%d%s" % (t["grade"], t["semester"]) for t in TOPICS)
    for k in VOLUMES:
        n = by_vol[k]
        bound = BOUNDS.get(k)
        if bound is None:
            # 初中册次的每册点数上下界要等目录双源核对后才能写；没有依据就先把这一册判为未覆盖。
            if n:
                print("%s 有 %d 个知识点，但每册点数边界未登记（先核对教材目录）" % (k, n), file=sys.stderr)
                return 1
            continue
        lo, hi = bound
        if n < lo or n > hi:
            print("%s 有 %d 个知识点，每册应为 %d–%d" % (k, n, lo, hi), file=sys.stderr)
            return 1
    if TOPICS[0]["key"] != "g1a_tian":
        print("第一个知识点必须是 g1a_tian", file=sys.stderr)
        return 1
    if not any("静夜思" in t["name"] for t in TOPICS):
        print("必须有一个名称里含「静夜思」的知识点", file=sys.stderr)
        return 1
    keys = [t["key"] for t in TOPICS]
    if len(set(keys)) != len(keys):
        print("知识点 key 重复", file=sys.stderr)
        return 1

    base_topics = [t for t in topics if not is_zh_topic_id(t.get("id"))]
    base_deps = [e for e in deps if not is_zh_topic_id(e.get("topicId")) and not is_zh_topic_id(e.get("prerequisiteId"))]
    base_questions = [q for q in questions if not is_zh_topic_id(q.get("topicId"))]
    base_items = [it for it in standards.get("items", []) if not str(it.get("id", "")).startswith("ccs-")]
    if any(is_zh_topic_id(t.get("id")) for t in base_topics):
        print("剥离语文知识点失败", file=sys.stderr)
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
    n_primary = 0
    n_junior = 0
    for i, spec in enumerate(TOPICS, start=1):
        # 小学段用 cnc_p、初中段用 cnc_j，各自连续编号。小学点必须全部排在初中点前面，
        # 这样 registry 里已登记的 cnc_p 编号不会因新增初中内容而整体后移。
        if spec["grade"] >= 7:
            n_junior += 1
            tid = "cnc_j%03d" % n_junior
        else:
            n_primary += 1
            if i != n_primary:
                print("小学知识点必须排在初中前面：%s 在第 %d 位" % (spec["key"], i), file=sys.stderr)
                return 1
            tid = "cnc_p%03d" % n_primary
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
            "subject": "chinese",
            "standards": [ref],
        }
        if spec["key"] == "g1a_tian":
            topic["root_reason"] = "一年级语文从识字「天地人」开始。按2024年修订的统编教材，识字排在汉语拼音前面，前面没有更早的小学语文知识点。"
        new_topics.append(topic)
        new_questions.extend(built)

    raw = []
    for i in range(1, len(TOPICS)):
        cur = TOPICS[i]["key"]
        prev = TOPICS[i - 1]["key"]
        if (cur, prev) in hard_pairs:
            continue
        reason = "按统编教材的常见教学顺序，先学「%s」，再学「%s」。" % (names[prev], names[cur])
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

    merged_deps, dropped = reduce_chinese(base_deps + new_edges)
    zh_edges = [e for e in merged_deps if is_zh_topic_id(e["topicId"])]
    if any(not is_zh_topic_id(e["prerequisiteId"]) for e in zh_edges):
        print("语文边连到了其他学科", file=sys.stderr)
        return 1
    if any(is_zh_topic_id(e["topicId"]) or is_zh_topic_id(e["prerequisiteId"]) for e in base_deps):
        print("剥离后的依赖里仍有语文边", file=sys.stderr)
        return 1
    covered = {e["topicId"] for e in zh_edges}
    missing = [t["id"] for t in new_topics if t["id"] != "cnc_p001" and t["id"] not in covered]
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

    kept_std = {k: v for k, v in standards.items() if k != "items" and k != "chinese"}
    standards_out = dict(standards)
    standards_out["items"] = list(base_items) + new_items
    standards_out["chinese"] = {
        "title": "义务教育语文课程标准（2022年版）",
        "issuer": "中华人民共和国教育部",
        "year": 2022,
        "stage": stage_label(),
        "note": "条目是对第一至第三学段学习要求的公开转述，不是逐页核对的原文。verbatim 为 false，page_or_ref 为「待核」。编号 ccs-2022 是本图谱编的，不是教育部原编号。一年级按2024年起修订的统编教材编排，二上、三上按2025秋修订目录编排，二下、三下按2026春修订目录编排，四上按2024修订统编目录逐课覆盖，四下按统编现行目录逐课覆盖，五上按2026秋统编目录逐课覆盖，五下按统编现行目录逐课覆盖，六上按2026秋统编目录逐课覆盖，六下按统编现行目录逐课覆盖，没有写入页码。",
    }
    for k, v in kept_std.items():
        standards_out[k] = v

    math_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cnm_")]
    en_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cne_")]
    phy_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cnp_")]

    n_hard = sum(1 for e in zh_edges if e["strength"] == "hard")
    n_soft = sum(1 for e in zh_edges if e["strength"] == "soft")
    by_dom = Counter(t["domain"] for t in new_topics)
    print("语文知识点 %d" % len(new_topics))
    for k in ["1上", "1下", "2上", "2下", "3上", "3下", "4上", "4下", "5上", "5下", "6上", "6下"]:
        print("  %s %d" % (k, by_vol[k]))
    for k, v in by_dom.most_common():
        print("  %s %d" % (k, v))
    print("语文边写入 %d（约简删去 %d）；hard %d，soft %d" % (len(zh_edges), dropped, n_hard, n_soft))
    # 四个数据文件都按 key 原地合并：生成器只覆盖自己产出的条目，其他学科的内容、补题阶段
    # 加进来的题目（带 source / accept / figure 等字段）原样保留、原位不动。重跑构建因此是
    # 幂等的，diff 里只剩真实变化。只有知识点被删掉时，它名下的题目才跟着删。
    dropped_topics = ({t["id"] for t in topics if is_zh_topic_id(t.get("id"))}
                      - {t["id"] for t in new_topics})
    topics_out, _ = merge_generated(topics, new_topics, lambda t: t["id"],
                                    lambda t: is_zh_topic_id(t.get("id")))
    gen_qids = {q["id"] for q in new_questions}
    questions_out, dropped_questions = merge_generated(
        questions, new_questions, lambda q: q["id"],
        lambda q: q["id"] in gen_qids or q.get("topicId") in dropped_topics)
    lost = [q["id"] for q in dropped_questions if q.get("topicId") not in dropped_topics]
    if lost:
        print("重写题库时丢了 %d 道已有题目：%s" % (len(lost), "、".join(lost[:10])), file=sys.stderr)
        return 1
    deps_out, _ = merge_generated(
        deps, zh_edges, lambda e: (e["topicId"], e["prerequisiteId"]),
        lambda e: is_zh_topic_id(e.get("topicId")) or is_zh_topic_id(e.get("prerequisiteId")))
    if {(e["topicId"], e["prerequisiteId"]) for e in deps_out} != \
       {(e["topicId"], e["prerequisiteId"]) for e in merged_deps}:
        print("原地合并后的先修图与约简结果不一致", file=sys.stderr)
        return 1
    items_out, _ = merge_generated(standards.get("items", []), new_items, lambda i: i["id"],
                                   lambda i: str(i.get("id", "")).startswith("ccs-"))
    standards_out["items"] = items_out
    n_extra = sum(1 for q in questions_out
                  if q["id"] not in gen_qids and is_zh_topic_id(q.get("topicId")))
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
    again_topics = [t for t in again_t if not is_zh_topic_id(t.get("id"))]
    again_deps = [e for e in again_d if not is_zh_topic_id(e.get("topicId")) and not is_zh_topic_id(e.get("prerequisiteId"))]
    again_qs = [q for q in again_q if not is_zh_topic_id(q.get("topicId"))]
    again_items = [it for it in again_s.get("items", []) if not str(it.get("id", "")).startswith("ccs-")]
    if again_topics != base_topics or again_deps != base_deps or again_qs != base_questions or again_items != base_items:
        print("数学、英语或物理数据在写回后发生了变化", file=sys.stderr)
        return 1
    if len(again_q) != len(questions_out):
        print("写回后的题目条数与合并结果不一致（%d ≠ %d）" % (len(again_q), len(questions_out)), file=sys.stderr)
        return 1
    if [(t["id"], t["name"]) for t in again_t if str(t["id"]).startswith("cnm_")] != math_before:
        print("数学知识点 id 或名称变了", file=sys.stderr)
        return 1
    if [(t["id"], t["name"]) for t in again_t if str(t["id"]).startswith("cne_")] != en_before:
        print("英语知识点 id 或名称变了", file=sys.stderr)
        return 1
    if [(t["id"], t["name"]) for t in again_t if str(t["id"]).startswith("cnp_")] != phy_before:
        print("物理知识点 id 或名称变了", file=sys.stderr)
        return 1
    for k, v in kept_std.items():
        if again_s.get(k) != v:
            print("原课标对象 %s 发生了变化" % k, file=sys.stderr)
            return 1
    if again_s.get("chinese", {}).get("title") != "义务教育语文课程标准（2022年版）":
        print("语文课标标题不正确", file=sys.stderr)
        return 1
    print("数学 %d、英语 %d、物理 %d 个知识点的 id 与名称未改" % (
        len(math_before), len(en_before), len(phy_before)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
