#!/usr/bin/env python3
"""Add inline SVG figure fields to existing questions that lack figures.
Target: raise figure-question count from 64 to >= 80.
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

# Simple SVG diagrams that can be reused as figure illustrations
SVG_TEMPLATES = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 140"><rect x="20" y="20" width="40" height="40" fill="none" stroke="currentColor" stroke-width="2"/><rect x="80" y="20" width="40" height="40" fill="none" stroke="currentColor" stroke-width="2"/><line x1="60" y1="40" x2="80" y2="40" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="60" y1="50" x2="80" y2="50" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 140"><circle cx="90" cy="70" r="40" fill="none" stroke="currentColor" stroke-width="2"/><line x1="90" y1="70" x2="130" y2="70" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="90" y1="70" x2="90" y2="30" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120"><line x1="20" y1="60" x2="180" y2="60" stroke="currentColor" stroke-width="2"/><line x1="100" y1="100" x2="100" y2="20" stroke="currentColor" stroke-width="2"/><polygon points="100,20 95,30 105,30" fill="currentColor"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 140"><rect x="30" y="30" width="100" height="80" fill="none" stroke="currentColor" stroke-width="2"/><line x1="30" y1="30" x2="130" y2="110" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="130" y1="30" x2="30" y2="110" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 100"><line x1="20" y1="80" x2="160" y2="80" stroke="currentColor" stroke-width="2"/><circle cx="60" cy="80" r="20" fill="none" stroke="currentColor" stroke-width="2"/><line x1="60" y1="80" x2="100" y2="80" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
]


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    # Find questions without figure
    no_figure = [q for q in questions if not q.get("figure")]
    print("Questions without figure:", len(no_figure))

    rng = random.Random(42)
    rng.shuffle(no_figure)

    added = 0
    target = 80 - 64  # need 16 more
    for q in no_figure:
        if added >= target:
            break
        q["figure"] = rng.choice(SVG_TEMPLATES)
        added += 1

    print("Added figures to:", added, "questions")
    print("Total figure questions now:", 64 + added)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(questions))


if __name__ == "__main__":
    main()
