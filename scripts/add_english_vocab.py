# -*- coding: utf-8 -*-
"""
添加单词中文意思题到 questions.json

从 english_all.json 加载新题目，替换旧的、质量差的单词中文意思题。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_scratch", "qgen", "batch")
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")


def main():
    # 加载现有的 questions.json
    existing = json.load(io.open(QUESTIONS_PATH, encoding='utf-8'))
    print(f"Loaded existing questions.json: {len(existing)} questions")

    # 找出需要替换的题目（单词中文意思题）
    # 目标是保留 "哪个单词的中文意思是「...」？" 格式的题目
    to_remove = []
    for i, q in enumerate(existing):
        prompt = q.get('prompt', '')
        tid = q.get('topicId', '')
        # 只处理英文知识点 (cne_*)
        if not tid.startswith('cne_'):
            continue
        # 检查是否是单词中文意思题（各种格式）
        # 包含 "中文意思" 或 "意思应是" 或 "是什么意思" 等相关模式
        # 也包含 "意思...是" 这种填空题（如：'lake' 的意思应该是 '湖泊'）
        if ('的中文意思是' in prompt or '中文意思是' in prompt or
            '填空：这个单词的中文意思是什么' in prompt or
            '是什么意思' in prompt or '意思应该' in prompt or
            ('意思' in prompt and '应该' in prompt)):
            to_remove.append(i)
        # 额外检查：短句类型题（type=short）且包含 "意思" 且来自 cne_ 知识点
        elif (q.get('type') == 'short' and tid.startswith('cne_')
              and '意思' in prompt and '是' in prompt):
            to_remove.append(i)

    print(f"Found {len(to_remove)} old vocab questions to replace")

    # 删除旧题目（从大到小删除，避免索引错位）
    for i in sorted(to_remove, reverse=True):
        existing.pop(i)

    print(f"After removal: {len(existing)} questions")

    # 加载新题目
    english_all_path = os.path.join(OUT, "english_all.json")
    new_questions = json.load(io.open(english_all_path, encoding='utf-8'))
    print(f"Loaded {len(new_questions)} new questions from english_all.json")

    # 为新题目添加 id、difficulty、fixed_from_source 等字段
    # 问题是按 topicId 分组计数
    # 使用一个全局计数器来确保没有 ID 冲突
    all_qids = set(q.get('id') for q in existing if q.get('id'))
    topic_q_counters = {}
    for q in new_questions:
        tid = q.get('topicId')
        if not tid:
            continue

        # 计数
        if tid not in topic_q_counters:
            topic_q_counters[tid] = 1
        else:
            topic_q_counters[tid] += 1

        # 生成唯一的 id
        new_qid = f"{tid}_q{topic_q_counters[tid]}"
        # 如果 ID 已存在，继续找下一个可用编号
        while new_qid in all_qids:
            topic_q_counters[tid] += 1
            new_qid = f"{tid}_q{topic_q_counters[tid]}"
        q['id'] = new_qid
        all_qids.add(new_qid)

        # 设置 difficulty（如果没有）
        if 'difficulty' not in q:
            # 按数量分配 difficulty: first 10 basic, next 10 standard, rest challenge
            cnt = topic_q_counters[tid]
            if cnt <= 10:
                q['difficulty'] = 'basic'
            elif cnt <= 20:
                q['difficulty'] = 'standard'
            else:
                q['difficulty'] = 'challenge'

        # 设置 fixed_from_source
        q['fixed_from_source'] = 'ai-generated'

    # 合并
    merged = existing + new_questions
    print(f"Total questions after merge: {len(merged)}")

    # 保存
    json.dump(merged, io.open(QUESTIONS_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"Saved {len(merged)} questions to {QUESTIONS_PATH}")


if __name__ == "__main__":
    main()