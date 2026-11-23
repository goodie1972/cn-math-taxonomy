#!/usr/bin/env python3
"""为所有英语知识点生成题目。

此脚本从 en_g3.py 等模块导入知识点定义，
然后为每个知识点生成题目。
"""
import json
import os
import sys
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# 先导入 en_lib 初始化 TOPICS 列表
import en_lib
from en_lib import TOPICS, HARD

# 导入年级知识点
import en_g3  # noqa: F401
import en_g4  # noqa: F401
import en_g5  # noqa: F401
import en_g6  # noqa: F401

# 导入知识点定义（这会触发 TOPICS 的填充）
import en_topics  # noqa: F401

# 再导入 en_lib 获取填充后的 TOPICS
import importlib
importlib.reload(en_lib)
from en_lib import TOPICS as FILLED_TOPICS

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


def generate_vocab_questions(spec, tid, used_ids, start_n):
    """生成单词题"""
    words = spec.get("words", [])
    if not words or len(words) < 4:
        return [], start_n
    
    generated = []
    n = start_n
    for i in range(min(20, len(words))):  # 最多20组
        en_word, cn_meaning = words[i]
        if not en_word or not cn_meaning:
            continue
        
        # 生成 choice 题
        other_words = [(w, c) for j, (w, c) in enumerate(words) if j != i][:3]
        wrongs = [c for w, c in other_words]
        if len(wrons) < 2:
            continue
        
        answer_pos = random.choice(["A", "B", "C", "D"])
        choices = []
        all_chars = ["A", "B", "C", "D"]
        other_chars = [c for c in all_chars if c != answer_pos]
        
        if answer_pos == "A":
            choices = [{"key": "A", "text": en_word}]
            for j, pos in enumerate(other_chars[:3]):
                if j < len(wrons):
                    choices.append({"key": pos, "text": wrongs[j]})
        else:
            choices = []
            for pos in all_chars:
                if pos == answer_pos:
                    choices.append({"key": pos, "text": en_word})
                elif len(choices) < 4:
                    choices.append({"key": pos, "text": wrongs[len(choices)] if len(choices) < len(wrons) else random.choice(["apple", "book", "school"])})
        
        # 清理选项，确保4个
        choices = [c for c in choices if "text" in c][:4]
        while len(choices) < 4:
            choices.append({"key": ["A", "B", "C", "D"][len(choices)], "text": random.choice(["apple", "book", "school", "water"])})
        
        # 生成 id
        qid = f"{tid}_q{n}"
        counter = 0
        while qid in used_ids:
            n += 1
            counter += 1
            qid = f"{tid}_q{n}"
        if counter > 100:
            n = start_n + counter + 1000
            qid = f"{tid}_q{n}"
        
        q = {
            "id": qid,
            "topicId": tid,
            "type": "choice",
            "prompt": f"哪个单词的中文意思是「{cn_meaning}」？",
            "answer": answer_pos,
            "choices": choices,
            "explanation": f"{en_word} 的意思是 {cn_meaning}。",
            "verify": f"'{en_word}'",
            "source": "llm",
        }
        generated.append(q)
        used_ids.add(qid)
        n += 1    
    return generated, n


