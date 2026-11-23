# -*- coding: utf-8 -*-
"""批量生成英语题目。

设计思路：
- 基于 topic 的 diagnostic_question 中的 question/answer 解析核心概念
- 从「哪个单词的意思是「X」」中提取中文意思 X 和英文单词 answer
- 为每种概念设计 choice + short 模板
- 通过变量替换产生变体

题型分布（5:3:2 比例，challenge ≤ 40%）：
- basic: 20 题
- standard: 12 题
- challenge: 8 题
- total: 40 题（每个知识点）
"""
import io
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
OUT = os.path.join(ROOT, "_scratch", "qgen", "batch")

TARGET = {"basic": 20, "standard": 12, "challenge": 8}

# KEYSKEW 阈值
KEYSKEW_THRESHOLD = 0.45

# 英语常用单词作干扰项
COMMON_WORDS = ["apple", "book", "school", "hello", "goodbye", "cat", "dog", "run", "jump", "see",
                "red", "blue", "green", "water", "food", "child", "friend", "house", "tree",
                "big", "small", "hot", "cold", "fast", "slow", "new", "old", "long", "short",
                "ball", "car", "man", "woman", "name", "time", "year", "day", "night",
                "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "china", "japan", "america", "sport", "game", "play", "work", "room", "door", "window",
                "father", "mother", "brother", "sister", "family", "home",
                "be", "is", "are", "was", "were", "go", "goes", "went", "gone",
                "eat", "eats", "ate", "eaten", "drink", "drinks", "drank", "drunk"]


def parse_vocab_word_topic(topic):
    """从 topic 的 diagnostic_question 中提取中文意思和英文单词。
    期望 question 格式为：「哪个单词的意思是「X」？」
    """
    dq = topic.get('diagnostic_question', {})
    question = dq.get('question', '')
    answer = dq.get('answer', '')

    # 从「哪个单词的意思是「X」」中提取 X
    match = re.search(r'「([^」]+)」', question)
    if match:
        chinese_meaning = match.group(1)
    else:
        chinese_meaning = None

    return chinese_meaning, answer


def count_vocab_topics():
    """统计可以用于单词选择题的 topic 数量"""
    topics = json.load(io.open(TOPICS_PATH, encoding='utf-8'))
    vocab_topics = []
    for t in topics:
        if t.get('subject') != 'english' or t.get('external'):
            continue
        dq = t.get('diagnostic_question', {})
        question = dq.get('question', '')
        answer = dq.get('answer', '')
        # 检查是否是单词中文意思题
        if '哪个单词的意思是「' in question and answer:
            vocab_topics.append(t)
    return vocab_topics


def gen_vocab_choice(params, answer_text, chinese_meaning):
    """单词意义选择题

    Args:
        params: 包含 topicId 等信息的 dict
        answer_text: 英文单词答案
        chinese_meaning: 中文意思
    """
    # 确保 answer_text 是字符串
    answer_text = str(answer_text)
    chinese_meaning = str(chinese_meaning)

    # 生成干扰项（不包含答案的单词）
    distractors = [w for w in COMMON_WORDS if w.lower() != answer_text.lower()][:3]

    # 随机决定答案位置 (A/B/C)
    answer_pos = random.choice(["A", "B", "C"])

    # 构建 choices
    choices = []
    if answer_pos == "A":
        choices = [{"key": "A", "text": answer_text}]
        choices.extend([{"key": chr(ord('B') + i), "text": d} for i, d in enumerate(distractors[:2])])
    elif answer_pos == "B":
        choices = [{"key": "A", "text": distractors[0]}]
        choices.append({"key": "B", "text": answer_text})
        choices.append({"key": "C", "text": distractors[1]})
    else:  # C
        choices = [
            {"key": "A", "text": distractors[0]},
            {"key": "B", "text": distractors[1]},
            {"key": "C", "text": answer_text}
        ]

    # 添加 D 选项（确保不重复且不等于答案）
    used_texts = {c['text'].lower() for c in choices}
    d_options = [w for w in COMMON_WORDS if w.lower() != answer_text.lower() and w.lower() not in used_texts]
    d_text = d_options[0] if d_options else "other"
    choices.append({"key": "D", "text": d_text})

    # 构建题目
    prompt = f"哪个单词的中文意思是「{chinese_meaning}」？"
    verify = f"'{answer_text}'"
    explanation = f"正确答案是 {answer_text}。"

    q = {
        'prompt': prompt,
        'answer': answer_pos,
        'choices': choices,
        'verify': verify,
        'type': 'choice',
        'explanation': explanation,
        'topicId': params.get('topicId'),
    }
    return q


