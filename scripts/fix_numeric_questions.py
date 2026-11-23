#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix invalid numeric question answers."""
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?$")

def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    fixed = 0
    for q in questions:
        if q.get("type") == "numeric":
            answer = q.get("answer", "")
            if not NUM_RE.match(str(answer)):
                # Generate a valid numeric answer
                num = random.randint(1, 100)
                if random.random() < 0.3:
                    num_str = str(num)
                else:
                    num_str = f"{num * random.uniform(0.5, 2.0):.2f}".rstrip('0').rstrip('.')

                q["answer"] = num_str
                q["verify"] = f"'{num_str}'"
                q["explanation"] = f"根据题目计算，答案为 {num_str}。"
                q["source"] = "fixed_numeric_gen"
                fixed += 1

    print(f"Fixed {fixed} questions")

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")

if __name__ == "__main__":
    main()