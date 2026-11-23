#!/usr/bin/env python3
"""Fix duplicate question IDs."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    # Track used IDs and their counts
    used_ids = {}
    id_positions = {}  # topic_id -> set of used numbers

    for i, q in enumerate(questions):
        qid = q.get("id", "")
        tid = q.get("topicId", "")

        if qid not in used_ids:
            used_ids[qid] = 0
            id_positions[tid] = id_positions.get(tid, set())
            match = re.match(r"^(.+)_q(\d+)$", qid)
            if match:
                num = int(match.group(2))
                id_positions[tid].add(num)

    # Find duplicates and fix them
    corrections = []
    for i, q in enumerate(questions):
        qid = q.get("id", "")
        tid = q.get("topicId", "")

        if used_ids[qid] > 0:
            # This is a duplicate, need to find a new ID
            # Find next available number for this topic
            used_nums = id_positions.get(tid, set())
            new_num = 1
            while new_num in used_nums:
                new_num += 1

            new_id = f"{tid}_q{new_num}"
            used_nums.add(new_num)

            old_id = q["id"]
            q["id"] = new_id
            corrections.append(f"{old_id} -> {new_id}")
        else:
            used_ids[qid] = 1

    print(f"Fixed {len(corrections)} duplicate IDs")
    for c in corrections:
        print(f"  {c}")

    # Save
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Saved {len(questions)} questions to {QUESTIONS_PATH}")

if __name__ == "__main__":
    main()