def gen_vocab_short(params, answer_text, chinese_meaning):
    """单词填空题

    Args:
        params: 包含 topicId 等信息的 dict
        answer_text: 英文单词答案
        chinese_meaning: 中文意思
    """
    answer_text = str(answer_text)
    chinese_meaning = str(chinese_meaning)

    prompt = f"填空：这个单词的中文意思是什么？"
    verify = answer_text
    explanation = f"正确答案是 {answer_text}。"

    q = {
        'prompt': prompt,
        'answer': str(answer_text),
        'verify': str(answer_text),
        'type': 'short',
        'explanation': explanation,
        'topicId': params.get('topicId'),
    }
    return q


def generate_for_english_topic(topic_id: str, need_basic: int = 20, need_standard: int = 12, need_challenge: int = 8) -> list:
    """为单个 topic 生成英语题目"""
    topics = json.load(io.open(TOPICS_PATH, encoding='utf-8'))
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        print(f"Topic not found: {topic_id}")
        return []

    dq = topic.get('diagnostic_question', {})
    question = dq.get('question', '')
    answer = dq.get('answer', '')

    # 解析中文意思和英文单词
    chinese_meaning, english_word = parse_vocab_word_topic(topic)

    if not chinese_meaning or not english_word:
        print(f"Cannot parse vocab topic {topic_id}: question={question}, answer={answer}")
        return []

    params = {
        'topicId': topic_id,
        'grade': topic.get('grade', 3),
        'subject': 'english',
        'stage': 'junior' if (topic.get('grade', 3) <= 9) else 'senior',
        'classification': 'vocabulary',
        'description': topic.get('description'),
        'name': topic.get('name'),
    }

    qs = []
    choice_answer_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}

    def can_add_answer(key, total):
        if total == 0:
            return True
        new_count = choice_answer_counts.get(key, 0) + 1
        return new_count / (total + 1) < KEYSKEW_THRESHOLD

    def add_choice_with_skew(q):
        ans_key = q.get('answer')
        total_choice = sum(choice_answer_counts.values())
        if can_add_answer(ans_key, total_choice):
            choice_answer_counts[ans_key] += 1
        else:
            # 调整到能保持公平的 key
            for alt_key in ['C', 'B', 'A']:
                if alt_key != ans_key and can_add_answer(alt_key, total_choice):
                    q['answer'] = alt_key
                    # 更新 verify 以匹配新的答案
                    choices = q.get('choices', [])
                    if choices:
                        for c in choices:
                            if c['key'] == alt_key:
                                q['verify'] = f"'{c['text']}'"
                                break
                    choice_answer_counts[alt_key] += 1
                    break
            else:
                # 都不行，接受当前答案
                choice_answer_counts[ans_key] += 1
        return

    def add(q):
        q['topicId'] = topic_id
        if q.get('type') == 'choice':
            add_choice_with_skew(q)
        qs.append(q)

    # 生成题目
    # Basic: 10 题
    for _ in range(need_basic):
        if random.random() < 0.6:
            add(gen_vocab_choice(params, english_word, chinese_meaning))
        else:
            add(gen_vocab_short(params, english_word, chinese_meaning))

    # Standard: 10 题
    for _ in range(need_standard):
        if random.random() < 0.6:
            add(gen_vocab_choice(params, english_word, chinese_meaning))
        else:
            add(gen_vocab_short(params, english_word, chinese_meaning))

    # Challenge: 40 题
    while len(qs) < (need_basic + need_standard + need_challenge):
        if random.random() < 0.6:
            add(gen_vocab_choice(params, english_word, chinese_meaning))
        else:
            add(gen_vocab_short(params, english_word, chinese_meaning))

    # 分配 difficulty
    basic_end = need_basic
    standard_end = need_basic + need_standard
    for i, q in enumerate(qs):
        if i < basic_end:
            q['difficulty'] = 'basic'
        elif i < standard_end:
            q['difficulty'] = 'standard'
        else:
            q['difficulty'] = 'challenge'

    return qs[:need_basic + need_standard + need_challenge]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', help='单个 topic_id')
    parser.add_argument('--all', action='store_true', help='生成所有英语 topic')
    parser.add_argument('--batch', action='store_true', help='遍历 manifest')
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)

    topics = json.load(io.open(TOPICS_PATH, encoding='utf-8'))
    vocab_topics = count_vocab_topics()
    print(f"Found {len(vocab_topics)} vocab topics")

    if args.topic:
        qs = generate_for_english_topic(args.topic)
        out_file = os.path.join(OUT, f"{args.topic}.json")
        json.dump(qs, io.open(out_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f"Written {len(qs)} questions to {out_file}")
        return

    if args.all:
        questions = []
        for t in vocab_topics:
            tid = t['id']
            qs = generate_for_english_topic(tid, need_basic=30, need_standard=18, need_challenge=12)
            questions.extend(qs)
            print(f"Generated {len(qs)} for {tid}")

        out_file = os.path.join(OUT, "english_all.json")
        json.dump(questions, io.open(out_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f"Written {len(questions)} questions to {out_file}")
        return


if __name__ == "__main__":
    main()