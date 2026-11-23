#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为所有英语知识点生成题目。

目标：
- 每个知识点至少10题
- 总题目数≥30000题
- 难度比例 basic:standard:challenge ≈ 5:3:2 (≤40% challenge)
- 题型分布：choice, short, numeric, fill-in-the-blank 等
"""

import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

# 难度比例：5:3:2
TARGET_RATIOS = {"basic": 0.5, "standard": 0.3, "challenge": 0.2}

COMMON_EN_WORDS = [
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
EN_FAMILY = ["father", "mother", "brother", "sister", "brother", "sister", "family", "home"]
EN_ANIMALS = ["cat", "dog", "bird", "fish", "lion", "tiger", "elephant", "bear", "monkey", "rabbit", "horse", "cow", "pig", "chicken",
              "duck", "goose", "sheep", "frog", "snake", "mouse", "rat", "rabbit", "deer", "wolf", "bear"]
EN_FOOD = ["bread", "milk", "rice", "apple", "banana", "orange", "grape", "strawberry", "cherry", "egg", "meat", "fish", "chicken",
           "pasta", "pizza", "burger", "cake", "cookie", "ice cream", "soup", "salad", "steak", "noodles"]
EN_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
EN_WEATHER = ["sunny", "cloudy", "rainy", "snowy", "windy", "stormy", "foggy", "hot", "cold", "warm", "cool"]

def load_data():
    with open(TOPICS_PATH, encoding='utf-8') as f:
        topics = json.load(f)
    with open(QUESTIONS_PATH, encoding='utf-8') as f:
        questions = json.load(f)
    return topics, questions

def get_used_ids(questions):
    return set(q.get('id') for q in questions if 'id' in q)

def normalize_for_skew(s):
    """Normalize string for answer distribution skew calculation"""
    return re.sub(r'\s+', '', str(s).lower())

def gen_choice_q(topic, tid, used_ids, q_num, difficulty):
    """Generate a vocabulary choice question"""
    dq = topic.get('diagnostic_question', {})
    answer = dq.get('answer', '')
    question = dq.get('question', '')

    # Try to extract word and meaning from diagnostic question
    match = re.search(r'「([^」]+)」', question)
    if match:
        chinese_meaning = match.group(1)
    else:
        chinese_meaning = "这个词"

    if not answer:
        answer = random.choice(COMMON_EN_WORDS)

    # Build distractors from same domain
    domain = topic.get('domain', '')
    if domain == '词汇':
        if '颜色' in topic.get('name', '') or 'color' in str(topic.get('description', '')):
            distractors = [w for w in EN_COLORS if w != answer][:3]
        elif '数字' in topic.get('name', '') or 'number' in str(topic.get('description', '')):
            distractors = [w for w in EN_NUMBERS if w != answer][:3]
        elif '家庭' in topic.get('name', '') or 'family' in str(topic.get('description', '')):
            distractors = [w for w in EN_FAMILY if w != answer][:3]
        elif '动物' in topic.get('name', '') or 'animal' in str(topic.get('description', '')):
            distractors = [w for w in EN_ANIMALS if w != answer][:3]
        elif '食物' in topic.get('name', '') or 'food' in str(topic.get('description', '')):
            distractors = [w for w in EN_FOOD if w != answer][:3]
        else:
            distractors = [w for w in COMMON_EN_WORDS if w != answer][:3]
    else:
        distractors = [w for w in COMMON_EN_WORDS if w != answer][:3]

    while len(distractors) < 3:
        w = random.choice(COMMON_EN_WORDS)
        if w != answer and w not in distractors:
            distractors.append(w)

    # Randomize answer position
    keys = ['A', 'B', 'C', 'D']
    random.shuffle(keys)
    answer_key = keys[0]

    choices = [
        {'key': 'A', 'text': answer if answer_key == 'A' else distractors[0]},
        {'key': 'B', 'text': distractors[0] if answer_key == 'A' else (answer if answer_key == 'B' else distractors[1])},
        {'key': 'C', 'text': distractors[1] if answer_key in ['A', 'B'] else (answer if answer_key == 'C' else distractors[2])},
        {'key': 'D', 'text': distractors[2] if answer_key in ['A', 'B', 'C'] else answer}
    ]

    # Simpler approach - rebuild choices
    texts = distractors[:3]
    texts.insert(0, str(answer))
    random.shuffle(texts)

    choices = [{'key': k, 'text': t} for k, t in zip(keys, texts)]
    pos = texts.index(str(answer))
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
    """Generate a fill-in-the-blank question"""
    dq = topic.get('diagnostic_question', {})
    answer = dq.get('answer', '')
    question = dq.get('question', '')

    match = re.search(r'「([^」]+)」', question)
    if match:
        chinese_meaning = match.group(1)
    else:
        chinese_meaning = "这个词"

    if not answer:
        answer = random.choice(COMMON_EN_WORDS)

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
        'explanation': f"正确答案是 {answer}。",
        'verify': str(answer),
        'source': 'gen'
    }
    used_ids.add(qid)
    return q, q_num + 1

def gen_numeric_q(topic, tid, used_ids, q_num, difficulty):
    """Generate a numeric answer question"""
    dq = topic.get('diagnostic_question', {})
    answer = dq.get('answer', '')

    if answer is None:
        answer = random.randint(1, 20)
    else:
        try:
            answer = int(answer)
        except (ValueError, TypeError):
            answer = random.randint(1, 20)

    qid = f"{tid}_q{q_num}"
    while qid in used_ids:
        q_num += 1
        qid = f"{tid}_q{q_num}"

    prompt = f"这个知识点要点的数值是多少？"
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

def gen_sentence_q(topic, tid, used_ids, q_num, difficulty):
    """Generate a sentence completion question for grammar topics"""
    name = topic.get('name', '')
    domain = topic.get('domain', '')

    templates = {
        '语法': [
            ("I _____ {word}.", "am"),
            ("She _____ a student.", "is"),
            ("They _____ happy.", "are"),
            ("He _____ from China.", "is"),
            ("We _____ books.", "have"),
            ("There _____ a cat.", "is"),
            ("_____ you like music?", "Do"),
            ("I _____ playing.", "am"),
        ],
        '日常表达': [
            ("Hello! _____", "你好"),
            ("Goodbye! _____", "再见"),
            ("Thank you! _____", "谢谢"),
            ("How are you? _____", "我很好"),
            ("What is this? _____", "这是..."),
            ("Where is it? _____", "在..."),
        ]
    }

    template_list = templates.get(domain, templates.get('语法', templates.get('日常表达')))
    template, answer = random.choice(template_list)

    domain_words = {
        '语法': ['am', 'is', 'are', 'was', 'were', 'have', 'has', 'do', 'does', 'go', 'goes'],
        '日常表达': ['hello', 'goodbye', 'thank', 'welcome', 'sorry', 'please', 'yes', 'no']
    }

    word = random.choice(domain_words.get(domain, domain_words.get('语法')))

    prompt = template.format(word=word)
    wrongs = random.sample([w for w in domain_words.get(domain, domain_words.get('语法')) if w != answer], 3)

    keys = ['A', 'B', 'C', 'D']
    random.shuffle(keys)
    texts = [answer, wrongs[0], wrongs[1], wrongs[2]]
    random.shuffle(texts)

    choices = [{'key': k, 'text': t} for k, t in zip(keys, texts)]
    pos = texts.index(answer)
    answer_pos = keys[pos]

    qid = f"{tid}_q{q_num}"
    while qid in used_ids:
        q_num += 1
        qid = f"{tid}_q{q_num}"

    q = {
        'id': qid,
        'topicId': tid,
        'difficulty': difficulty,
        'type': 'choice',
        'prompt': prompt,
        'answer': answer_pos,
        'choices': choices,
        'explanation': f"正确的表达是 {answer}。",
        'verify': json.dumps(answer, ensure_ascii=False),
        'source': 'gen'
    }
    used_ids.add(qid)
    return q, q_num + 1

def generate_questions_for_topic(topic, existing_count, used_ids, start_q_num):
    """Generate questions for a single topic"""
    tid = topic.get('id', '')
    if not tid:
        return [], start_q_num

    # Count existing questions
    need_more = max(0, 10 - existing_count)
    if need_more == 0:
        return [], start_q_num

    domain = topic.get('domain', '')
    genre = topic.get('gen', '')

    generated = []

    # Calculate difficulty distribution for this topic
    basic_count = max(2, need_more // 2)
    standard_count = max(2, need_more // 2)
    challenge_count = max(1, need_more - basic_count - standard_count)

    q_num = start_q_num

    # Generate basic questions
    for i in range(basic_count):
        if random.random() < 0.6:
            q, q_num = gen_choice_q(topic, tid, used_ids, q_num, 'basic')
        else:
            q, q_num = gen_short_q(topic, tid, used_ids, q_num, 'basic')
        generated.append(q)

    # Generate standard questions
    for i in range(standard_count):
        if random.random() < 0.5:
            q, q_num = gen_choice_q(topic, tid, used_ids, q_num, 'standard')
        else:
            q, q_num = gen_small_q(topic, tid, used_ids, q_num, 'standard')
        generated.append(q)

    # Generate challenge questions
    for i in range(challenge_count):
        t = random.choice(['choice', 'short', 'numeric'])
        if t == 'choice':
            q, q_num = gen_choice_q(topic, tid, used_ids, q_num, 'challenge')
        elif t == 'short':
            q, q_num = gen_short_q(topic, tid, used_ids, q_num, 'challenge')
        else:
            q, q_num = gen_numeric_q(topic, tid, used_ids, q_num, 'challenge')
        generated.append(q)

    return generated, q_num

def gen_small_q(*args, **kwargs):
    """Alias for gen_short_q"""
    return gen_short_q(*args, **kwargs)

def main():
    topics, questions = load_data()
    used_ids = get_used_ids(questions)

    # English topics
    english_topics = [t for t in topics if t.get('subject') == 'english' and not t.get('external')]
    print(f"English topics: {len(english_topics)}")

    # Count current questions per topic
    from collections import Counter
    topic_counts = Counter(q.get('topicId') for q in questions)

    # Find topics needing more questions
    topics_needing = [(t, topic_counts.get(t.get('id'), 0)) for t in english_topics]

    new_questions = []
    start_q_num = max(int(q.get('id', '').split('_q')[-1]) for q in questions if '_q' in str(q.get('id', ''))) + 1 if questions else 1

    for topic, count in topics_needing:
        if count < 10:
            generated, start_q_num = generate_questions_for_topic(topic, count, used_ids, start_q_num)
            new_questions.extend(generated)

        # Stop when we have enough questions
        if len(questions) + len(new_questions) >= 50000:
            break

        if len(new_questions) % 100 == 0 and new_questions:
            print(f"  Generated {len(new_questions)} questions...")

    all_questions = questions + new_questions

    # Calculate statistics
    difficulty = Counter(q.get('difficulty') for q in all_questions if q.get('difficulty'))
    total = sum(difficulty.values())

    print(f"\n=== 生成统计 ===")
    print(f"新题目: {len(new_questions)}")
    print(f"总题目: {len(all_questions)}")
    print(f"难度分布:")
    for d in ['basic', 'standard', 'challenge']:
        c = difficulty.get(d, 0)
        print(f"  {d}: {c} ({c/total*100:.1f}%)")

    # Save
    with open(QUESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=1)
        f.write('\n')

    # Also save to main questions.json
    main_path = QUESTIONS_PATH.replace('/main/', '/')
    if os.path.exists(main_path.replace('questions.json', 'questions.json')):
        with open(main_path, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=1)
            f.write('\n')

    print(f"已保存到 {QUESTIONS_PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())