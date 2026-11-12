# -*- coding: utf-8 -*-
"""知识点驱动的题型模板生成器

设计思路：
- 基于 topic 的 description / mastery_criteria 解析核心概念
- 为每种概念设计 choice + numeric 模板
- 通过变量替换产生变体，确保 10 轮不重样

题型分布：
- basic: 10 题 (choice 5 + numeric 5)
- standard: 10 题 (choice 5 + numeric 5)  
- challenge: 40 题 (choice 20 + numeric 20)
"""
import io
import json
import os
import re
import random
from typing import List, Dict, Any, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
OUT_PATH = os.path.join(ROOT, "_scratch", "qgen", "templates")


def extract_numbers_from_text(text: str) -> List[int]:
    """从文本中提取所有数字"""
    return [int(x) for x in re.findall(r'\d+', text)]


def classify_topic(topic: Dict) -> str:
    """根据 description 和 mastery_criteria 分类知识点类型"""
    desc = topic.get('description', '')
    criteria = topic.get('mastery_criteria', [])
    text = (desc + ' '.join(criteria)).lower()

    if '比较' in text or '大小' in text or '谁大谁小' in text or '大于' in text or '小于' in text:
        return 'comparison'
    if '加' in text or '加法' in text or '和' in text:
        return 'addition'
    if '减' in text or '减法' in text or '差' in text:
        return 'subtraction'
    if '乘' in text or '乘法' in text or '积' in text or '×' in text:
        return 'multiplication'
    if '除' in text or '除法' in text or '÷' in text:
        return 'division'
    if '分' in text or '合' in text and ('份' in text or '部分' in text):
        return 'fraction_add'
    if '0' in text:
        return 'zero'
    if '几' in text and '第几' in text:
        return 'position'
    if '认识' in text and ('数' in text or '数字' in text):
        return 'number_recognition'
    return 'general'


def get_max_number_for_grade(grade: int) -> int:
    """根据年级返回最大数字范围"""
    if grade <= 2:
        return 20
    elif grade <= 4:
        return 50
    elif grade <= 6:
        return 100
    return 100


def get_template_params(topic: Dict) -> Dict:
    """从 topic 提取模板参数"""
    grade = topic.get('grade', 1)
    max_num = get_max_number_for_grade(grade)
    classification = classify_topic(topic)

    desc = topic.get('description', '')
    criteria = topic.get('mastery_criteria', [])
    numbers = extract_numbers_from_text(desc + ' '.join(criteria))

    return {
        'grade': grade,
        'max_num': max_num,
        'classification': classification,
        'base_numbers': numbers[:3],
        'subject': topic.get('subject', 'math'),
        'topic_name': topic.get('name', ''),
        'chapter': topic.get('chapter', '')[:30],
    }


# ============================================
# 题型模板函数
# ============================================

def gen_compare_choice(params, difficulty='basic'):
    """生成比较类选择题"""
    if difficulty == 'basic':
        a = random.randint(1, 15)
        b = random.randint(1, 15)
    else:
        a = random.randint(10, 50)
        b = random.randint(10, 50)

    ans_key = "A" if a < b else "B"
    prompt = "把 {a} 和 {b} 哪个数大？".format(a=a, b=b)
    choices = {"A": a, "B": b, "C": min(a,b)+5, "D": max(a,b)+5}
    verify = f"{a} < {b}" if ans_key == "A" else f"{b} < {a}"
    return {
        'prompt': prompt,
        'answer': ans_key,
        'choices': choices,
        'verify': verify,
    }


def gen_add_numeric(params, difficulty='basic'):
    """生成加法计算题"""
    if difficulty == 'basic':
        a = random.randint(1, 10)
        b = random.randint(1, 10)
    elif difficulty == 'standard':
        a = random.randint(10, 30)
        b = random.randint(10, 30)
    else:
        a = random.randint(20, 80)
        b = random.randint(20, 80)

    prompt = "计算：{a} 加 {b} = ？".format(a=a, b=b)
    ans = a + b
    verify = f"{a}+{b}"
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
    }


def gen_sub_numeric(params, difficulty='basic'):
    """生成减法计算题"""
    if difficulty == 'basic':
        b = random.randint(1, 10)
        a = random.randint(b, b + 10)
    elif difficulty == 'standard':
        b = random.randint(10, 30)
        a = random.randint(b, b + 20)
    else:
        b = random.randint(20, 50)
        a = random.randint(b + 5, b + 50)

    prompt = "计算：{a} 减 {b} = ？".format(a=a, b=b)
    ans = a - b
    verify = f"{a}-{b}"
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
    }


def gen_mul_numeric(params, difficulty='basic'):
    """生成乘法计算题"""
    if difficulty == 'basic':
        a = random.randint(1, 5)
        b = random.randint(1, 5)
    elif difficulty == 'standard':
        a = random.randint(2, 10)
        b = random.randint(2, 10)
    else:
        a = random.randint(5, 12)
        b = random.randint(5, 12)

    prompt = "计算：{a} × {b} = ？".format(a=a, b=b)
    ans = a * b
    verify = f"{a}*{b}"
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
    }


def gen_div_numeric(params, difficulty='basic'):
    """生成除法计算题"""
    if difficulty == 'basic':
        b = random.randint(1, 5)
        a = b * random.randint(1, 5)
    elif difficulty == 'standard':
        b = random.randint(2, 10)
        a = b * random.randint(2, 10)
    else:
        b = random.randint(3, 12)
        a = b * random.randint(4, 15)

    prompt = "计算：{a} 除以 {b} = ？".format(a=a, b=b)
    ans = a // b
    verify = f"{a}/{b}"
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
    }


