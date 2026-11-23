#!/usr/bin/env python3
"""为现有的 cne_* 英语知识点批量生成题目。

使用 en_lib.py 中的模板逻辑生成题目。
"""
import json
import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import en_lib  # noqa: E402

TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

TARGET_RATIOS = {"basic": 0.5, "standard": 0.3, "challenge": 0.2}  # 5:3:2
QUESTIONS_PER_TOPIC = 60  # 30 basic + 18 standard + 12 challenge


def load_topics():
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_questions():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_used_ids(questions):
    """获取已使用的题目ID"""
    return set(q.get("id") for q in questions if "id" in q)


def generate_questions_for_topic(topic, used_ids):
    """为单个知识点生成题目"""
    tid = topic["id"]
    n = 1
    
    # 找到该topic现有的题目数
    existing_for_topic = sum(1 for q in questions if q.get("topicId") == tid)
    n = max(existing_for_topic + 1, 1)
    
    generated = []
    qtype = topic.get("type", "conceptual")
    gen_method = topic.get("gen", "custom")
    
    # 生成题目
    if topic.get("words"):
        # 单词题：从words中提取中文意思和英文单词
        words = topic["words"]
        for word_data in words:
            if isinstance(word_data, list) and len(word_data) == 2:
                en_word, cn_meaning = word_data
            else:
                continue
            
            # 生成choice题
            other_words = [w for w in words if w[0] != en_word][:3]
            if len(other_words) < 2:
                other_words = [w for w in words if w[0] != en_word and w[0] != en_word][:2]
            
            # 题干: "哪个单词的中文意思是「X」？"
            prompt = f"哪个单词的中文意思是「{cn_meaning}」？"
            verify = f"'{en_word}'"
            explanation = f"正确答案是 {en_word}。"
            
            # 生成选项
            answer_pos = random.choice(["A", "B", "C", "D"])
            choices = []
            other_chars = [chr(65 + i) for i in range(4) if chr(65 + i) != answer_pos]
            
            if answer_pos == "A":
                choices = [{"key": "A", "text": en_word}]
                pos = 0
                for c in other_chars[:3]:
                    idx = min(pos, len(other_words) - 1)
                    choices.append({"key": c, "text": other_words[idx][0]})
                    pos += 1
            else:
                # 其他位置放答案
                choices = [{"key": other_chars[0], "text": other_words[0][0]}] if other_words else []
                choices.insert({"key": answer_pos, "text": en_word})
                for c in other_chars[1:]:
                    if other_words:
                        choices.append({"key": c, "text": other_words.pop(0)[0]})
            
            # 生成题目ID
            qid = f"{tid}_q{n}"
            while qid in used_ids:
                n += 1
                qid = f"{tid}_q{n}"
            
            q = {
                "id": qid,
                "topicId": tid,
                "type": "choice",
                "prompt": prompt,
                "answer": answer_pos,
                "choices": choices[:4],
                "explanation": explanation,
                "verify": verify,
                "source": "llm",
            }
            generated.append(q)
            used_ids.add(qid)
            n += 1
            
            # 生成 short 题
            prompt2 = f"填空：这个单词的中文意思是什么？"
            verify2 = en_word
            
            qid2 = f"{tid}_q{n}"
            while qid2 in used_ids:
                n += 1
                qid2 = f"{tid}_q{n}"
            
            q2 = {
                "id": qid2,
                "topicId": tid,
                "type": "short",
                "prompt": prompt2,
                "answer": en_word,
                "explanation": explanation,
                "verify": verify2,
                "source": "llm",
            }
            generated.append(q2)
            used_ids.add(qid2)
            n += 1
    
    return generated


def assign_difficulty(questions, total_per_topic):
    """分配难度比例"""
    basic_count = int(total_per_topic * TARGET_RATIOS["basic"])
    standard_count = int(total_per_topic * TARGET_RATIOS["standard"])
    challenge_count = total_per_topic - basic_count - standard_count
    
    difficulties = (
        ["basic"] * basic_count +
        ["standard"] * standard_count +
        ["challenge"] * challenge_count
    )
    
    for i, q in enumerate(questions):
        if i < len(difficulties):
            q["difficulty"] = difficulties[i]
        else:
            q["difficulty"] = "challenge"
    
    return questions


