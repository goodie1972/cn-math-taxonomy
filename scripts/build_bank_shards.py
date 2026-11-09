#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 data/bank/ —— 学科骨架 + 学科×册题库分片 + 版本×学科顺序表 + manifest。

真源是 data/topics.json、data/dependencies.json、data/questions.json、
data/editions/registry.json，本脚本只读不写它们。产物进 git，静态托管直接可用，无后端。

  python scripts/build_bank_shards.py            # 构建（并删除 manifest 不再声明的陈旧产物）
  python scripts/build_bank_shards.py --check    # 只比对不写；有差异或缺文件退出码 1
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_registry import norm_vol, subject_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bank")
SOURCES = ["data/topics.json", "data/dependencies.json", "data/questions.json", "data/editions/registry.json"]


def read_json(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def volume_of(topic):
    return norm_vol((topic.get("chapter") or "").strip().split(" ")[0])


def first_seen(pairs):
    out = []
    for v in pairs:
        if v not in out:
            out.append(v)
    return out


def build():
    topics = read_json("data/topics.json")
    deps = read_json("data/dependencies.json")
    questions = read_json("data/questions.json")
    registry = read_json("data/editions/registry.json")

    h = hashlib.sha256()
    for rel in SOURCES:
        with io.open(os.path.join(ROOT, rel), "rb") as f:
            h.update(f.read())

    topic_volume = {}
    by_subject = {}
    for t in topics:
        if t["id"] in topic_volume:
            raise SystemExit("真源 topics 有重复 id：" + t["id"])
        s = subject_of(t)
        topic_volume[t["id"]] = volume_of(t)
        by_subject.setdefault(s, []).append(t)
    for q in questions:
        if q["topicId"] not in topic_volume:
            raise SystemExit("题目挂在未知知识点上：" + q["id"])

    files = {}
    manifest = {"buildId": h.hexdigest()[:12], "subjects": {}, "editions": {}, "topicVolume": topic_volume}

    for s in sorted(by_subject):
        ts = by_subject[s]
        allow = set(t["id"] for t in ts)
        ds = [d for d in deps if d["topicId"] in allow and d["prerequisiteId"] in allow]
        graph_rel = "graph/%s.json" % s
        files[graph_rel] = compact({"topics": ts, "deps": ds})
        volumes = first_seen(topic_volume[t["id"]] for t in ts)
        shards = {}
        for v in volumes:
            ids = set(t["id"] for t in ts if topic_volume[t["id"]] == v)
            qs = [q for q in questions if q["topicId"] in ids]
            rel = "questions/%s/%s.json" % (s, v)
            body = compact({"questions": qs})
            files[rel] = body
            shards[v] = {"file": rel, "topics": len(ids), "questions": len(qs), "bytes": len(body.encode("utf-8"))}
        manifest["subjects"][s] = {"graphFile": graph_rel, "topics": len(ts), "volumes": volumes, "shards": shards}

    for ed in registry["versions"]:
        entry = {"label": ed["label"], "subjects": {}}
        for s, sv in ed["subjects"].items():
            for tid in sv["topicIds"]:
                if tid not in topic_volume:
                    raise SystemExit("registry 引用了未知知识点：%s/%s %s" % (ed["id"], s, tid))
            rel = "order/%s/%s.json" % (ed["id"], s)
            files[rel] = compact({"topicIds": sv["topicIds"]})
            entry["subjects"][s] = {
                "label": sv["label"], "topics": len(sv["topicIds"]),
                "volumes": first_seen(topic_volume[tid] for tid in sv["topicIds"]), "orderFile": rel,
            }
        manifest["editions"][ed["id"]] = entry

    files["manifest.json"] = compact(manifest)
    return files, manifest["buildId"]


def disk_files():
    out = {}
    if not os.path.isdir(OUT):
        return out
    for dirpath, _, names in os.walk(OUT):
        for n in names:
            full = os.path.join(dirpath, n)
            out[os.path.relpath(full, OUT).replace(os.sep, "/")] = full
    return out


def main():
    check = "--check" in sys.argv[1:]
    files, build_id = build()
    existing = disk_files()
    changed = [rel for rel in sorted(files)
               if rel not in existing or io.open(existing[rel], encoding="utf-8").read() != files[rel]]
    stale = sorted(set(existing) - set(files))
    print("buildId=%s files=%d changed=%d stale=%d" % (build_id, len(files), len(changed), len(stale)))
    if check:
        for rel in changed:
            print("  CHANGED " + rel)
        for rel in stale:
            print("  STALE   " + rel)
        return 1 if (changed or stale) else 0
    for rel in sorted(files):
        full = os.path.join(OUT, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(files[rel])
    for rel in stale:
        print("  PRUNE " + rel)
        os.remove(existing[rel])
    print("OK -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())