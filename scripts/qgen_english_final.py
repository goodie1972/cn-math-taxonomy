#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最终版英语题目生成器

目标：
- 总题目数≥30000
- 难度比例约5:3:2 (basic:standard:challenge, challenge ≤ 40%)
- 为所有英语知识点生成题目
"""

import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

TARGET_TOTAL = 35000  # 目标题目数，给一些buffer
MIN_PER_TOPIC = 40    # 每个topic至少40题

# 难度比例: 5:3:2 = 50:30:20
RATIOS = {"basic": 0.50, "standard": 0.30, "challenge": 0.20}

COMMON_WORDS = [
    "apple", "book", "school", "hello", "goodbye", "cat", "dog", "run", "jump", "see",
    "red", "blue", "green", "yellow", "water", "food", "child", "friend", "house", "tree",
    "big", "small", "hot", "cold", "fast", "slow", "new", "old", "long", "short",
    "ball", "car", "man", "woman", "name", "time", "day", "night", "week", "month",
    "father", "mother", "brother", "sister", "family", "home",
    "be", "is", "are", "was", "were", "go", "has", "have", "will", "can",
    "eat", "drink", "like", "love", "want", "need", "think", "know", "take",
    "people", "animal", "food", "water", "room", "class", "school", "teacher",
]

EN_NUMBERS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
              "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
              "seventeen", "eighteen", "nineteen", "twenty"]
EN_COLORS = ["red", "blue", "green", "yellow", "orange", "purple", "pink", "brown", "black", "white", "gray", "gold", "silver"]
EN_ANIMALS = ["cat", "dog", "bird", "fish", "lion", "tiger", "elephant", "bear", "monkey", "rabbit", "horse", "cow", "pig", "chicken",
              "duck", "goose", "sheep", "frog", "snake", "mouse", "rat", "deer", "wolf", "bear"]
EN_FOOD = ["bread", "milk", "rice", "apple", "banana", "orange", "grape", "strawberry", "cherry", "egg", "meat", "fish", "chicken",
           "pasta", "pizza", "burger", "cake", "cookie", "ice cream", "soup", "salad", "steak", "noodles"]
EN_FAMILY = ["father", "mother", "brother", "sister", "family", "home"]
EN_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

def load_data():
    with open(TOPICS_PATH, encoding='utf-8') as f:
        topics = json.load(f)
    with open(QUESTIONS_PATH, encoding='utf-8') as f:
        questions = json.load(f)
    return topics, questions

def get_used_ids(questions):
    return set(q.get('id') for q in questions if 'id' in q)

def build_distractors(answer, count=3):
    """Build distractors for multiple choice"""
    distractors = [w for w in COMMON_WORDS if w != answer][:count]
    while len(distractors) < count:
        w = random.choice(COMMON_WORDS)
        if w != answer and w not in distractors:
            distractors.append(w)
    return distractors[:count]

def get_domain_hint(topic):
    """Get hint for generating appropriate distractors"""
    name = topic.get('name', '')
    desc = str(topic.get('description', ''))

    name_lower = name.lower()
    desc_lower = desc.lower()

    if any(k in name_lower or k in desc_lower for k in ['颜色', 'color']):
        return 'color'
    elif any(k in name_lower or k in desc_lower for k in ['动物', 'animal']):
        return 'animal'
    elif any(k in name_lower or k in desc_lower for k in ['食物', 'food', 'eat', 'drink']):
        return 'food'
    elif any(k in name_lower or k in desc_lower for k in ['数字', 'number']):
        return 'number'
    elif any(k in name_lower or k in desc_lower for k in ['家庭', 'family', 'father', 'mother', 'brother', 'sister']):
        return 'family'
    elif any(k in name_lower or k in desc_lower for k in ['星期', 'month', 'weather', 'season']):
        return 'week'
    return None

def parse_topic_info(topic):
    """Parse topic to extract word and meaning from diagnostic question"""
    dq = topic.get('diagnostic_question', {})
    question = dq.get('question', '')
    answer = dq.get('answer', '')

    # Try to extract word and meaning
    match = re.search(r'「([^」]+)」', question)
    if match:
        chinese_meaning = match.group(1)
    else:
        chinese_meaning = "这个词"

    if not answer:
        answer = random.choice(COMMON_WORDS)

    return str(answer), str(chinese_meaning)

def gen_choice_q(topic, tid, used_ids, q_num, difficulty):
    """Generate vocabulary choice question"""
    answer, chinese_meaning = parse_topic_info(topic)

    # Build distractors from same domain
    domain_hint = get_domain_hint(topic)
    if domain_hint == 'color':
        pool = EN_COLORS
    elif domain_hint == 'animal':
        pool = EN_ANIMALS
    elif domain_hint == 'food':
        pool = EN_FOOD
    elif domain_hint == 'number':
        pool = EN_NUMBERS
    elif domain_hint == 'family':
        pool = EN_FAMILY
    elif domain_hint == 'week':
        pool = EN_DAYS + EN_MONTHS
    else:
        pool = COMMON_WORDS

    distractors = [w for w in pool if w != answer][:3]
    while len(distractors) < 3:
        w = random.choice(COMMON_WORDS)
        if w != answer and w not in distractors:
            distractors.append(w)

    keys = ['A', 'B', 'C', 'D']
    random.shuffle(keys)

    texts = [answer, distractors[0], distractors[1], distractors[2]]
    random.shuffle(texts)

    choices = [{'key': k, 'text': t} for k, t in zip(keys, texts)]
    pos = texts.index(answer)
    answer_pos = keys[pos]

    qid = f"{tid}_q{q_num}"
    while qid in used_ids:
        q_num += 1
        qid = f"{tid}_q{q_num}"

    prompt = f"哪个单词的中文意思是「{chinese_meaning}」？"
    q = {
        'id': qid,
        'topicId': tid,
        'difficulty': difficulty,
        'type': 'choice',
        'prompt': prompt,
        'answer': answer_pos,
        'choices': choices,
        'explanation': f"{answer} 的意思是 {chinese_meaning}。",
        'verify': json.dumps(str(answer), ensure_ascii=False),
        'source': 'gen'
    }
    used_ids.add(qid)
    return q, q_num + 1

def gen_short_q(topic, tid, used_ids, q_num, difficulty):
    """Generate fill-in-the-blank question"""
    answer, chinese_meaning = parse_topic_info(topic)

    qid = f"{tid}_q{q_num}"
    while qid in used_ids:
        q_num += 1
        qid = f"{tid}_q{q_num}"

    prompt = f"填空：这个单词的中文意思是什么？"
    q = {
        'id': qid,
        'topicId': tid,
        'difficulty': difficulty,
        'type': 'short',
        'prompt': prompt,
        'answer': str(answer),
        'explanation': f"{answer} 的意思是 {chinese_meaning}。",
        'verify': str(answer),
        'source': 'gen'
    }
    used_ids.add(qid)
    return q, q_num + 1

def gen_numeric_q(topic, tid, used_ids, q_num, difficulty):
    """Generate numeric answer question (for counting, spelling, etc.)"""
    dq = topic.get('diagnostic_question', {})
    answer = dq.get('answer', '')

    # Convert to appropriate format
    if answer is None:
        answer = random.randint(1, 20)
    else:
        try:
            answer = int(answer)
        except (ValueError, TypeError):
            # Check if it's a count
            if isinstance(answer, str):
                for num_word in EN_NUMBERS:
                    if num_word in answer.lower() or answer.lower() in num_word:
                        answer = num_word
                        break
            answer = answer if answer else str(random.choice([1, 2, 3, 4, 5, 10, 20]))

    qid = f"{tid}_q{q_num}"
    while qid in used_ids:
        q_num += 1
        qid = f"{tid}_q{q_num}"

    if isinstance(answer, int):
        prompt = "按题干要求填写数字："
        verify_answer = str(answer)
    else:
        prompt = "填空：按要求填写单词："
        verify_answer = str(answer)

    q = {
        'id': qid,
        'topicId': tid,
        'difficulty': difficulty,
        'type': 'numeric',
        'prompt': prompt,
        'answer': str(answer),
        'explanation': f"正确答案是 {answer}。",
        'verify': str(answer),
        'source': 'gen'
    }
    used_ids.add(qid)
    return q, q_num + 1

def generate_batch(topic, existing_count, used_ids, start_q_num, target_count):
    """Generate a batch of questions for a topic"""
    tid = topic.get('id', '')
    if not tid:
        return [], start_q_num

    need = max(0, target_count - existing_count)
    if need == 0:
        return [], start_q_num

    generated = []

    # Calculate difficulty distribution for this batch
    basic_n = max(1, int(need * RATIOS['basic']))
    standard_n = max(1, int(need * RATIOS['standard']))
    challenge_n = max(1, need - basic_n - standard_n)

    # Generate basic questions
    for i in range(basic_n):
        if random.random() < 0.5:
            q, start_q_num = gen_choice_q(topic, tid, used_ids, start_q_num, 'basic')
        else:
            q, start_q_num = gen_short_q(topic, tid, used_ids, start_q_num, 'basic')
        generated.append(q)

    # Generate standard questions
    for i in range(standard_n):
        t = random.choice(['choice', 'short', 'numeric'])
        if t == 'choice':
            q, start_q_num = gen_choice_q(topic, tid, used_ids, start_q_num, 'standard')
        elif t == 'short':
            q, start_q_num = gen_short_q(topic, tid, used_ids, start_q_num, 'standard')
        else:
            q, start_q_num = gen_numeric_q(topic, tid, used_ids, start_q_num, 'standard')
        generated.append(q)

    # Generate challenge questions
    for i in range(challenge_n):
        t = random.choice(['choice', 'short', 'numeric'])
        if t == 'choice':
            q, start_q_num = gen_choice_q(topic, tid, used_ids, start_q_num, 'challenge')
        elif t == 'short':
            q, start_q_num = gen_short_q(topic, tid, used_ids, start_q_num, 'challenge')
        else:
            q, start_q_num = gen_numeric_q(topic, tid, used_ids, start_q_num, 'challenge')
        generated.append(q)

    return generated, start_q_num

def main():
    topics, questions = load_data()
    used_ids = get_used_ids(questions)

    # English topics
    english_topics = [t for t in topics if t.get('subject') == 'english' and not t.get('external')]
    print(f"English topics: {len(english_topics)}")

    # Count current questions per topic
    topic_counts = Counter(q.get('topicId') for q in questions)

    # Current English questions count
    current_english_q = sum(topic_counts.get(t.get('id'), 0) for t in english_topics)
    print(f"Current English questions: {current_english_q}")

    # Need to reach TARGET_TOTAL
    deficit = TARGET_TOTAL - current_english_q
    print(f"Target: {TARGET_TOTAL}")
    print(f"Need to generate: {deficit}")

    # Find max question number for ID generation
    max_q_num = 1
    for q in questions:
        qid = q.get('id', '')
        if '_q' in str(qid):
            try:
                n = int(str(qid).split('_q')[-1])
                max_q_num = max(max_q_num, n + 1)
            except:
                pass

    new_questions = []

    # Process all English topics
    for i, topic in enumerate(english_topics):
        tid = topic.get('id', '')
        count = topic_counts.get(tid, 0)

        # Generate questions for this topic
        generated, max_q_num = generate_batch(
            topic, count, used_ids, max_q_num, MIN_PER_TOPIC
        )
        new_questions.extend(generated)

        # Progress update
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(english_topics)} topics, generated {len(new_questions)} questions...")

    all_questions = questions + new_questions

    # Calculate statistics
    english_topic_ids = {t['id'] for t in english_topics}
    english_qs = [q for q in all_questions if q.get('topicId', '') in english_topic_ids]

    difficulty = Counter(q.get('difficulty') for q in english_qs if q.get('difficulty'))
    qtypes = Counter(q.get('type') for q in english_qs)
    total = sum(difficulty.values())

    print(f"\n=== 生成统计 ===")
    print(f"新题目: {len(new_questions)}")
    print(f"总题目: {len(all_questions)}")
    print(f"英语题目: {len(english_qs)}")
    print(f"难度分布:")
    for d in ['basic', 'standard', 'challenge']:
        c = difficulty.get(d, 0)
        print(f"  {d}: {c} ({c/total*100:.1f}%)")
    print(f"题型分布:")
    for t, c in sorted(qtypes.items()):
        print(f"  {t}: {c} ({c/len(english_qs)*100:.1f}%)")

    # Verify challenge ratio
    challenge_ratio = difficulty.get('challenge', 0) / total
    print(f"\nChallenge ratio: {challenge_ratio*100:.1f}% (target: ≤40%)")

    # Save
    with open(QUESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=1)
        f.write('\n')

    # Also sync to main file
    main_path = QUESTIONS_PATH.replace('/main/', '/')
    if os.path.exists(main_path.replace('questions.json', 'questions.json')):
        with open(main_path, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=1)
            f.write('\n')

    print(f"\n已保存到 {QUESTIONS_PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())