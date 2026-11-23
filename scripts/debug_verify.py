#!/usr/bin/env python3
"""Debug verify field format for science numeric questions."""
import json
import re
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

with open(QUESTIONS_PATH, encoding="utf-8") as f:
    qs = json.load(f)

# Show a few science numeric verify fields
count = 0
for q in qs:
    if q.get("id", "").startswith("cns_") and q.get("type") == "numeric":
        v = q.get("verify", "")
        print("ID:", q["id"])
        print("  verify repr:", repr(v))
        print("  verify hex:", v.encode("utf-8").hex())
        count += 1
        if count >= 3:
            break

# Check regex match
pattern = re.compile(r"^['\"]([-+]?\d+(?:\.\d+)?)$['\"]$")
for q in qs:
    if q.get("id", "") == "cns_p101_q12":
        v = q.get("verify", "")
        m = pattern.match(v)
        print("Regex match for cns_p101_q12:", m)
        if m:
            print("  Group 1:", m.group(1))
        break
