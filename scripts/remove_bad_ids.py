#!/usr/bin/env python3
"""Remove physics questions with bad ID format (cnp_XXXqNN without underscore)."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

BAD_ID = re.compile(r"^(cnp_\d+)q(\d+)$")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    removed = 0
    new_questions = []
    for q in questions:
        qid = q.get("id", "")
        if BAD_ID.match(qid):
            removed += 1
            continue
        new_questions.append(q)

    print("Removed bad-format IDs:", removed)
    print("Total after:", len(new_questions))

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(new_questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(new_questions))


if __name__ == "__main__":
    main()
