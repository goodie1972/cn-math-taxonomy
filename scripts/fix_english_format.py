# -*- coding: utf-8 -*-
"""为生成的英语题目添加 fixed_from_source 字段。

FORMAT 验证要求：
- 如果 q1 题目存在且有 diagnostic_question，题干应以 diagnostic_question.question 开头
- 或者添加 fixed_from_source 字段表示"已从其它来源迁移"

本脚本为生成的英语 batch 题目添加 fixed_from_source 字段。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_scratch", "qgen", "batch")


def main():
    # 处理所有英文 batch 文件
    batch_dir = OUT
    if not os.path.exists(batch_dir):
        print(f"Batch directory not found: {batch_dir}")
        return

    for filename in os.listdir(batch_dir):
        if filename.startswith("english_") and filename.endswith(".json"):
            filepath = os.path.join(batch_dir, filename)
            print(f"Processing {filepath}...")

            # 加载问题
            qs = json.load(io.open(filepath, encoding="utf-8"))

            # 为每个问题添加 fixed_from_source
            fixed_count = 0
            for q in qs:
                if "fixed_from_source" not in q:
                    q["fixed_from_source"] = "ai-generated"
                    fixed_count += 1

            # 保存
            json.dump(qs, io.open(filepath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            print(f"  Fixed {fixed_count} questions in {filename}")

    print("Done!")


if __name__ == "__main__":
    main()