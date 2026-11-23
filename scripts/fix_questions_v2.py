#!/usr/bin/env python3
"""Fix question IDs and remove extra fields from reading/essay questions."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?$")

def is_numeric_answer(ans):
    """Check if answer is a valid numeric value."""
    return bool(NUM_RE.match(str(ans)))

def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    corrections = []
    type_changes = []

    # First pass: Collect all valid IDs and fix numeric->self types
    used_ids = set()

    for q in questions:
        qtype = q.get("type", "")
        qid = q.get("id", "")
        tid = q.get("topicId", "")

        if qtype == "numeric":
            ans = q.get("answer", "")
            if not is_numeric_answer(ans):
                q["type"] = "self"
                type_changes.append(f"{qid}: numeric -> self")
            else:
                if qid in used_ids:
                    corrections.append(f"Duplicate ID: {qid}")
                used_ids.add(qid)
        elif qtype not in ("reading", "essay"):
            if qid in used_ids:
                corrections.append(f"Duplicate ID: {qid}")
            used_ids.add(qid)

    # Second pass: Renumber reading questions
    # Group by topic
    reading_by_topic = {}
    for i, q in enumerate(questions):
        if q.get("type") == "reading":
            tid = q.get("topicId", "")
            if tid not in reading_by_topic:
                reading_by_topic[tid] = []
            reading_by_topic[tid].append((i, q, q.get("id", "")))
            # Remove passage field
            if "passage" in q:
                del q["passage"]

    # Calculate existing max ID per topic
    topic_max_q = {}
    for qid in used_ids:
        m = re.match(r"^(.+)_q(\d+)$", qid)
        if m:
            tid = m.group(1)
            num = int(m.group(2))
            if tid not in topic_max_q or num > topic_max_q[tid]:
                topic_max_q[tid] = num

    # Assign new IDs to reading questions
    for tid, items in reading_by_topic.items():
        start_num = topic_max_q.get(tid, 0) + 1
        for idx, (i, q, old_id) in enumerate(items):
            new_id = f"{tid}_q{start_num + idx}"
            if new_id in used_ids:
                # Find next available
                while new_id in used_ids:
                    start_num += 1
                    new_id = f"{tid}_q{start_num}"
            old_qid = q.get("id", "")
            q["id"] = new_id
            corrections.append(f"Reading ID: {old_qid} -> {new_id}")
            used_ids.add(new_id)

    # Third pass: Renumber essay questions
    essay_by_topic = {}
    for i, q in enumerate(questions):
        if q.get("type") == "essay":
            tid = q.get("topicId", "")
            if tid not in essay_by_topic:
                essay_by_topic[tid] = []
            essay_by_topic[tid].append((i, q, q.get("id", "")))

    # Assign new IDs to essay questions
    for tid, items in essay_by_topic.items():
        start_num = topic_max_q.get(tid, 0) + 1
        for idx, (i, q, old_id) in enumerate(items):
            new_id = f"{tid}_q{start_num + idx}"
            if new_id in used_ids:
                while new_id in used_ids:
                    start_num += 1
                    new_id = f"{tid}_q{start_num}"
            old_qid = q.get("id", "")
            q["id"] = new_id
            corrections.append(f"Essay ID: {old_qid} -> {new_id}")
            used_ids.add(new_id)

    print(f"Applied {len(corrections)} corrections:")
    for c in corrections:
        print(f"  {c}")

    print(f"\nType changes ({len(type_changes)}):")
    for t in type_changes[:20]:
        print(f"  {t}")
    if len(type_changes) > 20:
        print(f"  ... and {len(type_changes) - 20} more")

    # Save
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nSaved {len(questions)} questions to {QUESTIONS_PATH}")

if __name__ == "__main__":
    main()