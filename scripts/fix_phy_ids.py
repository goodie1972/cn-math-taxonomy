#!/usr/bin/env python3
"""Fix physics question IDs: cnp_001q1 -> cnp_001_q1 format."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

# Pattern: topicId without underscore before q<number>
BAD_ID = re.compile(r"^(cnp_h?\d+)q(\d+)$")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    fixed = 0
    seen_ids = set()
    dup_errors = 0

    for q in questions:
        tid = q.get("topicId", "")
        qid = q.get("id", "")
        m = BAD_ID.match(qid)
        if m:
            new_id = f"{m.group(1)}_q{m.group(2)}"
            # Check for duplicates
            if new_id in seen_ids:
                dup_errors += 1
                print("DUPLICATE: %s -> %s" % (qid, new_id))
                continue
            q["id"] = new_id
            seen_ids.add(new_id)
            fixed += 1

    print("Fixed IDs:", fixed)
    print("Duplicate errors:", dup_errors)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(questions))


if __name__ == "__main__":
    main()
