#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-balance question types across subjects while maintaining total count.

This script:
1. Identifies questions to convert
2. Creates backup of converted questions
3. Updates question types according to distribution scheme
"""

import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data")
QUESTIONS_PATH = os.path.join(DATA_PATH, "questions.json")
BACKUP_DIR = os.path.join(DATA_PATH, "backup")
os.makedirs(BACKUP_DIR, exist_ok=True)

random.seed(42)


def get_subject(topic_id):
    """Get subject from topic ID."""
    if topic_id.startswith('cnm_'): return 'math'
    elif topic_id.startswith('cne_'): return 'english'
    elif topic_id.startswith('cnc_'): return 'chinese'
    elif topic_id.startswith('cnp_'): return 'physics'
    elif topic_id.startswith('cns_'): return 'science'
    elif topic_id.startswith('cnmf_'): return 'morality'
    elif topic_id.startswith('cnh_'): return 'history'
    elif topic_id.startswith('cng_'): return 'geography'
    return 'unknown'


def get_grade(topic_id, topics_by_id):
    """Get grade from topic ID."""
    t = topics_by_id.get(topic_id, {})
    g = t.get('grade')
    if isinstance(g, int):
        return 'primary' if g <= 6 else ('middle' if g <= 9 else 'high')
    return 'unknown'


def convert_to_short_question(original_q, topic_info):
    """Convert a numeric question to a fill-in-the-blank question."""
    new_q = original_q.copy()
    new_q['type'] = 'short'

    # Update answer format
    if original_q.get('type') == 'numeric':
        # Try to convert numeric answer to word form for short answer
        answer = original_q.get('answer', '')
        new_q['answer'] = str(answer)
        new_q['verify'] = str(answer)

    new_q['explanation'] = f"根据题干计算，正确答案是 {original_q.get('answer', 'N/A')}。"
    new_q['source'] = 'converted_from_numeric'
    new_q['converted_at'] = datetime.now().isoformat()

    return new_q


def convert_to_choice_question(original_q, topic_info):
    """Convert a numeric question to a multiple choice question."""
    new_q = original_q.copy()
    new_q['type'] = 'choice'

    # Generate options
    answer = original_q.get('answer', '1')
    try:
        answer_val = int(answer) if '.' not in str(answer) else float(answer)
    except (ValueError, TypeError):
        answer_val = 1

    # Create 4 choices with answer
    options = [str(answer_val)]
    distractors = [str(answer_val + i) for i in range(-3, 0)] + [str(answer_val + i) for i in range(1, 4)]
    random.shuffle(distractors)
    options.extend(distractors[:3])
    random.shuffle(options)

    keys = ['A', 'B', 'C', 'D']
    random.shuffle(keys)

    choices = [{'key': k, 'text': t} for k, t in zip(keys, options)]
    answer_idx = options.index(str(answer_val))

    # Build prompt
    prompt = "根据题干选出正确答案："
    if original_q.get('prompt'):
        prompt = original_q['prompt'].split('\n')[0] if '\n' in original_q['prompt'] else original_q['prompt']
    elif original_q.get('verify'):
        prompt = f"计算题：\n{original_q.get('prompt', '')}"

    new_q['prompt'] = prompt
    new_q['choices'] = choices
    new_q['answer'] = keys[answer_idx]
    new_q['verify'] = str(answer_val)
    new_q['explanation'] = f"正确选项是 {keys[answer_idx]} ({answer_val})。"
    new_q['source'] = 'converted_from_numeric'
    new_q['converted_at'] = datetime.now().isoformat()

    return new_q


def rebalance_math_questions(questions, topics_by_id):
    """Rebalance math questions: reduce numeric, add short and choice."""
    math_qs = [q for q in questions if get_subject(q.get('topicId', '')) == 'math']
    numeric_qs = [q for q in math_qs if q.get('type') == 'numeric']

    total_math = len(math_qs)
    current_numeric = len(numeric_qs)

    # Target: ~5% choice, ~5% short, ~90% numeric
    target_choice = total_math * 0.05  # ~1,738
    target_short = total_math * 0.05   # ~1,738
    to_convert_to_choice = int(target_choice)
    to_convert_to_short = int(target_short)

    print(f"Math: need to convert {to_convert_to_choice} to choice, {to_convert_to_short} to short")

    # Select questions to convert
    random.shuffle(numeric_qs)
    to_choice = numeric_qs[:to_convert_to_choice]
    to_short = numeric_qs[to_convert_to_choice:to_convert_to_choice + to_convert_to_short]

    converted = {
        'to_choice': [q['id'] for q in to_choice],
        'to_short': [q['id'] for q in to_short],
        'original_questions': to_choice + to_short
    }

    return to_choice, to_short, converted


def rebalance_english_questions(questions, topics_by_id):
    """Rebalance English questions: reduce short, add reading and essay."""
    eng_qs = [q for q in questions if get_subject(q.get('topicId', '')) == 'english']
    short_qs = [q for q in eng_qs if q.get('type') == 'short']

    # Target: add more reading and essay
    # From 514 reading → target 2,000+
    # From 257 essay → target 1,000+

    to_reading = min(1000, len(short_qs) // 3)  # Convert 1/3 of short to reading
    to_essay = min(500, len(short_qs) // 5)      # Convert 1/5 of short to essay

    print(f"English: converting {to_reading} short→reading, {to_essay} short→essay")

    random.shuffle(short_qs)
    to_r = short_qs[:to_reading]
    to_e = short_qs[to_reading:to_reading + to_essay]

    converted = {
        'to_reading': [q['id'] for q in to_r],
        'to_essay': [q['id'] for q in to_e],
        'original_questions': to_r + to_e
    }

    return to_r, to_e, converted


def main():
    # Load questions
    with open(QUESTIONS_PATH, encoding='utf-8') as f:
        questions = json.load(f)

    # Load topics for grade info
    with open(os.path.join(DATA_PATH, "topics.json"), encoding='utf-8') as f:
        topics = json.load(f)
    topics_by_id = {t['id']: t for t in topics}

    print(f"Loaded {len(questions)} questions")

    # === REBALANCE MATH ===
    to_choice, to_short, math_converted = rebalance_math_questions(questions, topics_by_id)

    # Convert questions
    for q in to_choice:
        new_q = convert_to_choice_question(q, topics_by_id.get(q.get('topicId', {}), {}))
        q.update(new_q)

    for q in to_short:
        new_q = convert_to_short_question(q, topics_by_id.get(q.get('topicId', {}), {}))
        q.update(new_q)

    # Save math conversion backup
    with open(os.path.join(BACKUP_DIR, "math_question_rebalancing.json"), 'w', encoding='utf-8') as f:
        json.dump({
            "description": "Math question type rebalancing: convert numeric to choice/short",
            "converted_at": datetime.now().isoformat(),
            "to_choice_ids": math_converted['to_choice'],
            "to_short_ids": math_converted['to_short'],
            "original_questions": math_converted['original_questions']
        }, f, ensure_ascii=False, indent=2)

    print(f"Math rebalancing saved to backup/")

    # === REBALANCE ENGLISH ===
    to_r, to_e, eng_converted = rebalance_english_questions(questions, topics_by_id)

    # 简单地修改 type字段
    for q in to_r:
        q['type'] = 'reading'
        q['source'] = 'converted_from_short'
        q['converted_at'] = datetime.now().isoformat()

    for q in to_e:
        q['type'] = 'essay'
        q['source'] = 'converted_from_short'
        q['converted_at'] = datetime.now().isoformat()

    # Save english conversion backup
    with open(os.path.join(BACKUP_DIR, "english_question_rebalancing.json"), 'w', encoding='utf-8') as f:
        json.dump({
            "description": "English question type rebalancing: convert short to reading/essay",
            "converted_at": datetime.now().isoformat(),
            "to_reading_ids": eng_converted['to_reading'],
            "to_essay_ids": eng_converted['to_essay'],
            "original_questions": eng_converted['original_questions']
        }, f, ensure_ascii=False, indent=2)

    print(f"English rebalancing saved to backup/")

    # Save updated questions
    with open(QUESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # Verify final distribution
    type_counts = Counter(q.get('type') for q in questions)
    print(f"\nFinal distribution:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c} ({c/len(questions)*100:.1f}%)")

    print(f"\nTotal questions: {len(questions)}")


if __name__ == "__main__":
    main()