#!/usr/bin/env python3
"""Deduplicate question IDs - keep first occurrence, fix subsequent ones with _dup suffix."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    seen = set()
    deduped = 0
    total = len(questions)

    new_questions = []
    for q in questions:
        qid = q.get("id", "")
        if qid in seen:
            # Find next available number
            base = qid
            n = 2
            while f"{base}_dup{n}" in seen:
                n += 1
            new_id = f"{base}_dup{n}"
            q["id"] = new_id
            seen.add(new_id)
            deduped += 1
        else:
            seen.add(qid)
        new_questions.append(q)

    print("Total questions:", total)
    print("Deduplicated:", deduped)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(new_questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(new_questions))


if __name__ == "__main__":
    main()
