#!/usr/bin/env python3
"""Fix question IDs and remove extra fields from reading/essay questions."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

Q_ID_RE = re.compile(r"^((?:cnm_(?:p|h)?|cne_[pjh]|cnp_h?|cnc_[pj]|cns_[pj]|cnd_[pj]|cnh_j|cng_j)\d{3,})_q([1-9]\d*)$")
NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?$")

def is_numeric_answer(ans):
    """Check if answer is a valid numeric value."""
    return bool(NUM_RE.match(str(ans)))

def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    # Track used IDs
    used_ids = set()
    corrections = []
    type_changes = []

    # First pass: collect all existing valid question IDs
    reading_by_topic = {}  # topic_id -> list of (index, question, old_id)
    essay_by_topic = {}    # topic_id -> list of (index, question, old_id)

    for i, q in enumerate(questions):
        qid = q.get("id", "")
        tid = q.get("topicId", "")
        qtype = q.get("type", "")

        if qtype == "reading":
            if tid not in reading_by_topic:
                reading_by_topic[tid] = []
            reading_by_topic[tid].append((i, q, qid))
            # Remove passage field if present
            if "passage" in q:
                del q["passage"]
                corrections.append(f"Removed passage from {qid}")
        elif qtype == "essay":
            if tid not in essay_by_topic:
                essay_by_topic[tid] = []
            essay_by_topic[tid].append((i, q, qid))
        elif qtype == "numeric":
            ans = q.get("answer", "")
            if not is_numeric_answer(ans):
                # Change to self type for fill-in-the-blank
                old_type = qtype
                q["type"] = "self"
                type_changes.append(f"{qid}: {old_type} -> self (non-numeric answer: '{ans[:30]}...')")
                corrections.append(f"Changed {qid} type from numeric to self")
            else:
                if qid in used_ids:
                    corrections.append(f"Duplicate ID: {qid}")
                used_ids.add(qid)
        else:
            # Regular question, track ID
            if qid in used_ids:
                corrections.append(f"Duplicate ID: {qid}")
            used_ids.add(qid)

    # Second pass: renumber reading questions
    for tid, items in reading_by_topic.items():
        # Find the next available number for this topic
        max_q = 1

        # Check existing questions to find highest _q number
        for qid in used_ids:
            match = re.match(r"^" + re.escape(tid) + r"_q(\d+)$", qid)
            if match and int(match.group(1)) >= max_q:
                max_q = int(match.group(1)) + 1

        # Also check other reading questions from other batches
        for other_tid, other_items in reading_by_topic.items():
            if other_tid == tid:
                continue
            for _, q, old_id in other_items:
                match = re.match(r"^" + re.escape(tid) + r"_q(\d+)$", q.get("id", ""))
                if match and int(match.group(1)) >= max_q:
                    max_q = int(match.group(1)) + 1

        # Assign new IDs
        for idx, (i, q, old_id) in enumerate(items):
            new_num = max_q + idx
            new_id = f"{tid}_q{new_num}"
            if new_id in used_ids:
                while new_id in used_ids:
                    new_num += 1
                    new_id = f"{tid}_q{new_num}"
            old_qid = q.get("id", "")
            q["id"] = new_id
            corrections.append(f"Reading ID: {old_qid} -> {new_id}")
            used_ids.add(new_id)

    # Third pass: renumber essay questions
    for tid, items in essay_by_topic.items():
        # Find the next available number for this topic
        max_q = 1

        # Check existing questions to find highest _q number
        for qid in used_ids:
            match = re.match(r"^" + re.escape(tid) + r"_q(\d+)$", qid)
            if match and int(match.group(1)) >= max_q:
                max_q = int(match.group(1)) + 1

        # Assign new IDs
        for idx, (i, q, old_id) in enumerate(items):
            new_num = max_q + idx
            new_id = f"{tid}_q{new_num}"
            if new_id in used_ids:
                while new_id in used_ids:
                    new_num += 1
                    new_id = f"{tid}_q{new_num}"
            old_qid = q.get("id", "")
            q["id"] = new_id
            corrections.append(f"Essay ID: {old_qid} -> {new_id}")
            used_ids.add(new_id)

    print(f"Applied {len(corrections)} corrections:")
    for c in corrections:
        print(f"  {c}")

    print(f"\nType changes ({len(type_changes)}):")
    for t in type_changes[:20]:
        print(f"  {t}")
    if len(type_changes) > 20:
        print(f"  ... and {len(type_changes) - 20} more")

    # Save
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nSaved {len(questions)} questions to {QUESTIONS_PATH}")

if __name__ == "__main__":
    main()