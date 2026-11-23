#!/usr/bin/env python3
"""Convert English 'self' type questions to 'short' (allowed types in test_engine.js)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    converted = 0
    for q in questions:
        if q.get("topicId", "").startswith("cne_") and q.get("type") == "self":
            q["type"] = "short"
            converted += 1

    print("Converted English self→short: %d" % converted)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(questions))


if __name__ == "__main__":
    main()
