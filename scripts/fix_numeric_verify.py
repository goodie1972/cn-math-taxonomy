#!/usr/bin/env python3
"""Fix numeric verify fields that are quoted strings (e.g. '18.64' -> 18.64).
The evaluator needs bare expressions like 18.64, not quoted strings.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

# Pattern: a quoted string containing only digits, decimal point, optional leading minus
QUOTED_NUMERIC = re.compile(r"^['\"]([-+]?\d+(?:\.\d+)?)['\"]$")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    fixed = 0
    already_ok = 0

    for q in questions:
        if q.get("type") != "numeric":
            continue
        v = q.get("verify", "")
        if not v:
            continue
        m = QUOTED_NUMERIC.match(v)
        if m:
            q["verify"] = m.group(1)
            fixed += 1
        elif all(ord(c) < 128 for c in v):
            already_ok += 1

    print("Fixed numeric quoted-verify: %d" % fixed)
    print("Already OK (bare expression): %d" % already_ok)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(questions))


if __name__ == "__main__":
    main()
