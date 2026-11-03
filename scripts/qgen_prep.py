# -*- coding: utf-8 -*-
"""把「缺拓展档」与「basic 只 1 道」的知识点切成批次文件，供批量补题。

批次按学科 + 学段切，每片不超过 CHUNK 个点；每片带上该点已有题干（截断），
让补出来的题不重复情境。产物只读，写在 _scratch/qgen/。
"""
import io
import json
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_scratch", "qgen")
CHUNK = 40
EXT = ("challenge", "advanced")
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
        need = []
        if not [d for d in diff if d in EXT]:
            need.append("challenge")
        if len([d for d in diff if d == "basic"]) < 2:
            need.append("basic")
        if not need:
            continue
        todo.append({
            "topicId": t["id"], "subject": subject_of(t), "stage": stage(t),
            "name": t.get("name"), "grade": t.get("grade"), "semester": t.get("semester"),
            "chapter": t.get("chapter"), "domain": t.get("domain"),
            "description": t.get("description"), "mastery_criteria": t.get("mastery_criteria"),
            "need": need, "n_existing": len(mine),
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
                             "need_challenge": sum(1 for p in part if "challenge" in p["need"]),
                             "need_basic": sum(1 for p in part if "basic" in p["need"])})
    io.open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8").write(
        json.dumps(manifest, ensure_ascii=False, indent=1))
    print("topics=%d batches=%d challenge=%d basic=%d" % (
        len(todo), len(manifest),
        sum(1 for x in todo if "challenge" in x["need"]),
        sum(1 for x in todo if "basic" in x["need"])))


if __name__ == "__main__":
    main()