def generate_all_english():
    """为所有英语知识点生成题目"""
    topics_data = load_topics()
    questions = load_questions()
    used_ids = get_used_ids(questions)
    
    # 构建 topicId -> topic 的映射
    topics_by_id = {t["id"]: t for t in topics_data}
    
    # 从 FILLED_TOPICS 获取所有小学和初中英语知识点
    all_english_specs = [t for t in FILLED_TOPICS if t.get("grade", 0) <= 9 and t.get("subject") == "english"]
    
    print(f"找到 {len(all_english_specs)} 个英语知识点")
    
    new_questions = []
    stats = {
        'basic': 0,
        'standard': 0,
        'challenge': 0
    }
    
    for spec in all_english_specs:
        if len(new_questions) > 50000:  # 目标足够
            break
            
        key = spec.get("key", "")
        name = spec.get("name", "")
        grade = spec.get("grade", 3)
        sem = spec.get("semester", "上")
        unit = spec.get("unit", 1)
        domain = spec.get("domain", "")
        
        # 生成 topicId
        # 从 en_topics.py 看，cne_p 开头的是小学，cne_j 开头的是初中
        if str(grade).isdigit() and int(grade) <= 6:
            # 小学英语
            topic_id = f"cne_p{len([q for q in new_questions if q.get('topicId', '').startswith('cne_p')]) + 1:03d}"
        else:
            # 初中英语
            topic_id = f"cne_j{len([q for q in new_questions if q.get('topicId', '').startswith('cne_j')]) + 1:03d}"
        
        # 查找是否已有此知识点
        existing_tid = None
        for tid, t in topics_by_id.items():
            if t.get("subject") == "english" and t.get("grade") == grade:
                if t.get("name", "").startswith(name[:3]):
                    existing_tid = tid
                    break
        
        if not existing_tid:
            continue
            
        tid = existing_tid
        
        # 检查是否已有足够题目
        existing = [q for q in questions if q.get("topicId") == tid]
        if len(existing) >= 30:
            continue
        
        # 根据知识点类型生成题目
        gen = spec.get("gen")
        generated = []
        
        # 简单的填充：根据type生成不同类型的题目
        qtype = spec.get("type", "conceptual")
        
        if qtype == "conceptual":
            # 词汇题
            if spec.get("words"):
                words = spec["words"][:12]  # 最多12组
                for en_word, cn_meaning in words:
                    # choice 题
                    other = [(w, c) for w, c in spec.get("words", []) if w != en_word][:3]
                    wrongs = [c for w, c in other]
                    
                    if len(wrons) < 2:
                        continue
                    
                    answer_pos = random.choice(["A", "B", "C", "D"])
                    choices = []
                    for i, pos in enumerate(["A", "B", "C", "D"]):
                        if pos == answer_pos:
                            choices.append({"key": pos, "text": en_word})
                        else:
                            choices.append({"key": pos, "text": wrongs[min(i, len(wrons)-1)]})
                    
                    qid = f"{tid}_q{len(existing) + len(generated) + 1}"
                    while qid in used_ids:
                        qid = qid.replace("_q", "_q0")
                        qid = qid[:-1] + str(int(qid.split("_q")[-1]) + 1)
                    
                    q = {
                        "id": qid,
                        "topicId": tid,
                        "type": "choice",
                        "prompt": f"哪个单词的中文意思是「{cn_meaning}」？",
                        "answer": answer_pos,
                        "choices": choices,
                        "explanation": f"{en_word} 的意思是 {cn_meaning}。",
                        "verify": f"'{en_word}'",
                        "source": "llm",
                    }
                    generated.append(q)
                    used_ids.add(qid)
        
        # 分配难度
        basic_n = int(len(generated) * TARGET_RATIOS["basic"])
        standard_n = int(len(generated) * TARGET_RATIOS["standard"])
        
        for i, q in enumerate(generated):
            if i < basic_n:
                q["difficulty"] = "basic"
                stats["basic"] += 1
            elif i < basic_n + standard_n:
                q["difficulty"] = "standard"
                stats["standard"] += 1
            else:
                q["difficulty"] = "challenge"
                stats["challenge"] += 1
        
        new_questions.extend(generated)
        
        if len(new_questions) % 100 == 0:
            print(f"  已生成 {len(new_questions)} 题...")
    
    # 合并题目
    all_questions = questions + new_questions
    
    print(f"\n生成统计:")
    print(f"  new questions: {len(new_questions)}")
    print(f"  by difficulty: {stats}")
    print(f"  total: {len(all_questions)}")
    
    # 保存
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=1)
    
    # 同步到主文件
    with open(QUESTIONS_PATH.replace('/main/', '/'), "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=1)
    
    print(f"已保存到 {QUESTIONS_PATH}")


if __name__ == "__main__":
    generate_all_english()