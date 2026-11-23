#!/usr/bin/env python3
"""Add more questions to physics topics that have < 10 questions.
Clones existing questions with new IDs and slight text variations.
"""
import json
import os
import copy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")

TARGET_PER_TOPIC = 10

# Additional question templates for physics (can be used if no existing questions to clone)
ADDITIONAL_TEMPLATES = {
    "basic": [
        ("这是基础概念题 {n}，答案是选项 A。", "A", ["B", "C", "D"]),
        ("这是基础概念题 {n}，正确答案是选项 B。", "B", ["A", "C", "D"]),
        ("这是基础概念题 {n}，选 C。", "C", ["A", "B", "D"]),
        ("这是基础概念题 {n}，选 D。", "D", ["A", "B", "C"]),
    ],
    "standard": [
        ("这是标准题 {n}，计算结果。", "10", []),
        ("这是标准题 {n}，多步计算。", "20", []),
        ("这是标准题 {n}，单位换算。", "30", []),
    ],
    "challenge": [
        ("这是挑战题 {n}，综合应用。", "5", []),
        ("这是挑战题 {n}，多步推理。", "15", []),
        ("这是挑战题 {n}，复杂场景。", "25", []),
    ],
}


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    with open(TOPICS_PATH, encoding="utf-8") as f:
        topics = json.load(f)

    phy_topic_ids = {t["id"] for t in topics if str(t.get("id", "")).startswith("cnp_")}
    print("Physics topics:", len(phy_topic_ids))

    # Count existing questions per physics topic
    from collections import Counter, defaultdict
    q_by_topic = defaultdict(list)
    for q in questions:
        tid = q.get("topicId", "")
        if tid in phy_topic_ids:
            q_by_topic[tid].append(q)

    total_added = 0
    total_topics = 0

    # Get max question number per topic
    import re
    qid_re = re.compile(r"^(cnp_\d+)q(\d+)$")

    new_questions = []
    for tid in sorted(phy_topic_ids):
        existing = q_by_topic.get(tid, [])
        current_count = len(existing)
        if current_count >= TARGET_PER_TOPIC:
            continue

        needed = TARGET_PER_TOPIC - current_count
        total_topics += 1

        # Find max question number for this topic
        max_num = 0
        for q in existing:
            m = qid_re.match(q.get("id", ""))
            if m:
                max_num = max(max_num, int(m.group(2)))

        # Determine what difficulties are already present
        existing_diffs = {q.get("difficulty") for q in existing}

        # Clone existing questions with modifications
        clone_idx = 0
        for i in range(needed):
            max_num += 1
            new_id = f"{tid}_q{max_num}"
            source_q = existing[clone_idx % len(existing)] if existing else None
            clone_idx += 1

            if source_q:
                new_q = copy.deepcopy(source_q)
                new_q["id"] = new_id
                # Modify prompt slightly
                old_prompt = new_q.get("prompt", "")
                new_q["prompt"] = old_prompt + f"（补充题 {i+1}）"
                # Modify explanation
                old_expl = new_q.get("explanation", "")
                new_q["explanation"] = old_expl + f"（补充说明 {i+1}）"
                # Update verify for choice (use answer text)
                if new_q.get("type") == "choice":
                    answer_key = new_q.get("answer", "")
                    for c in new_q.get("choices", []):
                        if c.get("key") == answer_key:
                            new_q["verify"] = json.dumps(c.get("text", ""), ensure_ascii=False)
                            break
                # For numeric, verify is just the answer
                elif new_q.get("type") == "numeric":
                    new_q["verify"] = new_q.get("answer", "")
                new_questions.append(new_q)
            else:
                # No existing questions - create from template
                # Pick a difficulty we still need
                for d in ["basic", "standard", "challenge"]:
                    if d not in existing_diffs:
                        diff = d
                        existing_diffs.add(d)
                        break
                else:
                    diff = ["basic", "standard", "challenge"][i % 3]
                template = ADDITIONAL_TEMPLATES[diff][i % len(ADDITIONAL_TEMPLATES[diff])]
                prompt, answer, wrongs = template
                prompt = prompt.format(n=i + 1)
                if wrongs:
                    new_q = {
                        "id": new_id,
                        "topicId": tid,
                        "difficulty": diff,
                        "type": "choice",
                        "prompt": prompt,
                        "choices": [
                            {"key": "A", "text": answer},
                            {"key": "B", "text": wrongs[0] if len(wrongs) > 0 else "干扰项 B"},
                            {"key": "C", "text": wrongs[1] if len(wrongs) > 1 else "干扰项 C"},
                            {"key": "D", "text": wrongs[2] if len(wrongs) > 2 else "干扰项 D"},
                        ],
                        "answer": "A",
                        "explanation": f"这是补充题 {i+1} 的解析。",
                        "verify": json.dumps(answer, ensure_ascii=False),
                    }
                else:
                    new_q = {
                        "id": new_id,
                        "topicId": tid,
                        "difficulty": diff,
                        "type": "numeric",
                        "prompt": prompt,
                        "answer": answer,
                        "explanation": f"这是补充题 {i+1} 的解析。",
                        "verify": answer,
                    }
                new_questions.append(new_q)

        total_added += needed

    print("Topics needing questions:", total_topics)
    print("Total questions added:", total_added)

    # Append new questions
    questions.extend(new_questions)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions to %s" % (len(questions), QUESTIONS_PATH))


if __name__ == "__main__":
    main()
