# -*- coding: utf-8 -*-
"""
合并 batch 文件到 data/questions.json

将所有 batch 文件中的题目合并到 questions.json 中。
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
    if os.path.exists(QUESTIONS_PATH):
        existing = json.load(io.open(QUESTIONS_PATH, encoding='utf-8'))
        print(f"Loaded existing questions.json: {len(existing)} questions")
    else:
        existing = []
        print("No existing questions.json found, starting fresh")

    # 遍历 batch 目录
    all_new_questions = []
    batch_dir = OUT

    for filename in sorted(os.listdir(batch_dir)):
        if filename.endswith(".json") and not filename.startswith("manifest"):
            filepath = os.path.join(batch_dir, filename)
            print(f"Processing {filename}...")

            with io.open(filepath, 'r', encoding='utf-8') as f:
                questions = json.load(f)

            # 为每个问题生成唯一 ID 并添加必要字段
            for q in questions:
                tid = q.get('topicId', 'unknown')

                # 生成 ID (如果没有的话)
                if 'id' not in q or not q['id']:
                    qtype = q.get('type', 'unknown')
                    # 统计同一 topicId 的同类型题目数量
                    existing_q = [x for x in existing + all_new_questions
                                  if x.get('topicId') == tid and x.get('type') == qtype]
                    seq = len(existing_q) + 1
                    if qtype == 'choice':
                        q['id'] = f"{tid}_q{seq}"
                    else:
                        q['id'] = f"{tid}_{qtype}_{seq}"
                else:
                    # 如果已有 ID，更新 topicId
                    q['topicId'] = tid

                # 添加 subject 字段（从 topicId 前缀推断）
                if 'subject' not in q or not q.get('subject'):
                    if tid.startswith('cne_') or tid.startswith('cnc_') or tid.startswith('cng_') or tid.startswith('cnj_') or tid.startswith('cnh_') or tid.startswith('cn_h'):
                        q['subject'] = 'english'
                    else:
                        q['subject'] = 'english'  # 我们生成的都是英语

                all_new_questions.append(q)

    print(f"\nTotal new questions from batch files: {len(all_new_questions)}")

    # 合并
    merged = existing + all_new_questions
    print(f"Total questions after merge: {len(merged)}")

    # 保存 (使用较大的缓冲区)
    with io.open(QUESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(merged)} questions to {QUESTIONS_PATH}")


if __name__ == "__main__":
    main()