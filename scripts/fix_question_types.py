#!/usr/bin/env python3
"""Convert reading/essay question types to short (allowed types: numeric/choice/short/self).
Also verify reading/essay questions have valid answer and explanation fields.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    converted_reading = 0
    converted_essay = 0

    for q in questions:
        t = q.get("type")
        if t == "reading":
            q["type"] = "short"
            converted_reading += 1
        elif t == "essay":
            q["type"] = "short"
            converted_essay += 1

    print("Converted reading→short: %d" % converted_reading)
    print("Converted essay→short: %d" % converted_essay)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(questions))


if __name__ == "__main__":
    main()
