#!/usr/bin/env python3
"""把小学与初中道德与法治草稿编译进 data/topics.json、dependencies.json、questions.json、课标文件。

可以重复运行：先去掉已有的 cnd_ 知识点和 cds- 课标条目，再按脚本重新写入。
不改数学、英语、物理、语文、科学的知识点、先修、题目和课标。先修边只对道德与法治边做传递约简。

小学按 2022 年版课标第一至第三学段、初中按第四学段；初中目录依据 _scratch/junior_toc/mor_junior.json
（六三制统编版，逐册双源以上核对）。

用法：python3 scripts/mor_build.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mor_g1  # noqa: E402,F401
import mor_g2  # noqa: E402,F401
import mor_g3  # noqa: E402,F401
import mor_g4  # noqa: E402,F401
import mor_g5  # noqa: E402,F401
import mor_g6  # noqa: E402,F401
import mor_g7  # noqa: E402,F401
import mor_g8  # noqa: E402,F401
import mor_g9  # noqa: E402,F401
import mor_edges  # noqa: E402,F401
import mor_j_edges  # noqa: E402,F401
from mor_lib import HARD, CODE_OF, STANDARD_ROWS, TOPICS, chapter, check_question, materialise_questions, stage_label  # noqa: E402
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
# 每册知识点数上下界（每册约 10–16 课）。初中的界（JUNIOR_BOUNDS）要等目录双源核对后再填，
# 留空就等于「这一册还没覆盖」，不许凭印象给一个数。
BOUNDS = {k: (10, 20) for k in PRIMARY_VOLUMES}
# 初中按「一课一点」建点，所以上下界直接取双源核对后的各册课数：多一课少一课都说明与目录不符。
JUNIOR_BOUNDS = {"7上": (13, 13), "7下": (11, 11), "8上": (12, 12),
                 "8下": (14, 14), "9上": (10, 10), "9下": (7, 7)}
BOUNDS.update(JUNIOR_BOUNDS)


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


def dump(name, data):
    path = os.path.join(ROOT, "data", name)
    with open(path, "w", encoding="utf-8") as f:
        if name == "questions.json":
            # 题库由 scripts/qgen_merge.py 落盘，格式是 indent=1 且没有行尾换行；这里必须跟它一致，
            # 否则单跑一次道法构建就把 79 万行的题库整体重排。
            json.dump(data, f, ensure_ascii=False, indent=1)
            return
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_mor_topic_id(tid):
    return str(tid).startswith("cnd_")


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


def reduce_morality(edges):
    """只删除道德与法治知识点上的冗余边。hard 仅当另有全 hard 路径时删；soft 只要另有路径就删。"""
    adj = defaultdict(list)
    for e in edges:
        adj[e["topicId"]].append([e["prerequisiteId"], e["strength"]])
    kept = []
    dropped = 0
    for e in edges:
        if not is_mor_topic_id(e["topicId"]):
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
        sid = "cds-2022:%s.%s.%02d" % (level, code, counters[key])
        id_of[symbol] = sid
        items.append({
            "id": sid,
            "domain": domain,
            "section": section,
            "clause": "(%d)" % counters[key],
            "text": text,
            "page_or_ref": "待核",
            "verbatim": False,
            "text_status": "公开转述，未与《义务教育道德与法治课程标准（2022年版）》逐页核对",
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
    # 同一单元内，让硬先修排在后续前面（稳定拓扑排序）。
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
    keys = [t["key"] for t in TOPICS]
    if len(set(keys)) != len(keys):
        print("知识点 key 重复", file=sys.stderr)
        return 1

    base_topics = [t for t in topics if not is_mor_topic_id(t.get("id"))]
    base_deps = [e for e in deps if not is_mor_topic_id(e.get("topicId")) and not is_mor_topic_id(e.get("prerequisiteId"))]
    base_questions = [q for q in questions if not is_mor_topic_id(q.get("topicId"))]
    base_items = [it for it in standards.get("items", []) if not str(it.get("id", "")).startswith("cds-")]
    if any(is_mor_topic_id(t.get("id")) for t in base_topics):
        print("剥离道德与法治知识点失败", file=sys.stderr)
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
        # 小学段 cnd_p、初中段 cnd_j 各自连续编号：新增初中内容不会让已登记的 cnd_p 编号后移。
        if spec["grade"] >= 7:
            n_junior += 1
            tid = "cnd_j%03d" % n_junior
        else:
            n_primary += 1
            tid = "cnd_p%03d" % n_primary
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
            "subject": "morality",
            "standards": [ref],
        }
        if i == 1:
            topic["root_reason"] = "一年级道德与法治从认识小学生活开始，前面没有更早的小学道德与法治知识点。"
        new_topics.append(topic)
        new_questions.extend(built)

    raw = []
    for i in range(1, len(TOPICS)):
        cur = TOPICS[i]["key"]
        prev = TOPICS[i - 1]["key"]
        if (cur, prev) in hard_pairs:
            continue
        reason = "按统编版道德与法治的常见教学顺序，先学「%s」，再学「%s」。" % (names[prev], names[cur])
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

    merged_deps, dropped = reduce_morality(base_deps + new_edges)
    zh_edges = [e for e in merged_deps if is_mor_topic_id(e["topicId"])]
    if any(not is_mor_topic_id(e["prerequisiteId"]) for e in zh_edges):
        print("道德与法治边连到了其他学科", file=sys.stderr)
        return 1
    if any(is_mor_topic_id(e["topicId"]) or is_mor_topic_id(e["prerequisiteId"]) for e in base_deps):
        print("剥离后的依赖里仍有道德与法治边", file=sys.stderr)
        return 1
    covered = {e["topicId"] for e in zh_edges}
    missing = [t["id"] for t in new_topics if t["id"] != "cnd_p001" and t["id"] not in covered]
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

    kept_std = {k: v for k, v in standards.items() if k != "items" and k != "morality"}
    standards_out = dict(standards)
    standards_out["items"] = list(base_items) + new_items
    standards_out["morality"] = {
        "title": "义务教育道德与法治课程标准（2022年版）",
        "issuer": "中华人民共和国教育部",
        "year": 2022,
        "stage": stage_label(),
        "note": "条目是对道德与法治课标学段内容要求的公开转述，不是逐页核对的原文。verbatim 为 false，page_or_ref 为「待核」。编号 cds-2022 是本图谱编的，不是教育部原编号。小学：一上按2024秋修订统编目录，一下按2025春，二上按2025秋，二下按2026春，三上按2025秋，三下按2026春，四上/五上/六上按2026秋修订目录；四下、五下、六下修订版公开目录仍按现行统编版编排。初中（第四学段）：七上按2024秋、七下按2025春、八上按2025秋、八下按2026春、九上按2026秋修订目录；九下修订版已审定列入教育部2024年目录但截至2026-11-03未公开出版，仍按现行2018年12月第1版目录建点。",
    }
    for k, v in kept_std.items():
        standards_out[k] = v

    math_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cnm_")]
    en_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cne_")]
    phy_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cnp_")]
    zh_before = [(t["id"], t["name"]) for t in base_topics if str(t["id"]).startswith("cnc_")]

    n_hard = sum(1 for e in zh_edges if e["strength"] == "hard")
    n_soft = sum(1 for e in zh_edges if e["strength"] == "soft")
    by_dom = Counter(t["domain"] for t in new_topics)
    print("道德与法治知识点 %d" % len(new_topics))
    for k in VOLUMES:
        print("  %s %d" % (k, by_vol[k]))
    for k, v in by_dom.most_common():
        print("  %s %d" % (k, v))
    print("道德与法治边写入 %d（约简删去 %d）；hard %d，soft %d" % (len(zh_edges), dropped, n_hard, n_soft))
    # 四个数据文件都按 key 原地合并：生成器只覆盖自己产出的条目，其他学科的内容、补题阶段
    # 加进来的题目（带 source / accept / figure 等字段）原样保留、原位不动。重跑构建因此是
    # 幂等的，diff 里只剩真实变化。只有知识点被删掉时，它名下的题目才跟着删。
    dropped_topics = ({t["id"] for t in topics if is_mor_topic_id(t.get("id"))}
                      - {t["id"] for t in new_topics})
    topics_out, _ = merge_generated(topics, new_topics, lambda t: t["id"],
                                    lambda t: is_mor_topic_id(t.get("id")))
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
        lambda e: is_mor_topic_id(e.get("topicId")) or is_mor_topic_id(e.get("prerequisiteId")))
    if {(e["topicId"], e["prerequisiteId"]) for e in deps_out} != \
       {(e["topicId"], e["prerequisiteId"]) for e in merged_deps}:
        print("原地合并后的先修图与约简结果不一致", file=sys.stderr)
        return 1
    items_out, _ = merge_generated(standards.get("items", []), new_items, lambda i: i["id"],
                                   lambda i: str(i.get("id", "")).startswith("cds-"))
    standards_out["items"] = items_out
    n_extra = sum(1 for q in questions_out
                  if q["id"] not in gen_qids and is_mor_topic_id(q.get("topicId")))
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
    again_topics = [t for t in again_t if not is_mor_topic_id(t.get("id"))]
    again_deps = [e for e in again_d if not is_mor_topic_id(e.get("topicId")) and not is_mor_topic_id(e.get("prerequisiteId"))]
    again_qs = [q for q in again_q if not is_mor_topic_id(q.get("topicId"))]
    again_items = [it for it in again_s.get("items", []) if not str(it.get("id", "")).startswith("cds-")]
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
    if again_s.get("morality", {}).get("title") != "义务教育道德与法治课程标准（2022年版）":
        print("道德与法治课标标题不正确", file=sys.stderr)
        return 1
    if [(t["id"], t["name"]) for t in again_t if str(t["id"]).startswith("cnc_")] != zh_before:
        print("语文知识点 id 或名称变了", file=sys.stderr)
        return 1
    print("数学 %d、英语 %d、物理 %d、语文 %d 个知识点的 id 与名称未改" % (
        len(math_before), len(en_before), len(phy_before), len(zh_before)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
