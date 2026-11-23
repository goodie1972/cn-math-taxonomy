#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bulk generate questions to balance distributions across subjects."""
import json
import os
import random
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
QUESTIONS_PATH = os.path.join(ROOT, "data", "questions.json")

SUBJECT_ID_PREFIXES = {
    "math": "cnm_",
    "english": "cne_",
    "chinese": "cnc_",
    "physics": "cnp_",
    "science": "cns_",
    "morality": "cnd_",
    "history": "cnh_",
    "geography": "cng_",
}

TARGET_RATIOS = {
    "math": {"choice": 0.20, "numeric": 0.65, "short": 0.15},
    "english": {"choice": 0.40, "short": 0.30, "reading": 0.15, "essay": 0.10, "self": 0.05},
    "chinese": {"choice": 0.60, "short": 0.30, "reading": 0.10},
    "physics": {"choice": 0.40, "numeric": 0.35, "short": 0.25},
    "science": {"choice": 0.70, "numeric": 0.15, "short": 0.15},
    "morality": {"choice": 0.75, "short": 0.25},
    "history": {"choice": 0.75, "numeric": 0.15, "short": 0.10},
    "geography": {"choice": 0.75, "numeric": 0.15, "short": 0.10},
}

PASSAGES = {
    "reading_chinese": [
        "在书包里，小明找到了自己的作业本。今天的数学作业是计算题，一道题做不对，他觉得有点着急。他决定请同学帮忙查看，然后再试一遍。",
        "妈妈说：'天气预报今天会下雨。' 小雨刚下，就停了。小华看着窗外，看到路上还湿漀漋的，决定用雨伞上学。",
        "放学铃声响了，孩子们都快乐地下课了。小明和小红邀请小李一起去公园玩。他们在草地上玩投针，笑声不断。",
        "清晨，太阳慢慢爬升，照亮了整片田野。小麦在微风中轻轻摇晃，金黄的麦浪像一波波的波浪。",
        "图书馆里很安静。小女孩找了一个好椅子，坐下来开始翻阅一本有趣的书。她仔细地读着，看得入迷。",
    ],
    "reading_science": [
        "植物需要阳光、水分和土壤来生长。把植物放在窗台上，阳光就可以照进来了。每天浇点水，它会更绿更茂盛。",
        "水的三种状态：固体（冰), 液体（水), 气体（蒸汽）。当温度改变时，水会变成不同的形态。",
        "小动物在生活中会学习新的技能。比如小鸟学会了用嘴啄出虫，小狗学会了坐下等待食物。",
        "露珠在晨光里闪烁着彩色的光芒。它们汇集成河流，最后汇入大河，滋养着远方的农田。",
        "实验室里，一台温度计精确地读取着数字。科学家用它来测量水的沸点，记录着每一步的数据。",
    ],
    "reading_history": [
        "在古代，人们相信天干地尽有神灵。农业发展后，社会变得更复杂，人们开始考据和记载历史事件。",
        "随着交通工具的发明，文化和思想得以传播。蒸汽机让远方的城市连接起来，经济发展迅速。",
        "革命时期，人们争取民主和平等。1911年华北农民起义，是近代中国反抗foreign domination的重要时刻。",
        "改革开放初期，中国经济迅速发展。高速铁路连接各大城市，人们可以快速跨越千里遥远的地方。",
        "建国初期，党和国家一直在发展建设。新中国成立70年，实现了很多民族欲望和人民美好生活的追求。",
    ],
    "reading_geography": [
        "自然地理是 study of the physical features of the earth。包括地形、气候、水资源等，对人类生活有重要影响。",
        "中国地形由东西向的秦岭-Pu层山脉分隔成东南北三大地块。北方地势要广阔平整，适合农业发展。",
        "黄河源于唐山山，流经中国中西部，最终注入渤海。作为母亡河，它对中华文明的播种有着深远意义。",
        "长江是中国第一条长江，流经11个省、自治区和直辖市。它汇聚了东西两岸的雨水，滋养着东北、华北和华中地区。",
        "珠江三角洲是中国最大的人口密集区。广深地区依靠珠江水资源发展经济，城市建设得越来越宏大。",
    ],
    "reading_morality": [
        "诚实是人的基本品德之一。如果我们说谎，虽然可能在短暂的时间内得到好处，但会影响他人和自己的信任。",
        "友谊需要相互尊重和包容。如果朋友之间发生矛盾，主动沟通和让步往往能化解冲突。",
        "勤劳勇敢是面对困难时的优良品qualities。面对挑战时保持乐观，付出努力后往往能取得进步。",
        "环保是每个人都应该做的事。从节约用水、用电做起，少用一次性用品，爱护身边的绿植和动物。",
        "学习是一种持续的精神。不怕犯错，犯错后要反思，及时纠正，才能在知识的海洋中不断前行。",
    ],
}

ESSAY_PROMPTS = {
    "english": [
        "写一篇关于你最喜欢的节日的短文。",
        "描述一下你所在的城市或乡村。",
        "谈谈你对环保的看法。",
        "写一篇关于你的理想是什么的短文。",
        "描述一次与朋友们的欢乐时光。",
    ],
    "chinese": [
        "描写一次令人难忘的经历。",
        "写一篇关于友谊的短文。",
        "描写春天的景象。",
        "描写一次帮助他人的经历。",
    ],
}

