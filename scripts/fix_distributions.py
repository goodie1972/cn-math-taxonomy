#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix math difficulty distribution and remove English numeric questions."""
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data")
QUESTIONS_PATH = os.path.join(DATA_PATH, "questions.json")
TOPICS_PATH = os.path.join(DATA_PATH, "topics.json")

random.seed(42)


def get_subject(topic_id):
    if topic_id.startswith('cnm_'): return 'math'
    elif topic_id.startswith('cne_'): return 'english'
    elif topic_id.startswith('cnc_'): return 'chinese'
    elif topic_id.startswith('cnp_'): return 'physics'
    elif topic_id.startswith('cns_'): return 'science'
    elif topic_id.startswith('cnd_'): return 'morality'
    elif topic_id.startswith('cnh_'): return 'history'
    elif topic_id.startswith('cng_'): return 'geography'
    return 'unknown'


def main():
    with open(QUESTIONS_PATH, encoding='utf-8') as f:
        questions = json.load(f)
    with open(TOPICS_PATH, encoding='utf-8') as f:
        topics = json.load(f)
    topics_by_id = {t['id']: t for t in topics}

    print(f"Loaded {len(questions)} questions")

    # === FIX 1: Math difficulty distribution (target: 50%:30%:20%) ===
    math_qs = [q for q in questions if get_subject(q.get('topicId', '')) == 'math']
    basic = [q for q in math_qs if q.get('difficulty') == 'basic']
    standard = [q for q in math_qs if q.get('difficulty') == 'standard']
    challenge = [q for q in math_qs if q.get('difficulty') == 'challenge']

    total_math = len(math_qs)
    target_basic = int(total_math * 0.50)
    target_standard = int(total_math * 0.30)
    target_challenge = int(total_math * 0.20)

    print(f"\nMath difficulty before:")
    print(f"  Basic: {len(basic)} ({len(basic)/total_math*100:.1f}%)")
    print(f"  Standard: {len(standard)} ({len(standard)/total_math*100:.1f}%)")
    print(f"  Challenge: {len(challenge)} ({len(challenge)/total_math*100:.1f}%)")

    # We need to convert challenge -> basic and challenge -> standard
    need_basic = target_basic - len(basic)
    need_standard = target_standard - len(standard)
    # Challenge has excess equal to need_basic + need_standard

    random.shuffle(challenge)

    to_basic = challenge[:need_basic]
    to_standard = challenge[need_basic:need_basic + need_standard]

    for q in to_basic:
        q['difficulty'] = 'basic'
        q['source'] = 'rebalanced_difficulty'

    for q in to_standard:
        q['difficulty'] = 'standard'
        q['source'] = 'rebalanced_difficulty'

    # === FIX 2: English numeric questions should be converted to short ===
    en_numeric = [q for q in questions if get_subject(q.get('topicId', '')) == 'english' and q.get('type') == 'numeric']
    print(f"\nEnglish numeric questions to convert: {len(en_numeric)}")

    for q in en_numeric:
        tid = q['topicId']
        topic_name = topics_by_id.get(tid, {}).get('name', tid)
        q['type'] = 'short'
        q['prompt'] = f"{topic_name}的简答题：请用简短的文字回答。"
        q['answer'] = "简要回答"
        q['verify'] = f"'{topic_name[:20]}'"
        q['explanation'] = "根据知识点名称作答。"
        q['source'] = 'converted_from_english_numeric'

    # Save the updated questions
    with open(QUESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # Verify final distribution
    math_qs_new = [q for q in questions if get_subject(q.get('topicId', '')) == 'math']
    basic_new = [q for q in math_qs_new if q.get('difficulty') == 'basic']
    standard_new = [q for q in math_qs_new if q.get('difficulty') == 'standard']
    challenge_new = [q for q in math_qs_new if q.get('difficulty') == 'challenge']

    print(f"\nMath difficulty after:")
    print(f"  Basic: {len(basic_new)} ({len(basic_new)/len(math_qs_new)*100:.1f}%)")
    print(f"  Standard: {len(standard_new)} ({len(standard_new)/len(math_qs_new)*100:.1f}%)")
    print(f"  Challenge: {len(challenge_new)} ({len(challenge_new)/len(math_qs_new)*100:.1f}%)")

    en_numeric_new = [q for q in questions if get_subject(q.get('topicId', '')) == 'english' and q.get('type') == 'numeric']
    print(f"\nEnglish numeric questions remaining: {len(en_numeric_new)}")

    # Count total
    total_questions = len(questions)
    print(f"\nTotal questions: {total_questions}")

    type_counts = Counter(q.get('type') for q in questions)
    print("By type:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c} ({c/total_questions*100:.1f}%)")

    diff_counts = Counter(q.get('difficulty') for q in questions)
    print("By difficulty:")
    for d in ['basic', 'standard', 'challenge']:
        c = diff_counts.get(d, 0)
        print(f"  {d}: {c} ({c/total_questions*100:.1f}%)")

    print("\nDone!")


if __name__ == "__main__":
    main()