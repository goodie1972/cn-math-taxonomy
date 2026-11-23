#!/usr/bin/env python3
"""为现有的 cne_* 英语知识点生成题目。

此脚本读取 topics.json 中的所有英语知识点，
使用 en_lib.py 中的模板生成题目，并按 5:3:2 比例分配难度。
"""
import json
import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import en_lib  # noqa: E402

TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
QUESTIONS_PATH = os.path.join(ROOT, "data", "main", "questions.json")

TARGET_RATIOS = {"basic": 0.5, "standard": 0.3, "challenge": 0.2}
QUESTIONS_PER_TOPIC = 40  # 20 basic + 12 standard + 8 challenge


def load_topics():
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_questions():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_used_ids(questions):
    return set(q.get("id") for q in questions if "id" in q)


_global_questions = []  # 用于引用

def generate_questions_for_topic(topic, used_ids, questions_list):
    """为单个知识点生成题目"""
    tid = topic["id"]
    n = 1
    
    # 找该topic的最大题号
    existing_for_topic = [q for q in questions if q.get("topicId") == tid]
    if existing_for_topic:
        max_n = max(int(q["id"].split("_q")[-1]) for q in existing_for_topic if "_q" in q.get("id", ""))
        n = max_n + 1
    
    # 获取知识点的生成信息
    gen = topic.get("gen")
    words = topic.get("words")
    sound = topic.get("sound")
    goods = topic.get("goods")
    bads = topic.get("bads")
    items = topic.get("items")
    
    generated = []
    
    # 生成题目
    if words and gen == "vocab":
        # 单词题：从words中提取中文意思和英文单词
        for en_word, cn_meaning in words:
            if not en_word or not cn_meaning:
                continue
            
            # 生成 choice 题
            other_words = [(w, c) for w, c in words if w != en_word]
            if len(other_words) < 2:
                continue
            
            wrongs = [c for w, c in other_words[:3]]
            
            # 生成选项
            answer_pos = random.choice(["A", "B", "C", "D"])
            choices = []
            other_chars = [p for p in ["A", "B", "C", "D"] if p != answer_pos][:3]
            
            if answer_pos == "A":
                choices = [{"key": "A", "text": en_word}]
                for j, pos in enumerate(other_chars):
                    if j < len(wrons):
                        choices.append({"key": pos, "text": wrongs[j]})
            else:
                choices = [{"key": "A", "text": wrongs[0]}] if wrongs else []
                choices.insert({"key": answer_pos, "text": en_word})
                for j, pos in enumerate(["B", "C", "D"]):
                    if j < len(wrons) - 1:
                        choices.append({"key": pos, "text": wrongs[j + 1] if j + 1 < len(wrons) else random.choice(["apple", "book", "school"])})
            
            # 生成 id
            qid = f"{tid}_q{n}"
            while qid in used_ids:
                n += 1
                qid = f"{tid}_q{n}"
            
            q = {
                "id": qid,
                "topicId": tid,
                "type": "choice",
                "prompt": f"哪个单词的中文意思是「{cn_meaning}」？",
                "answer": answer_pos,
                "choices": [c for c in choices if "text" in c],
                "explanation": f"{en_word} 的意思是 {cn_meaning}。",
                "verify": f"'{en_word}'",
                "source": "llm",
            }
            generated.append(q)
            used_ids.add(qid)
            n += 1
            
            # 生成 short 题
            qid2 = f"{tid}_q{n}"
            while qid2 in used_ids:
                n += 1
                qid2 = f"{tid}_q{n}"
            
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
            n += 1
    
    # 分配难度
    basic_n = int(len(generated) * TARGET_RATIOS["basic"])
    standard_n = int(len(generated) * TARGET_RATIOS["standard"])
    
    for i, q in enumerate(generated):
        if i < basic_n:
            q["difficulty"] = "basic"
        elif i < basic_n + standard_n:
            q["difficulty"] = "standard"
        else:
            q["difficulty"] = "challenge"
    
    return generated


