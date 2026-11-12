# -*- coding: utf-8 -*-
"""把「孩子端 60 题/点」的缺口切成批次文件，供批量补题。

目标口径（2026-11-11 定案）：confirm=5、只派 choice + numeric、10 次出题不重样
=> 每个知识点 basic 10 / standard 10 / challenge 40 = 60 题。

批次按学科 + 学段切，每片不超过 CHUNK 个点；每片带上该点的 description /
mastery_criteria / 已有题干全文（不截断），让补出来的题不重复情境。
产物只读，写在 _scratch/qgen/batch/（与 out/ 分目录，避免 qgen_merge 认错）。
"""
import io
import json
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_scratch", "qgen", "batch")
CHUNK = 40
TARGET = {"basic": 10, "standard": 10, "challenge": 40}
GRADE_CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九"}


def subject_of(t):
    s = t.get("subject")
    if s:
        return s
    return "math" if t["id"].startswith("cnm_") else t["id"].split("_")[0]


def stage(t):
    g = t.get("grade") or 0
    if g >= 10:
        return "senior"
    return "primary" if g <= 6 else "junior"


def main():
    if not os.path.isdir(OUT):
        os.mkdir(OUT)
    topics = json.load(io.open(os.path.join(ROOT, "data/topics.json"), encoding="utf-8"))
    topics = topics if isinstance(topics, list) else topics["topics"]
    qs = json.load(io.open(os.path.join(ROOT, "data/questions.json"), encoding="utf-8"))
    qs = qs if isinstance(qs, list) else qs["questions"]
    by_topic = collections.defaultdict(list)
    for q in qs:
        by_topic[q["topicId"]].append(q)

    todo = []
    for t in topics:
        if t.get("external"):
            continue
        mine = by_topic.get(t["id"], [])
        diff = [q.get("difficulty") for q in mine]
        need = {k: max(0, TARGET[k] - diff.count(k)) for k in TARGET}
        total = sum(need.values())
        if total == 0:
            continue
        todo.append({
            "topicId": t["id"], "subject": subject_of(t), "stage": stage(t),
            "name": t.get("name"), "grade": t.get("grade"), "semester": t.get("semester"),
            "chapter": t.get("chapter"), "domain": t.get("domain"),
            "description": t.get("description"), "mastery_criteria": t.get("mastery_criteria"),
            "need": need, "total_need": total, "n_existing": len(mine),
            "n_by_difficulty": dict(collections.Counter(diff)),
            # 题干给全文，不截断：补题要靠它判断情境有没有重复
            "existing_prompts": [str(q.get("prompt")) for q in mine],
            "existing_types": sorted(set(q.get("type") for q in mine)),
        })

    groups = collections.defaultdict(list)
    for x in todo:
        groups[(x["subject"], x["stage"])].append(x)
    manifest = []
    for (s, st), items in sorted(groups.items()):
        items.sort(key=lambda x: (x["grade"] or 0, x["topicId"]))
        for i in range(0, len(items), CHUNK):
            part = items[i:i + CHUNK]
            fn = "%s_%s_%02d.json" % (s, st, i // CHUNK + 1)
            json.dump(part, io.open(os.path.join(OUT, fn), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            manifest.append({"file": fn, "subject": s, "stage": st, "count": len(part),
                             "need": {k: sum(p["need"][k] for p in part) for k in TARGET},
                             "total_need": sum(p["total_need"] for p in part)})
    io.open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8").write(
        json.dumps(manifest, ensure_ascii=False, indent=1))
    print("topics=%d batches=%d total_need=%d" % (
        len(todo), len(manifest), sum(p["total_need"] for p in todo)))
    for k in TARGET:
        print("  %s=%d" % (k, sum(1 for p in todo if p["need"][k] > 0)))


if __name__ == "__main__":
    main()