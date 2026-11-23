#!/usr/bin/env python3
"""Remove duplicate question IDs - keep first occurrence only."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    seen = set()
    removed = 0
    total = len(questions)

    new_questions = []
    for q in questions:
        qid = q.get("id", "")
        if qid in seen:
            removed += 1
            continue
        seen.add(qid)
        new_questions.append(q)

    print("Total questions before:", total)
    print("Removed duplicates:", removed)
    print("Total after:", len(new_questions))

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(new_questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(new_questions))


if __name__ == "__main__":
    main()
