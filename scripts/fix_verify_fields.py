#!/usr/bin/env python3
"""Fix mojibake/corrupted verify fields in data/questions.json.

For choice questions: verify = json.dumps(correct_option_text, ensure_ascii=False)
For numeric questions: verify = str(answer) (if numeric) or json.dumps(answer)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    fixed_choice = 0
    fixed_numeric = 0
    already_ok = 0

    for q in questions:
        v = q.get("verify", "")
        if not v:
            continue
        typ = q.get("type")
        # Already valid ASCII verify (expression or quoted text) - skip
        if all(ord(c) < 128 for c in v):
            already_ok += 1
            continue

        # Corrupted verify - need to fix
        if typ == "choice":
            choices = q.get("choices", [])
            answer_key = q.get("answer", "")
            correct_text = None
            for c in choices:
                if c.get("key") == answer_key:
                    correct_text = c.get("text", "")
                    break
            if correct_text:
                q["verify"] = json.dumps(correct_text, ensure_ascii=False)
                fixed_choice += 1
            else:
                print("WARNING: no matching choice for %s answer=%s" % (q.get("id"), answer_key), file=sys.stderr)
        elif typ == "numeric":
            answer = q.get("answer", "")
            # Numeric verify should be a bare expression, not a quoted string.
            # Strip surrounding quotes if present so the evaluator parses it as a number.
            s = answer.strip()
            if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
                s = s[1:-1]
            q["verify"] = s
            fixed_numeric += 1
        else:
            # short/essay/self - leave as-is (not auto-verified anyway)
            pass

    print("Fixed choice verify: %d" % fixed_choice)
    print("Fixed numeric verify: %d" % fixed_numeric)
    print("Already OK: %d" % already_ok)

    # Save
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
    print("Saved %d questions to %s" % (len(questions), QUESTIONS_PATH))


if __name__ == "__main__":
    main()
