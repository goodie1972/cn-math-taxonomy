#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix choice question key ordering - keys must be A, B, C, D in order.

The choices array must have keys A, B, C, D in order, and the answer field
must point to the correct key for the correct answer text.

Usage: python3 scripts/fix_choice_keys.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def fix_choice_question(q):
    """Fix the key ordering and answer for a choice question."""
    if q.get('type') != 'choice':
        return q

    choices = q.get('choices', [])
    if not choices:
        return q

    # Determine expected keys based on number of choices (3 or 4)
    num_choices = len(choices)
    if num_choices not in [3, 4]:
        return None  # Unsupported
    expected_keys = ['A', 'B', 'C', 'D'][:num_choices]

    # Get the answer text from the answer key
    answer_key = q.get('answer')
    answer_text = None
    for c in choices:
        if c.get('key') == answer_key:
            answer_text = c.get('text')
            break

    if answer_text is None:
        # Try to get answer from answer field (might be the text itself)
        if isinstance(answer_key, str) and answer_key not in expected_keys:
            for c in choices:
                if c.get('text') == answer_key:
                    answer_text = answer_key
                    answer_key = c.get('key')
                    break

    if answer_text is None:
        return None  # Cannot fix

    # Now assign proper keys A, B, C, D based on position
    texts = [c.get('text') for c in choices]
    answer_pos = -1
    fixed_choices = []
    for i, text in enumerate(texts):
        key = expected_keys[i]
        fixed_choices.append({'key': key, 'text': text})
        if text == answer_text:
            answer_pos = i

    if answer_pos >= 0:
        # Update answer to point to new key
        q['answer'] = expected_keys[answer_pos]

    q['choices'] = fixed_choices
    return q


def main():
    with open(QUESTIONS_PATH, encoding='utf-8') as f:
        questions = json.load(f)

    print(f"Loaded {len(questions)} questions")

    fixed_count = 0
    for q in questions:
        if q.get('type') == 'choice':
            choices = q.get('choices', [])
            expected_keys = ['A', 'B', 'C', 'D']
            actual_keys = [c.get('key') for c in choices]
            if actual_keys != expected_keys:
                fixed_q = fix_choice_question(q)
                if fixed_q:
                    q.update(fixed_q)
                    fixed_count += 1

    print(f"Fixed {fixed_count} questions")

    # Verify fix
    incorrect_after = 0
    for q in questions:
        if q.get('type') == 'choice':
            choices = q.get('choices', [])
            actual_keys = [c.get('key') for c in choices]
            if actual_keys != ['A', 'B', 'C', 'D']:
                incorrect_after += 1

    print(f"Questions still with incorrect keys: {incorrect_after}")

    # Save
    with open(QUESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f"Saved to {QUESTIONS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())