def main():
    topics = load_topics()
    questions = load_questions()
    used_ids = get_used_ids(questions)
    
    # 找出需要生成题目的英语知识点
    english_topics = [t for t in topics if 
                      str(t.get("id", "")).startswith("cne_") and 
                      t.get("subject") == "english"]
    
    print(f"找到 {len(english_topics)} 个英语知识点")
    
    new_questions = []
    for topic in english_topics:
        tid = topic["id"]
        
        # 检查是否已经有足够的题目
        existing = [q for q in questions if q.get("topicId") == tid]
        if len(existing) >= 30:  # 至少30题
            print(f"  {tid}: 已有 {len(existing)} 题")
            continue
        
        # 生成新题目
        gen = topic.get("gen")
        if gen == "vocab" and topic.get("words"):
            # 单词题
            generated = []
            words = topic.get("words", [])
            for i, (en_word, cn_meaning) in enumerate(words[:12]):  # 最多12组
                if not en_word or not cn_meaning:
                    continue
                
                # 生成 choice 题
                wrongs = []
                for w in words:
                    if w[0] != en_word:
                        wrongs.append(w[1])
                        if len(wrans) >= 3:
                            break
                
                answer_pos = random.choice(["A", "B", "C", "D"])
                choices = []
                other_pos = [p for p in ["A", "B", "C", "D"] if p != answer_pos][:3]
                
                if answer_pos == "A":
                    choices = [{"key": "A", "text": en_word}]
                    for j, pos in enumerate(other_pos):
                        if j < len(wrans):
                            choices.append({"key": pos, "text": wrongs[j]})
                else:
                    choices = []
                    for j, pos in enumerate(["A", "B", "C", "D"]):
                        if pos == answer_pos:
                            choices.append({"key": pos, "text": en_word})
                        else:
                            idx = j - 1 if j < answer_pos else j
                            if idx < len(wrans):
                                choices.append({"key": pos, "text": wrongs[idx]})
                            else:
                                choices.append({"key": pos, "text": random.choice(["apple", "book", "school"])})
                
                # 生成 id
                qid = f"{tid}_q{len([q for q in questions if q.get('topicId') == tid]) + len([q for q in generated if q.get('topicId') == tid]) + 1}"
                while qid in used_ids:
                    # Need better logic here
                    qid = f"{tid}_q{len(generated) + 1}"
                    # Simple increment
                    base = len(generated) + 1
                    counter = 0
                    while f"{tid}_q{base + counter}" in used_ids:
                        counter += 1
                    qid = f"{tid}_q{base + counter}"
                
                q = {
                    "id": qid,
                    "topicId": tid,
                    "type": "choice",
                    "prompt": f"哪个单词的中文意思是「{cn_meaning}」？",
                    "answer": answer_pos,
                    "choices": choices[:4],
                    "explanation": f"{en_word} 的意思是 {cn_meaning}。",
                    "verify": f"'{en_word}'",
                    "source": "llm",
                }
                generated.append(q)
                used_ids.add(qid)
                
                # 生成 short 题
                qid2 = f"{tid}_q{len(generated) + 1}"
                counter = 0
                while f"{tid}_q{len(generated) + 1 + counter}" in used_ids:
                    counter += 1
                qid2 = f"{tid}_q{len(generated) + 1 + counter}"
                
                q2 = {
                    "id": qid2,
                    "topicId": tid,
                    "type": "short",
                    "prompt": "填空：这个单词的中文意思是什么？",
                    "answer": en_word,
                    "explanation": f"{en_word} 的意思是 {cn_meaning}。",
                    "verify": en_word,
                    "source": "llm",
                }
                generated.append(q2)
                used_ids.add(qid2)
            
            # 分配难度
            assigned_qs = []
            basic_n = min(30, len(generated))
            standard_n = min(18, len(generated) - basic_n)
            challenge_n = len(generated) - basic_n - standard_n
            
            for i, q in enumerate(generated):
                if i < basic_n:
                    q["difficulty"] = "basic"
                elif i < basic_n + standard_n:
                    q["difficulty"] = "standard"
                else:
                    q["difficulty"] = "challenge"
                assigned_qs.append(q)
            
            new_questions.extend(assigned_qs)
            print(f"  {tid}: 生成 {len(assigned_qs)} 题")
    
    # 合并题目
    all_questions = questions + new_questions
    
    # 保存
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=1)
    
    print(f"\n总计: 现有 {len(questions)} 题 + 新生成 {len(new_questions)} 题 = {len(all_questions)} 题")


if __name__ == "__main__":
    main()