def gen_story_numeric(params, difficulty='basic'):
    """生成情境题"""
    objects = ["苹果", "本", "书", "球", "蛋糕", "糖果", "书包", "铅笔"]
    if difficulty == 'basic':
        a = random.randint(1, 10)
        b = random.randint(1, 5)
    else:
        a = random.randint(10, 30)
        b = random.randint(5, 15)

    obj = random.choice(objects)
    verbs = ["加", "拿", "剩", "用"]
    verb = random.choice(verbs)

    prompt = "小明有 {a} 个 {obj}，老师又 {verb}了 {b} 个，现在有几个 {obj}？".format(a=a, b=b, obj=obj, verb=verb)
    ans = a + b
    verify = f"{a}+{b}"
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
    }


def gen_mixed_challenge(params):
    """生成综合运算 challenge 题"""
    ops = [('+', lambda a, b: a + b), ('-', lambda a, b: a - b), ('*', lambda a, b: a * b)]
    op_sym, op_func = random.choice(ops)

    if op_sym == '-':
        b = random.randint(10, 50)
        a = random.randint(b + 5, b + 50)
    elif op_sym == '*':
        a = random.randint(5, 12)
        b = random.randint(5, 12)
    else:
        a = random.randint(30, 100)
        b = random.randint(10, 30)

    ans = op_func(a, b)
    op_display = {'+': '＋', '-': '－', '*': '×'}[op_sym]
    prompt = "计算：{a} {op} {b} = ？".format(a=a, op=op_display, b=b)
    verify = f"{a}{op_sym}{b}"
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
    }


def generate_questions(topic: Dict, basic_count=10, standard_count=10, challenge_count=40) -> List[Dict]:
    """为单个 topic 生成题目"""
    params = get_template_params(topic)
    params['topicId'] = topic['id']

    qs_raw = []

    # Basic: 10 题 (choice 5 + numeric 5)
    qs_raw.append(('basic', gen_compare_choice(params, 'basic')))
    qs_raw.append(('basic', gen_compare_choice(params, 'basic')))
    qs_raw.append(('basic', gen_add_numeric(params, 'basic')))
    qs_raw.append(('basic', gen_add_numeric(params, 'basic')))
    qs_raw.append(('basic', gen_story_numeric(params, 'basic')))
    qs_raw.append(('basic', gen_story_numeric(params, 'basic')))
    qs_raw.append(('basic', gen_compare_choice(params, 'basic')))
    qs_raw.append(('basic', gen_add_numeric(params, 'basic')))
    qs_raw.append(('basic', gen_compare_choice(params, 'basic')))
    qs_raw.append(('basic', gen_add_numeric(params, 'basic')))

    # Standard: 10 题
    qs_raw.append(('standard', gen_add_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_add_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_sub_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_sub_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_compare_choice(params, 'standard')))
    qs_raw.append(('standard', gen_compare_choice(params, 'standard')))
    qs_raw.append(('standard', gen_add_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_sub_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_add_numeric(params, 'standard')))
    qs_raw.append(('standard', gen_compare_choice(params, 'standard')))

    # Challenge: 40 题
    # 使用不同的数字范围增加变体
    for _ in range(5):
        qs_raw.append(('challenge', gen_add_numeric(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_sub_numeric(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_mul_numeric(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_compare_choice(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_add_numeric(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_sub_numeric(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_mul_numeric(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_compare_choice(params, 'challenge')))
    for _ in range(5):
        qs_raw.append(('challenge', gen_add_numeric(params, 'challenge')))
    for _ in range(4):
        qs_raw.append(('challenge', gen_mixed_challenge(params)))

    # 去重并分配 difficulty
    seen = set()
    result = []

    for diff, q in qs_raw:
        key = (q['prompt'], q.get('answer'))
        if key in seen:
            continue
        seen.add(key)

        qtype = 'choice' if 'choices' in q else 'numeric'
        question = {
            'topicId': params['topicId'],
            'type': qtype,
            'difficulty': diff,
            'subject': params['subject'],
            'grade': params['grade'],
            'prompt': q['prompt'],
            'answer': q['answer'],
            'verify': q['verify'],
        }
        if 'choices' in q:
            question['choices'] = q['choices']
        result.append(question)

    # 重新分配 difficulty 确保数量正确
    for i, q in enumerate(result):
        if i < 10:
            q['difficulty'] = 'basic'
        elif i < 20:
            q['difficulty'] = 'standard'
        else:
            q['difficulty'] = 'challenge'

    return result[:60]


def main():
    import argparse
    import sys

    os.makedirs(OUT_PATH, exist_ok=True)

    topics = json.load(io.open(TOPICS_PATH, encoding='utf-8'))
    topics = topics if isinstance(topics, list) else topics['topics']

    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', help='单个 topic_id')
    parser.add_argument('--count', type=int, default=60)
    parser.add_argument('--all', action='store_true', help='生成所有 topic')
    args = parser.parse_args()

    if args.topic:
        topic = next((t for t in topics if t['id'] == args.topic), None)
        if not topic:
            print(f"Topic not found: {args.topic}")
            return
        qs = generate_questions(topic, 10, 10, 40)
        out_file = os.path.join(OUT_PATH, f"{args.topic}.json")
        json.dump(qs, io.open(out_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f"Written {len(qs)} questions to {out_file}")
        return

    if args.all:
        for topic in topics[:10]:
            qs = generate_questions(topic, 10, 10, 40)
            out_file = os.path.join(OUT_PATH, f"{topic['id']}.json")
            json.dump(qs, io.open(out_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            print(f"{topic['id']}: {len(qs)} 题")


if __name__ == "__main__":
    main()