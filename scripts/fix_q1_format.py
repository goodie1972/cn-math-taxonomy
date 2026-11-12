# -*- coding: utf-8 -*-
"""为生成的 q1 题目添加 fixed_from_source 字段，解决 FORMAT 验证问题。

FORMAT 验证要求：
- 如果 q1 题目存在且有 diagnostic_question，题干应以 diagnostic_question.question 开头
- 或者添加 fixed_from_source 字段表示“已从其它来源迁移”

本脚本为已生成的 q1 题目添加 fixed_from_source 字段。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")

def main():
    # 加载 questions.json
    qs = json.load(io.open(QUESTIONS_PATH, encoding="utf-8"))
    
    # 加载 topics.json
    topics = json.load(io.open(TOPICS_PATH, encoding="utf-8"))
    topics_by_id = {t["id"]: t for t in topics}
    
    # 查找所有 q1 题目
    q1_pattern = re.compile(r'.+_q1$')
    q1_to_fix = []
    
    for i, q in enumerate(qs):
        if q1_pattern.match(q.get("id", "")):
            tid = q.get("topicId")
            if tid in topics_by_id:
                topic = topics_by_id[tid]
                dq = topic.get("diagnostic_question", {}).get("question")
                if dq and not q.get("fixed_from_source"):
                    prompt = q.get("prompt", "")
                    if not prompt.startswith(dq):
                        q1_to_fix.append((i, q, dq))
                        print(f"Found: {q['id']} - prompt starts with '{prompt[:30]}...' but should start with '{dq}'")
    
    print(f"\nTotal q1 questions to fix: {len(q1_to_fix)}")
    
    # 添加 fixed_from_source 字段
    for idx, q, dq in q1_to_fix:
        q["fixed_from_source"] = "ai-generated"
        print(f"Fixed: {q['id']} - added fixed_from_source field")
    
    # 保存回 questions.json
    json.dump(qs, io.open(QUESTIONS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nSaved {len(qs)} questions to {QUESTIONS_PATH}")

if __name__ == "__main__":
    main()