# -*- coding: utf-8 -*-
"""
更新英语单词中文意思题

检查每个英语 topic 的题目数量，补齐不足 60 题的题目。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_scratch", "qgen", "batch")
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")


def is_good_vocab_question(q):
    """检查题目是否是质量好的单词中文意思题"""
    prompt = q.get('prompt', '')
    # 检查是否是我们生成的格式：没有乱码，且包含正确字符
    if '�' in prompt:
        return False
    if not prompt:
        return False
    return True


def main():
    # 加载 questions.json
    existing = json.load(io.open(QUESTIONS_PATH, encoding='utf-8'))
    print(f"Loaded {len(existing)} questions from questions.json")

    # 加载 topics.json 获取 vocab topics
    topics = json.load(io.open(TOPICS_PATH, encoding='utf-8'))
    vocab_topics = []
    for t in topics:
        if t.get('subject') != 'english' or t.get('external'):
            continue
        dq = t.get('diagnostic_question', {})
        question = dq.get('question', '')
        answer = dq.get('answer', '')
        if '哪个单词的意思是「' in question and answer:
            vocab_topics.append(t)

    print(f"Found {len(vocab_topics)} vocab topics in topics.json")

    # 加载我们生成的题目
    english_all_path = os.path.join(OUT, "english_all.json")
    new_questions = json.load(io.open(english_all_path, encoding='utf-8'))
    print(f"Loaded {len(new_questions)} new questions from english_all.json")

    # 统计每个 topic 已有的题目
    topic_questions = {}
    for q in existing:
        tid = q.get('topicId')
        if not tid:
            continue
        if tid not in topic_questions:
            topic_questions[tid] = []
        topic_questions[tid].append(q)

    # 检查哪些 topic 需要补齐
    topics_needing_fill = []
    for t in vocab_topics:
        tid = t['id']
        existing_qs = topic_questions.get(tid, [])
        # 只统计单词中文意思题
        vocab_qs = [q for q in existing_qs if q.get('type') == 'choice' and is_good_vocab_question(q)]
        # 我们要求每个 topic 有 60 题
        if len(vocab_qs) < 60:
            topics_needing_fill.append((tid, 60 - len(vocab_qs)))

    print(f"Topics needing fill: {len(topics_needing_fill)}")

    # 为需要的 topic 获取题目
    new_questions_to_add = []
    for tid, needed in topics_needing_fill:
        # 从我们生成的题目中找出对应的题目
        topic_new = [q for q in new_questions if q.get('topicId') == tid]
        if len(topic_new) >= needed:
            new_questions_to_add.extend(topic_new[:needed])
        else:
            new_questions_to_add.extend(topic_new)

    # 去重（根据 id）
    existing_ids = set(q.get('id') for q in existing)
    added = [q for q in new_questions_to_add if q.get('id') not in existing_ids]
    print(f"Adding {len(added)} new questions")

    # 合并并保存
    merged = existing + added
    json.dump(merged, io.open(QUESTIONS_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"Saved {len(merged)} questions to {QUESTIONS_PATH}")


if __name__ == "__main__":
    main()