def main():
    topics = load_topics()
    questions = load_questions()
    used_ids = get_used_ids(questions)
    
    # 找出需要生成题目的英语知识点
    english_topics = [t for t in topics if 
                      str(t.get("id", "")).startswith("cne_") and 
                      any(t.get("subject") == "english" or t.get("id", "").startswith("cne_"))]
    
    print(f"找到 {len(english_topics)} 个英语知识点")
    
    # 统计每个topic现有题目数
    topic_counts = {}
    for tid in [t["id"] for t in english_topics]:
        topic_counts[tid] = len([q for q in questions if q.get("topicId") == tid])
    
    new_questions = []
    for topic in english_topics:
        tid = topic["id"]
        existing = topic_counts.get(tid, 0)
        
        if existing >= 20:  # 每题点至少20题
            print(f"  {tid}: 已有 {existing} 题")
            continue
        
        # 生成新题目
        gen = topic.get("gen")
        generated = []
        
        if gen == "vocab" and topic.get("words"):
            words = topic.get("words", [])
            for en_word, cn_meaning in words:
                if not en_word or not cn_meaning:
                    continue
                
                # 生成 choice 题
                wrongs = [(w, c) for w, c in words if w != en_word][:3]
                wrongs_text = [c for w, c in wrongs]
                
                if len(wrons_text) < 2:
                    continue
                
                answer_pos = random.choice(["A", "B", "C", "D"])
                choices = []
                other_chars = [p for p in ["A", "B", "C", "D"] if p != answer_pos][:3]
                
                if answer_pos == "A":
                    choices = [{"key": "A", "text": en_word}]
                    for j, pos in enumerate(other_chars):
                        if j < len(wrons_text):
                            choices.append({"key": pos, "text": wrongs_text[j]})
                else:
                    choices = []
                    for j, pos in enumerate(["A", "B", "C", "D"]):
                        if pos == answer_pos:
                            choices.append({"key": pos, "text": en_word})
                        else:
                            idx = j - 1 if j < answer_pos else j
                            if idx < len(wrons_text):
                                choices.append({"key": pos, "text": wrongs_text[idx]})
                            else:
                                choices.append({"key": pos, "text": random.choice(["apple", "book", "school"])})
                
                # 生成 id
                qid = f"{tid}_q{existing + len(generated) + 1}"
                counter = 0
                while f"{tid}_q{existing + len(generated) + 1 + counter}" in used_ids:
                    counter += 1
                qid = f"{tid}_q{existing + len(generated) + 1 + counter}"
                
                q = {
                    "id": qid,
                    "topicId": tid,
                    "type": "choice",
                    "prompt": f"哪个单词的中文意思是「{cn_meaning}」？",
                    "answer": answer_pos,
                    "choices": [c for c in choices if "text" in c],
                    "explanation": f"{en_word} 的意思是 {cn_meaning}。",
                    "verify": f"'{en_word}'",
                    "source": "llm",
                }
                generated.append(q)
                used_ids.add(qid)
                
                # 生成 short 题
                qid2 = f"{tid}_q{len(generated) + 1}"
                counter2 = 0
                while f"{tid}_q{len(generated) + 1 + counter2}" in used_ids:
                    counter2 += 1
                qid2 = f"{tid}_q{len(generated) + 1 + counter2}"
                
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
        basic_n = int(len(generated) * TARGET_RATIOS["basic"])
        standard_n = int(len(generated) * TARGET_RATIOS["standard"])
        
        for i, q in enumerate(generated):
            if i < basic_n:
                q["difficulty"] = "basic"
            elif i < basic_n + standard_n:
                q["difficulty"] = "standard"
            else:
                q["difficulty"] = "challenge"
        
        new_questions.extend(generated)
        print(f"  {tid}: 生成 {len(generated)} 题")
    
    # 合并题目
    all_questions = questions + new_questions
    
    # 保存
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=1)
    
    print(f"\n总计: 现有 {len(questions)} 题 + 新生成 {len(new_questions)} 题 = {len(all_questions)} 题")


if __name__ == "__main__":
    main()