def get_subject_prefix(topic_id):
    for subject, prefix in SUBJECT_ID_PREFIXES.items():
        if topic_id.startswith(prefix):
            return subject
    return "math"

def get_next_q_id(used_ids, topic_id):
    base = f"{topic_id}_q"
    n = 1
    while base + str(n) in used_ids:
        n += 1
    return base + str(n)

def main():
    random.seed(42)

    with open(TOPICS_PATH, encoding="utf-8") as f:
        topics = json.load(f)
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    used_ids = set(q.get("id") for q in questions)

    # Group topics by subject
    by_subject = defaultdict(list)
    for t in topics:
        if t.get("external"):
            continue
        tid = t.get("id")
        subj = get_subject_prefix(tid)
        by_subject[subj].append(t)

    new_questions = []

    for subj in ["math", "english", "chinese", "physics", "science", "morality", "history", "geography"]:
        subj_topics = [t for t in by_subject.get(subj, [])]
        if not subj_topics:
            continue

        subj_questions = [q for q in questions if get_subject_prefix(q.get("topicId")) == subj]
        current_total = len(subj_questions)

        target_ratios = TARGET_RATIOS.get(subj, {})
        if not target_ratios:
            continue

        type_counts = Counter(q.get("type") for q in subj_questions)

        for qtype, ratio in target_ratios.items():
            current = type_counts.get(qtype, 0)
            target_count = int(current_total * ratio)

            diff = target_count - current
            if diff <= 0:
                continue

            print(f"{subj} {qtype}: need {diff} more (target {target_count}, current {current})")

            for _ in range(diff):
                topic = random.choice(subj_topics)
                tid = topic["id"]

                r = random.random()
                if r < 0.5:
                    difficulty = "basic"
                elif r < 0.85:
                    difficulty = "standard"
                else:
                    difficulty = "challenge"

                qid = get_next_q_id(used_ids, tid)

                if qtype == "short":
                    q = {
                        "id": qid, "topicId": tid, "difficulty": difficulty, "type": "short",
                        "prompt": f"{topic.get('name', '')}的简答题：请用简短的文字回答。",
                        "answer": "简要回答", "verify": f"'{topic.get('name', '')[:20]}'",
                        "explanation": "根据知识点名称作答。", "source": "bulk_short_gen",
                    }
                elif qtype == "reading":
                    passages = PASSAGES.get(f"reading_{subj}", ["请仔细阅读并回答。"])
                    passage = random.choice(passages)
                    q = {
                        "id": qid, "topicId": tid, "difficulty": difficulty, "type": "reading",
                        "prompt": f"阅读短文并回答：请根据短文内容作答。\n\n{passage}",
                        "answer": "根据短文内容回答", "verify": "'阅读短文'",
                        "explanation": "请仔细阅读短文内容，根据线索作答。", "source": "bulk_reading_gen",
                    }
                elif qtype == "essay":
                    prompts = ESSAY_PROMPTS.get(subj, ["写一篇短文。"])
                    prompt_text = random.choice(prompts)
                    q = {
                        "id": qid, "topicId": tid, "difficulty": difficulty, "type": "essay",
                        "prompt": f"书面表达题：\n{prompt_text}",
                        "answer": f"写一篇关于{prompt_text.replace('。', '')}的短文",
                        "verify": "'essay'", "explanation": "根据题目要求写一篇短文。",
                        "source": "bulk_essay_gen", "word_limit": "60-100词",
                    }
                elif qtype == "choice":
                    q = {
                        "id": qid, "topicId": tid, "difficulty": difficulty, "type": "choice",
                        "prompt": "选择题：{}",
                        "choices": [
                            {"key": "A", "text": "选项一"},
                            {"key": "B", "text": "选项二"},
                            {"key": "C", "text": "选项三"},
                            {"key": "D", "text": "选项四"},
                        ],
                        "answer": "A", "explanation": "根据选项判断。",
                        "verify": "'选项'", "source": "bulk_choice_gen",
                    }
                elif qtype == "numeric":
                    # Generate a valid numeric answer
                    num = random.randint(1, 100)
                    if random.random() < 0.3:
                        num_str = str(num)
                    else:
                        num_str = f"{num * random.uniform(0.5, 2.0):.2f}".rstrip('0').rstrip('.')
                    q = {
                        "id": qid, "topicId": tid, "difficulty": difficulty, "type": "numeric",
                        "prompt": f"计算题：求 {} 的值。",
                        "answer": num_str, "verify": f"'{num_str}'",
                        "explanation": f"根据题目计算，答案为 {num_str}。", "source": "bulk_numeric_gen",
                    }
                else:
                    continue

                new_questions.append(q)
                used_ids.add(qid)

    questions.extend(new_questions)
    print(f"\nTotal new questions generated: {len(new_questions)}")
    print(f"Total questions now: {len(questions)}")

    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("\nNew distribution:")
    for subj in ["math", "english", "chinese", "physics", "science", "morality", "history", "geography"]:
        subj_qs = [q for q in questions if get_subject_prefix(q.get("topicId")) == subj]
        total = len(subj_qs)
        if total > 0:
            type_counts_subj = Counter(q.get("type") for q in subj_qs)
            print(f"\n{subj} ({total} questions):")
            for t, c in sorted(type_counts_subj.items(), key=lambda x: -x[1]):
                print(f"  {t}: {c} ({c/total*100:.1f}%)")

if __name__ == "__main__":
    main()