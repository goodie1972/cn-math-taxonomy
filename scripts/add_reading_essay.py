#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add more reading and essay questions to English topics.

This script generates:
- Reading comprehension questions (type: reading)
- Essay/creative writing questions (type: essay)

Usage: python3 scripts/add_reading_essay.py
"""
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reading passage templates
PASSAGES = {
    "animals": [
        "Tommy the tiger was very hungry. He walked through the jungle looking for food. Suddenly, he saw a big herd of deer. The deer ran away, but Tommy was too slow. He only caught a small mouse.",
        "At the zoo, visitors love to watch the playful otters. Otters hold hands while they sleep so they don't drift apart. In the water, they can use their powerful tails to swim fast.",
        "The clever fox knew when to be quiet. While other animals were loud, the fox crept softly through the forest. She found a berry bush and filled her belly without being seen.",
    ],
    "friends": [
        "Maya and Leo have been friends since they were little. They share secrets and play together every day. When Maya fell down, Leo helped her up with a smile.",
        "A good friend listens. When Sam was sad about his pet goldfish, his friend Anna brought him a flower. 'It's not the same,' Sam said, 'but it's a nice memory now.'",
        "The best gifts are not wrapped in paper. When Tom found out his friend had helped his family during the storm, he gave Tom the biggest hug he could.",
    ],
    "school": [
        "The morning bell rang, and students rushed to their classrooms. In Mrs. Smith's class, they were learning about the solar system. Outside, the playground echoed with laughter and shouts of 'Tag!'",
        "During show-and-tell, Emma held up a beautiful seashell. 'I found this on my vacation in Hawaii,' she said. The class imagined the waves of the Pacific Ocean.",
        "The science fair was the most exciting day of the month. Students had built volcanoes, painted dioramas, and made models of the human heart. Judges walked from one display to the next.",
    ],
    "weather": [
        "The sun peeked out from behind the clouds. After a week of rain, everyone felt happy to see the warm rays. Sarah ran outside without her umbrella.",
        "Thunder rumbled in the distance as Lily opened her umbrella. The rain fell in silver sheets. Inside, she warmed her hands with a mug of hot chocolate.",
        "Snowflakes danced down from the sky. The world turned white and quiet. Tim threw snowballs with his brother, building the perfect snowman together.",
    ],
    "family": [
        "At dinner, the whole family shared their day's adventures. Little Mei told a long story about her drawing, while her brother showed his new soccer goal.",
        "Grandpa's kitchen smelled of ginger and pork. He taught his granddaughter how to roll dumpling dough. 'Like this,' he said, demonstrating the gentle pinch.",
        "Sunday morning meant pancakes in bed. Mom served maple syrup, and everyone laughed as Dad tried to flip his pancake too high.",
    ],
}

# Reading comprehension question templates
READING_QUESTIONS = {
    "what_happened": [
        "根据短文，发生了什么事？",
        "接下来会发生什么？用短文判断答：",
        "短文中描述了哪些事件？",
    ],
    "who": [
        "短文里谁在说话？",
        "谁帮助了谁？",
        "介绍一下短文里的人物。",
    ],
    "where": [
        "故事发生在哪里？",
        "在哪里可以看到这些？",
        "描述一下短文中的场所。",
    ],
    "why": [
        "为什么会这样？",
        "他/她这样做的原因是什么？",
        "请解释短文中的一个原因。",
    ],
    "detail": [
        "短文中提到了哪些细节？",
        "说说最有趣的一个细节。",
        "找出短文中提到的数字。",
    ],
}

# Essay prompts
ESSAY_PROMPTS = {
    "describe": [
        "描述一个你最喜欢的节日。",
        "描述你家里的一天。",
        "描述你第一次去的地方。",
    ],
    "compare": [
        "比较春天和秋天，你最喜欢哪一季？为什么？",
        "比较两种食物，你喜欢哪一种？",
        "比较两种活动，你更喜欢哪一种？",
    ],
    "opinion": [
        "你觉得应该如何帮助困难的人？",
        "如果可以带一种动物回家，你会带哪一种？为什么？",
        "你认为学校应该有哪些活动？",
    ],
    "narrative": [
        "讲讲你最近一次旅游的经历。",
        "讲讲你最开心的一天。",
        "讲讲你第一次学会的一件事。",
    ],
}


def get_next_q_id(questions, topic_id, used_ids):
    """Get the next available question ID for a topic."""
    base = f"{topic_id}_q"
    n = 1
    while base + str(n) in used_ids:
        n += 1
    return base + str(n)


def generate_reading_question(topic_id, passage, prompt_type, difficulty, used_ids):
    """Generate a reading comprehension question."""
    prompt_text = random.choice(READING_QUESTIONS.get(prompt_type, ["请仔细阅读短文并回答。"]))

    prompt = f"阅读短文并回答：{prompt_text}\n\n{passage}"

    qid = get_next_q_id([], topic_id, used_ids)

    question = {
        "id": qid,
        "topicId": topic_id,
        "difficulty": difficulty,
        "type": "reading",
        "prompt": prompt,
        "answer": "根据短文内容回答",
        "verify": f"'{prompt_text}'",
        "explanation": "请仔细阅读短文内容，根据线索作答。",
        "source": "bulk_reading_gen",
    }
    used_ids.add(qid)
    return question


def generate_essay_question(topic_id, prompt_type, difficulty, used_ids):
    """Generate an essay/creative writing question."""
    prompt_text = random.choice(ESSAY_PROMPTS.get(prompt_type, ["写一篇关于日常生活的短文。"]))

    full_prompt = f"书面表达题：\n{prompt_text}"

    qid = get_next_q_id([], topic_id, used_ids)

    question = {
        "id": qid,
        "topicId": topic_id,
        "difficulty": difficulty,
        "type": "essay",
        "prompt": full_prompt,
        "answer": f"写一篇关于{prompt_text.replace('。', '')}的短文",
        "verify": f"'essay:{prompt_type}'",
        "explanation": "根据题目要求写一篇短文，表达自己的想法。",
        "source": "bulk_essay_gen",
        "word_limit": "60-100词",
    }
    used_ids.add(qid)
    return question


def main():
    with open(os.path.join(ROOT, "data", "topics.json"), encoding="utf-8") as f:
        topics = json.load(f)

    with open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8") as f:
        questions = json.load(f)

    # Get all English topics
    eng_topics = [t for t in topics if t.get("subject") == "english" and not t.get("external")]
    print(f"Found {len(eng_topics)} English topics")

    # Build set of used IDs
    used_ids = set(q.get("id") for q in questions)

    # Count current reading and essay questions for English
    current_reading = len([q for q in questions if q.get("type") == "reading" and q.get("topicId", "").startswith("cne_")])
    current_essay = len([q for q in questions if q.get("type") == "essay" and q.get("topicId", "").startswith("cne_")])
    eng_count = len([q for q in questions if q.get("topicId", "").startswith("cne_")])

    # Target: reading >= 10%, essay >= 5% of English questions
    target_reading = int(eng_count * 0.10)
    target_essay = int(eng_count * 0.05)

    reading_to_generate = max(0, target_reading - current_reading)
    essay_to_generate = max(0, target_essay - current_essay)

    print(f"Current reading: {current_reading}, essay: {current_essay}, total English: {eng_count}")
    print(f"Target reading: {target_reading}, essay: {target_essay}")
    print(f"Need to generate: {reading_to_generate} reading, {essay_to_generate} essay")

    new_questions = []

    # Generate reading comprehension questions
    reading_types = list(READING_QUESTIONS.keys())
    for i in range(reading_to_generate):
        topic = random.choice(eng_topics)
        tid = topic["id"]

        # Distribute difficulty: ~50% basic, ~50% standard
        difficulty = "basic" if random.random() < 0.5 else "standard"

        passage = random.choice(random.choice(list(PASSAGES.values())))
        q = generate_reading_question(
            tid, passage, random.choice(reading_types), difficulty, used_ids
        )
        new_questions.append(q)

    # Generate essay questions
    essay_types = list(ESSAY_PROMPTS.keys())
    for i in range(essay_to_generate):
        topic = random.choice(eng_topics)
        tid = topic["id"]

        # Distribute difficulty: ~30% basic, ~50% standard, ~20% challenge
        r = random.random()
        if r < 0.3:
            difficulty = "basic"
        elif r < 0.8:
            difficulty = "standard"
        else:
            difficulty = "challenge"

        q = generate_essay_question(tid, random.choice(essay_types), difficulty, used_ids)
        new_questions.append(q)

    # Append to existing questions
    questions.extend(new_questions)

    print(f"Generated {len(new_questions)} new questions")
    print(f"  Reading comprehension: {len([q for q in new_questions if q['type'] == 'reading'])}")
    print(f"  Essay: {len([q for q in new_questions if q['type'] == 'essay'])}")

    # Save
    with open(os.path.join(ROOT, "data", "questions.json"), "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Total questions now: {len(questions)}")


if __name__ == "__main__":
    main()