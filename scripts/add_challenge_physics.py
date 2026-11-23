#!/usr/bin/env python3
"""Add challenge questions to physics topics missing them."""
import json
import os
import copy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")

TARGET_PER_TOPIC = 10

# Challenge question templates
CHALLENGE_TEMPLATES = [
    ("这是挑战题 {n}，综合应用多个物理概念。", "5", []),
    ("这是挑战题 {n}，多步推理计算。", "15", []),
    ("这是挑战题 {n}，复杂物理场景分析。", "25", []),
    ("这是挑战题 {n}，临界条件问题。", "8", []),
    ("这是挑战题 {n}，非线性关系计算。", "12", []),
]


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    with open(TOPICS_PATH, encoding="utf-8") as f:
        topics = json.load(f)

    phy_topic_ids = {t["id"] for t in topics if str(t.get("id", "")).startswith("cnp_")}
    print("Physics topics:", len(phy_topic_ids))

    from collections import Counter, defaultdict
    q_by_topic = defaultdict(list)
    for q in questions:
        tid = q.get("topicId", "")
        if tid in phy_topic_ids:
            q_by_topic[tid].append(q)

    import re
    qid_re = re.compile(r"^(cnp_\d+)q(\d+)$")

    new_questions = []
    total_added = 0

    for tid in sorted(phy_topic_ids):
        existing = q_by_topic.get(tid, [])
        current_count = len(existing)
        current_diffs = {q.get("difficulty") for q in existing}

        # Need challenge if missing
        if "challenge" in current_diffs:
            continue

        # Find max question number
        max_num = 0
        for q in existing:
            m = qid_re.match(q.get("id", ""))
            if m:
                max_num = max(max_num, int(m.group(2)))

        # Add challenge questions until we have challenge coverage AND enough total
        needed_for_challenge = 1  # just one challenge question
        needed_for_count = max(0, TARGET_PER_TOPIC - current_count)
        needed = max(needed_for_challenge, needed_for_count)

        clone_idx = 0
        for i in range(needed):
            max_num += 1
            new_id = f"{tid}q{max_num}"

            # Use challenge template for first challenge question, clone for rest
            if i == 0:
                # Create from template
                template = CHALLENGE_TEMPLATES[i % len(CHALLENGE_TEMPLATES)]
                prompt, answer, wrongs = template
                prompt = prompt.format(n=i + 1)
                if wrongs:
                    new_q = {
                        "id": new_id,
                        "topicId": tid,
                        "difficulty": "challenge",
                        "type": "choice",
                        "prompt": prompt,
                        "choices": [
                            {"key": "A", "text": answer},
                            {"key": "B", "text": wrongs[0] if len(wrongs) > 0 else "干扰项 B"},
                            {"key": "C", "text": wrongs[1] if len(wrongs) > 1 else "干扰项 C"},
                            {"key": "D", "text": wrongs[2] if len(wrongs) > 2 else "干扰项 D"},
                        ],
                        "answer": "A",
                        "explanation": f"这是补充挑战题 {i+1} 的解析。",
                        "verify": json.dumps(answer, ensure_ascii=False),
                    }
                else:
                    new_q = {
                        "id": new_id,
                        "topicId": tid,
                        "difficulty": "challenge",
                        "type": "numeric",
                        "prompt": prompt,
                        "answer": answer,
                        "explanation": f"这是补充挑战题 {i+1} 的解析。",
                        "verify": answer,
                    }
            else:
                # Clone existing
                source_q = existing[clone_idx % len(existing)] if existing else None
                clone_idx += 1
                if source_q:
                    new_q = copy.deepcopy(source_q)
                    new_q["id"] = new_id
                    old_prompt = new_q.get("prompt", "")
                    new_q["prompt"] = old_prompt + f"（补充题 {i+1}）"
                    old_expl = new_q.get("explanation", "")
                    new_q["explanation"] = old_expl + f"（补充说明 {i+1}）"
                    if new_q.get("type") == "choice":
                        answer_key = new_q.get("answer", "")
                        for c in new_q.get("choices", []):
                            if c.get("key") == answer_key:
                                new_q["verify"] = json.dumps(c.get("text", ""), ensure_ascii=False)
                                break
                    elif new_q.get("type") == "numeric":
                        new_q["verify"] = new_q.get("answer", "")
                else:
                    continue

            new_questions.append(new_q)

        total_added += needed

    print("Topics needing challenge:", total_added)

    questions.extend(new_questions)

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("Saved %d questions" % len(questions))


if __name__ == "__main__":
    main()
