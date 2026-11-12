# -*- coding: utf-8 -*-
"""批量生成数学 challenge 题（choice + numeric）。

口径：
- confirm=5、只派 choice + numeric、10 轮不重样
- 每个知识点 challenge 40 题 (basic 10 / standard 10 / challenge 40)
- 类型：只给 choice 和 numeric，不给 short
- 基于 topics.json 的 description / mastery_criteria 解析核心概念

设计思路：
- 知识点 → 题型模板 → 变量参数 → 批量生成
- 每类知识点设计专属模板
- 通过换数字、换情境产生变体
- 所有题都带 verify 表达式（求值 == answer）

用法：
  PYTHONIOENCODING=utf-8 python scripts/qgen_math_challenge.py --topic cnm_p001
  PYTHONIOENCODING=utf-8 python scripts/qgen_math_challenge.py --batch
"""
import io
import json
import os
import random
import re
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_scratch", "qgen", "batch")
TOPNS_PATH = os.path.join(ROOT, "data", "topics.json")

TARGET = {"basic": 10, "standard": 10, "challenge": 40}


def classify_topic(topic: dict) -> str:
    """根据 description 和 mastery_criteria 分类知识点类型"""
    desc = topic.get('description', '')
    name = topic.get('name', '')
    criteria = topic.get('mastery_criteria', [])
    text = (desc + ' ' + name + ' ' + ' '.join(criteria))

    # 先检查 name 中更关键的词
    if '认识' in name and ('数' in name or '数字' in name or '各数' in name):
        return 'number_recognition'
    if '第几' in text or ('第' in text and '几' in text and ('第几个' in text or '个数' in text)):
        return 'position'
    if '几和第几' in name or ('几' in text and '第几' in criteria):
        return 'position'

    # 再检查 description/criteria
    if '比较' in text or '大小' in text or '谁大谁小' in text or '大于' in text or '小于' in text:
        return 'comparison'
    if '顺序' in text:
        return 'sequence'
    if '分合' in name or '分与合' in name:
        return 'partition'
    if '加' in text and ('加法' in text or '加' not in name[:4] if len(name) >= 4 else True):
        if '加法' in name or ('加' in name and '减' not in name):
            return 'addition'
    if '减' in text and '减法' in name:
        return 'subtraction'
    if '乘' in text or '乘法' in text or '积' in text or '×' in text:
        return 'multiplication'
    if '除' in text or '除法' in text:
        return 'division'
    if '长度' in text or '周长' in text:
        return 'length'
    if '认识' in text and ('数' in text or '数字' in text):
        return 'number_recognition'
    if '分' in name and ('份' in text or '部分' in text or '分合' in text):
        return 'partition'
    return 'general'


def subject_of(t):
    s = t.get("subject")
    if s:
        return s
    return "math" if t["id"].startswith("cnm_") else t["id"].split("_")[0]


def stage(t):
    g = t.get("grade") or 0
    if g >= 10:
        return "senior"
    return "primary" if g <= 6 else "junior"


# ============================================
# 题型模板函数 (每个 difficulty 有不同参数)
# ============================================

def gen_compare_basic(params):
    """比较类 choice 题 (basic)"""
    a = random.randint(1, 15)
    b = random.randint(1, 15)
    # 确保 a != b，避免题目无意义
    while a == b:
        b = random.randint(1, 15)
    larger = max(a, b)
    smaller = min(a, b)
    prompt = "哪个数大？{a} 和 {b} 是哪个数？".format(a=a, b=b)

    # 随机决定把大数放在 A/B/C 中的哪个位置
    answer_pos = random.choice(["A", "B", "C"])

    # 确保所有选项值唯一
    # 生成 4 个唯一的值：correct, other, distractor1, distractor2
    while True:
        distractor1 = larger + random.randint(5, 15)
        distractor2 = smaller + random.randint(5, 15)
        values = [larger, smaller, distractor1, distractor2]
        if len(set(values)) == 4:  # 所有值唯一
            break

    if answer_pos == "A":
        choices = [
            {"key": "A", "text": str(larger)},
            {"key": "B", "text": str(smaller)},
            {"key": "C", "text": str(distractor1)},
            {"key": "D", "text": str(distractor2)},
        ]
        ans_key = "A"
        ans_text = str(larger)
        explanation = "比较两个数的大小，{larger} 更大，所以选 A。".format(larger=larger)
    elif answer_pos == "B":
        choices = [
            {"key": "A", "text": str(smaller)},
            {"key": "B", "text": str(larger)},
            {"key": "C", "text": str(distractor1)},
            {"key": "D", "text": str(distractor2)},
        ]
        ans_key = "B"
        ans_text = str(larger)
        explanation = "比较两个数的大小，{larger} 更大，所以选 B。".format(larger=larger)
    else:
        choices = [
            {"key": "A", "text": str(smaller)},
            {"key": "B", "text": str(distractor1)},
            {"key": "C", "text": str(larger)},
            {"key": "D", "text": str(distractor2)},
        ]
        ans_key = "C"
        ans_text = str(larger)
        explanation = "比较两个数的大小，{larger} 更大，所以选 C。".format(larger=larger)

    verify = repr(ans_text)
    return {
        'prompt': prompt,
        'answer': ans_key,
        'choices': choices,
        'verify': verify,
        'type': 'choice',
        'explanation': explanation,
    }


def gen_compare_standard(params):
    """比较类 choice 题 (standard)"""
    a = random.randint(10, 50)
    b = random.randint(10, 50)
    # 确保 a != b，避免题目无意义
    while a == b:
        b = random.randint(10, 50)
    larger = max(a, b)
    smaller = min(a, b)
    prompt = "{a} 和 {b} 哪个数更大？".format(a=a, b=b)

    # 随机决定把大数放在 A/B/C 中的哪个位置
    answer_pos = random.choice(["A", "B", "C"])

    # 确保所有选项值唯一
    # correct = larger, other candidates
    while True:
        diff_val = abs(a - b) + 5
        sum_val = a + b
        distractor1 = larger + random.randint(5, 10)
        distractor2 = smaller + random.randint(5, 10)
        values = [larger, smaller, diff_val, sum_val, distractor1, distractor2]
        # 取 4 个唯一值：correct + 2 distractors + 1 computed value
        unique_vals = []
        seen = set()
        for v in values:
            if v not in seen:
                seen.add(v)
                unique_vals.append(v)
                if len(unique_vals) == 4:
                    break
        if len(unique_vals) == 4:
            break

    if answer_pos == "A":
        choices = [
            {"key": "A", "text": str(unique_vals[0])},
            {"key": "B", "text": str(unique_vals[1])},
            {"key": "C", "text": str(unique_vals[2])},
            {"key": "D", "text": str(unique_vals[3])},
        ]
        ans_key = "A"
        ans_text = str(unique_vals[0])
    elif answer_pos == "B":
        choices = [
            {"key": "A", "text": str(unique_vals[1])},
            {"key": "B", "text": str(unique_vals[0])},
            {"key": "C", "text": str(unique_vals[2])},
            {"key": "D", "text": str(unique_vals[3])},
        ]
        ans_key = "B"
        ans_text = str(unique_vals[0])
    else:
        choices = [
            {"key": "A", "text": str(unique_vals[1])},
            {"key": "B", "text": str(unique_vals[2])},
            {"key": "C", "text": str(unique_vals[0])},
            {"key": "D", "text": str(unique_vals[3])},
        ]
        ans_key = "C"
        ans_text = str(unique_vals[0])

    explanation = "比较两个数的大小，{larger} 更大，所以选 {ans_key}。".format(larger=larger, ans_key=ans_key)

    verify = repr(ans_text)
    return {
        'prompt': prompt,
        'answer': ans_key,
        'choices': choices,
        'verify': verify,
        'type': 'choice',
        'explanation': explanation,
    }


def gen_compare_challenge(params):
    """比较类 choice 题 (challenge)"""
    a = random.randint(20, 100)
    b = random.randint(20, 100)
    # 确保 a != b，避免 smaller == larger 导致选项重复
    while a == b:
        b = random.randint(20, 100)
    smaller = min(a, b)
    larger = max(a, b)
    prompt = "从 {a} 和 {b} 中选出较小的一个".format(a=a, b=b)

    # 随机决定把小数放在 A/B/C 中的哪个位置
    answer_pos = random.choice(["A", "B", "C"])
    sum_val = a + b
    diff_val = abs(a - b)

    # 确保所有选项值唯一，使用一个辅助值填充
    extra_val = max(sum_val, diff_val) + random.randint(10, 20)

    if answer_pos == "A":
        choices = [
            {"key": "A", "text": str(smaller)},
            {"key": "B", "text": str(larger)},
            {"key": "C", "text": str(sum_val)},
            {"key": "D", "text": str(extra_val)},
        ]
        ans_key = "A"
        ans_text = str(smaller)
        explanation = "从 {a} 和 {b} 中挑选较小的数，{smaller} 更小，所以选 A。".format(a=a, b=b, smaller=smaller)
    elif answer_pos == "B":
        choices = [
            {"key": "A", "text": str(larger)},
            {"key": "B", "text": str(smaller)},
            {"key": "C", "text": str(sum_val)},
            {"key": "D", "text": str(extra_val)},
        ]
        ans_key = "B"
        ans_text = str(smaller)
        explanation = "从 {a} 和 {b} 中挑选较小的数，{smaller} 更小，所以选 B。".format(a=a, b=b, smaller=smaller)
    else:
        choices = [
            {"key": "A", "text": str(larger)},
            {"key": "B", "text": str(sum_val)},
            {"key": "C", "text": str(smaller)},
            {"key": "D", "text": str(extra_val)},
        ]
        ans_key = "C"
        ans_text = str(smaller)
        explanation = "从 {a} 和 {b} 中挑选较小的数，{smaller} 更小，所以选 C。".format(a=a, b=b, smaller=smaller)

    verify = repr(ans_text)
    return {
        'prompt': prompt,
        'answer': ans_key,
        'choices': choices,
        'verify': verify,
        'type': 'choice',
        'explanation': explanation,
    }


def gen_add_basic(params):
    """加法题 (basic)"""
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    prompt = "1 到 10 内相加：{a} 加 {b} = 多少？".format(a=a, b=b)
    ans = a + b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}+{b}",
        'type': 'numeric',
        'explanation': "{a} 加 {b} 等于 {ans}。".format(a=a, b=b, ans=ans),
    }


def gen_add_standard(params):
    """加法题 (standard)"""
    a = random.randint(10, 50)
    b = random.randint(10, 50)
    prompt = "计算：{a} + {b} = ？".format(a=a, b=b)
    ans = a + b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}+{b}",
        'type': 'numeric',
        'explanation': "{a} 加 {b} 等于 {ans}。".format(a=a, b=b, ans=ans),
    }


def gen_add_challenge(params):
    """加法题 (challenge) - 有情境"""
    a = random.randint(30, 200)
    b = random.randint(30, 200)
    prompt = "小明有 {a} 分，又获得了 {b} 分，现在总分是多少？".format(a=a, b=b)
    ans = a + b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}+{b}",
        'type': 'numeric',
        'explanation': "小明原有 {a} 分，又获得 {b} 分，相加得到 {ans} 分。".format(a=a, b=b, ans=ans),
    }


def gen_sub_basic(params):
    """减法题 (basic)"""
    b = random.randint(1, 10)
    a = random.randint(b, b + 10)
    prompt = "从 {a} 中减去 {b} = ？".format(a=a, b=b)
    ans = a - b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}-{b}",
        'type': 'numeric',
        'explanation': "从 {a} 减去 {b} 等于 {ans}。".format(a=a, b=b, ans=ans),
    }


def gen_sub_standard(params):
    """减法题 (standard)"""
    b = random.randint(10, 50)
    a = random.randint(b, b + 30)
    prompt = "计算：{a} - {b} = ？".format(a=a, b=b)
    ans = a - b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}-{b}",
        'type': 'numeric',
        'explanation': "{a} 减去 {b} 等于 {ans}。".format(a=a, b=b, ans=ans),
    }


def gen_sub_challenge(params):
    """减法题 (challenge) - 有情境"""
    b = random.randint(20, 100)
    a = random.randint(b + 10, b + 100)
    prompt = "仓库里有 {a} 个物品，用掉了 {b} 个，还剩几个？".format(a=a, b=b)
    ans = a - b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}-{b}",
        'type': 'numeric',
        'explanation': "仓库原有 {a} 个物品，用掉了 {b} 个，剩余 {ans} 个。".format(a=a, b=b, ans=ans),
    }


def gen_mul_basic(params):
    """乘法题 (basic)"""
    a = random.randint(1, 5)
    b = random.randint(1, 5)
    prompt = "1 到 5 之间相乘：{a} × {b} = ？".format(a=a, b=b)
    ans = a * b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}*{b}",
        'type': 'numeric',
        'explanation': "{a} 乘以 {b} 等于 {ans}。".format(a=a, b=b, ans=ans),
    }


def gen_mul_standard(params):
    """乘法题 (standard)"""
    a = random.randint(2, 12)
    b = random.randint(2, 12)
    prompt = "计算：{a} × {b} = ？".format(a=a, b=b)
    ans = a * b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}*{b}",
        'type': 'numeric',
        'explanation': "{a} 乘以 {b} 等于 {ans}。".format(a=a, b=b, ans=ans),
    }


def gen_mul_challenge(params):
    """乘法题 (challenge) - 有情境"""
    a = random.randint(4, 15)
    b = random.randint(4, 15)
    prompt = "一排座椅排成 {a} 行，每排有 {b} 个座位，一共有多少个座位？".format(a=a, b=b)
    ans = a * b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}*{b}",
        'type': 'numeric',
        'explanation': "一排座椅排成 {a} 行，每排有 {b} 个座位，共 {ans} 个座位。".format(a=a, b=b, ans=ans),
    }


def gen_story_standard(params):
    """情境题 (standard)"""
    objects = ["苹果", "本", "书", "球", "糖果", "饼干", "蛋糕"]
    verbs = ["加", "拿", "剩", "用"]
    a = random.randint(10, 30)
    b = random.randint(5, 15)
    obj = random.choice(objects)
    verb = random.choice(verbs)
    prompt = "小明有 {a} 个 {obj}，老师又{verb}了 {b} 个，现在有几个 {obj}？".format(a=a, b=b, obj=obj, verb=verb)
    ans = a + b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}+{b}",
        'type': 'numeric',
        'explanation': "小明原有 {a} 个 {obj}，老师又{verb}了 {b} 个，现在共有 {ans} 个 {obj}。".format(a=a, b=b, ans=ans, obj=obj, verb=verb),
    }


def gen_story_challenge(params):
    """情境题 (challenge)"""
    objects = ["苹果", "本", "书", "球", "糖果", "蛋糕", "巧克力", "玩具"]
    verbs = ["加", "拿", "剩", "用", "买了", "送给"]
    a = random.randint(20, 100)
    b = random.randint(10, 50)
    obj = random.choice(objects)
    verb = random.choice(verbs)
    prompt = "小明有 {a} 个 {obj}，老师又{verb}了 {b} 个，现在有几个 {obj}？".format(a=a, b=b, obj=obj, verb=verb)
    ans = a + b
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': f"{a}+{b}",
        'type': 'numeric',
        'explanation': "小明原有 {a} 个 {obj}，老师又{verb}了 {b} 个，现在共有 {ans} 个 {obj}。".format(a=a, b=b, ans=ans, obj=obj, verb=verb),
    }



def gen_position_basic(params):
    """位置题 (basic)"""
    a = random.randint(1, 5)
    prompt = "一排5个物品，从左边数，第 {a} 个是第几个？".format(a=a)
    explanation = "从左边数，第 {a} 个就是它的序号，所以是 {a}。".format(a=a)
    return {
        'prompt': prompt,
        'answer': str(a),
        'verify': str(a),
        'type': 'numeric',
        'explanation': explanation,
    }

def gen_position_standard(params):
    """位置题 (standard) - choice 形式
    把随机数排成序号，从左边数第几个是中间值？
    """
    # 确保三个数不同，避免歧义
    nums = random.sample(range(1, 11), 3)
    nums.sort()
    a, b, c = nums
    # b 在排序后位于中间位置，即第 2 位
    position = 2
    prompt = "把 {a}、{b}、{c} 从小到大排成一排，从左边数，排在中间的那个是第几个数字？".format(a=a, b=b, c=c)

    # 随机分配 1, 2, 3 给 A/B/C 选项
    options = ["1", "2", "3"]
    random.shuffle(options)

    choices = [
        {"key": "A", "text": options[0]},
        {"key": "B", "text": options[1]},
        {"key": "C", "text": options[2]},
        {"key": "D", "text": "4"},
    ]
    # 找到 "2" 所在的 key
    for i, opt in enumerate(options):
        if opt == "2":
            ans_key = ["A", "B", "C"][i]
            break
    ans_text = "2"
    verify = repr(ans_text)
    explanation = "将 {a}、{b}、{c} 按大小排序后：{a}、{b}、{c}。从左边数，{b} 位于第 {position} 个位置。".format(a=a, b=b, c=c, position=position)
    return {
        'prompt': prompt,
        'answer': ans_key,
        'choices': choices,
        'verify': verify,
        'type': 'choice',
        'explanation': explanation,
    }

def gen_position_challenge(params):
    """位置题 (challenge) - 有情境"""
    a = random.randint(3, 12)
    b = random.randint(1, 5)
    prompt = "小华排在第 {a} 个位置，前面有 {b} 个人，排队总共有多少人？".format(a=a, b=b)
    ans = a + b
    explanation = "小华排在第 {a} 位，前面有 {b} 个人，所以队伍总人数是 {a}+{b}={ans} 人。".format(a=a, b=b, ans=ans)
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': "{}+{}".format(a, b),
        'type': 'numeric',
        'explanation': explanation,
    }

def gen_partition_basic(params):
    """分合题 (basic) - 加法形式"""
    a = random.randint(1, 4)  # 确保 a <= 4，这样 b = randint(1, 5-a) >= 1
    b = random.randint(1, 5 - a)
    prompt = "{a} 和 {b} 合起来是几？".format(a=a, b=b)
    ans = a + b
    explanation = "{a} 和 {b} 合在一起是 {ans}。".format(a=a, b=b, ans=ans)
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': "{}+{}".format(a, b),
        'type': 'numeric',
        'explanation': explanation,
    }

def gen_partition_standard(params):
    """分合题 (standard) - 减法形式"""
    total = random.randint(5, 10)
    part = random.randint(1, total - 1)
    prompt = "{total} 可以分成 {part} 和几？".format(total=total, part=part)
    ans = total - part
    explanation = "{total} 总共有 {total} 个，分出 {part} 个，剩下 {ans} 个。".format(total=total, part=part, ans=ans)
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': "{}-{}".format(total, part),
        'type': 'numeric',
        'explanation': explanation,
    }

def gen_partition_challenge(params):
    """分合题 (challenge) - 有情境"""
    total = random.randint(10, 30)
    part1 = random.randint(3, 12)
    prompt = "小明把 {total} 颗糖分成两堆，一堆有 {part1} 颗，另一堆有多少颗？".format(total=total, part1=part1)
    ans = total - part1
    explanation = "小明总共有 {total} 颗糖，分出 {part1} 颗，剩余 {ans} 颗。".format(total=total, part1=part1, ans=ans)
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': "{}-{}".format(total, part1),
        'type': 'numeric',
        'explanation': explanation,
    }
def gen_compare_order(params, difficulty='basic'):
    """数的顺序比较题"""
    if difficulty == 'basic':
        # 位置题：随机排列3个数，从左边数中间位置是第几
        # 让答案在 A/B/C 中随机（只用前3个选项）
        nums = random.sample(range(1, 11), 3)
        # 随机决定中间位置是第几（不一定是排序后第2个）
        pos_in_sorted = random.randint(0, 2)
        sorted_nums = sorted(nums)
        middle_val = sorted_nums[pos_in_sorted]

        # 随机分配给 A/B/C
        ans_key = random.choice(["A", "B", "C"])
        ans_text = "2"  # 中间位置总是第2个

        options = ["1", "2", "3"]
        random.shuffle(options)

        prompt = "把 {a}、{b}、{c} 从小到大排成一排，从左边数，中间的数字是哪个位置？".format(a=nums[0], b=nums[1], c=nums[2])
        choices = [
            {"key": "A", "text": options[0]},
            {"key": "B", "text": options[1]},
            {"key": "C", "text": options[2]},
            {"key": "D", "text": "4"},
        ]
        # 找到答案 key 对应的位置
        for i, opt in enumerate(options):
            if opt == ans_text:
                keys_order = ["A", "B", "C"]
                ans_key = keys_order[i]
                break
        verify = repr(ans_text)
        explanation = "将 {a}、{b}、{c} 排序后为 {sorted_nums}，中间的数字在第 2 个位置。".format(a=nums[0], b=nums[1], c=nums[2], sorted_nums=sorted_nums)
        return {
            'prompt': prompt,
            'answer': ans_key,
            'choices': choices,
            'verify': verify,
            'type': 'choice',
            'explanation': explanation,
        }
    elif difficulty == 'standard':
        # 最小值题：从3个数中挑最小，答案随机在 A 或 B（不总是 A）
        # 确保三个数字唯一
        a, b, c = random.sample(range(10, 51), 3)
        nums = sorted([a, b, c])
        smallest = nums[0]
        prompt = "从 {a}、{b}、{c} 这三个数字里挑出最小的那个".format(a=a, b=b, c=c)

        # 随机决定把最小值放在 A 还是 B
        put_smallest_first = random.choice([True, False])
        if put_smallest_first:
            choices = [
                {"key": "A", "text": str(smallest)},
                {"key": "B", "text": str(nums[1])},
                {"key": "C", "text": str(nums[2])},
                {"key": "D", "text": str(a + b + c)},
            ]
            ans_key = "A"
        else:
            choices = [
                {"key": "A", "text": str(nums[1])},
                {"key": "B", "text": str(smallest)},
                {"key": "C", "text": str(nums[2])},
                {"key": "D", "text": str(a + b + c)},
            ]
            ans_key = "B"

        ans_text = str(smallest)
        verify = repr(ans_text)
        explanation = "{a}、{b}、{c} 三个数中（排序后：{sorted_nums}），最小的是 {smallest}。".format(a=a, b=b, c=c, sorted_nums=nums, smallest=smallest)
        return {
            'prompt': prompt,
            'answer': ans_key,
            'choices': choices,
            'verify': verify,
            'type': 'choice',
            'explanation': explanation,
        }
    else:
        # challenge: numeric with context
        a = random.randint(3, 15)
        b = random.randint(a + 1, a + 5)
        ans = b - a
        prompt = "小明从 {a} 数到 {b}，跨越了多少个整数？".format(a=a, b=b)
        verify = f"{b}-{a}"
        explanation = "小明从 {a} 数到 {b}，中间跨过的整数个数是 {b} - {a} = {ans}。".format(a=a, b=b, ans=ans)
        return {
            'prompt': prompt,
            'answer': str(ans),
            'verify': verify,
            'type': 'numeric',
            'explanation': explanation,
        }


def gen_equality(params, difficulty='basic'):
    """相等比较题 - choice 题，选项是数
    问题：哪个数多？
    答案是正确选项的 key，verify 返回正确选项的 text
    为解决 KEYSKEW，答案在 A/B/C 中随机分配（33%）
    """
    if difficulty == 'basic':
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        while a == b:  # 确保 a != b，避免题目无意义
            b = random.randint(1, 10)
    elif difficulty == 'standard':
        a = random.randint(10, 50)
        b = random.randint(10, 50)
        while a == b:
            b = random.randint(10, 50)
    else:
        a = random.randint(20, 100)
        b = random.randint(20, 100)
        while a == b:
            b = random.randint(20, 100)

    prompt = "{a} 和 {b} 上哪个数多？".format(a=a, b=b)

    big = max(a, b)
    small = min(a, b)

    # 生成所有选项文本，确保唯一
    # 答案在 A/B/C 中随机分配（33%）
    answer_pos = random.choice(["A", "B", "C"])

    if big == small:
        # a == b 时，两数相等，答案随机在 A/B/C 任一位置
        a_text = str(big)
        b_text = str(big + random.choice([-4, -2, -1, 1, 2, 3, 5]))
        b_text = str(max(1, min(100, int(b_text))))
        # 确保不相等
        while b_text == a_text:
            b_text = str(max(1, min(100, int(a_text) + random.choice([1, 2, 3]))))
        # C 选项：另一个备选数
        c_text = str(big + random.choice([-5, 5]))
        c_text = str(max(1, min(100, int(c_text))))
        while c_text == a_text:
            c_text = str(max(1, min(100, int(a_text) + random.choice([1, 2, 3]))))
        # D 选项：第四个数
        d_text = str(big + random.choice([-6, 6]))
        d_text = str(max(1, min(100, int(d_text))))
        while d_text in {a_text, b_text, c_text}:
            d_text = str(max(1, min(100, int(a_text) + random.choice([1, 2, 3, 4]))))

        if answer_pos == "A":
            ans_text = a_text
            ans_key = "A"
            explanation = "{a} 和 {b} 相等，所以两数都多，选 A。".format(a=a, b=b)
        elif answer_pos == "B":
            ans_text = b_text
            ans_key = "B"
            explanation = "{a} 和 {b} 相等，所以两数都多，选 B。".format(a=a, b=b)
        else:
            ans_text = c_text
            ans_key = "C"
            explanation = "{a} 和 {b} 相等，所以三个数中，{c_text} 最大，选 C。".format(a=a, b=b, c_text=c_text)
    elif answer_pos == "A":
        a_text = str(big)
        b_text = str(small)
        c_text = str(big + small)
        ans_text = a_text
        ans_key = "A"
        explanation = "{a} 和 {b} 比较，{big} 更多，所以选 A。".format(a=a, b=b, big=big)
    elif answer_pos == "B":
        a_text = str(small)
        b_text = str(big)
        c_text = str(big + small)
        ans_text = b_text
        ans_key = "B"
        explanation = "{a} 和 {b} 比较，{big} 更多，所以选 B。".format(a=a, b=b, big=big)
    else:
        # C 选项放 big (作为答案)，A/B 使用 different values
        a_text = str(small)
        b_text = str(big + small)  # 和 big 不同
        c_text = str(big)
        ans_text = c_text
        ans_key = "C"
        explanation = "{a} 和 {b} 比较，{big} 更多，所以选 C。".format(a=a, b=b, big=big)

        # D 选项：使用计算值，确保不与 A/B/C 重复
        d_text = str(abs(big - small) + 10)
        used = {a_text, b_text, c_text}
        if d_text in used or d_text == c_text:
            d_text = str(abs(big - small) + 5)
            if d_text in used or d_text == c_text:
                d_text = str((big + small) // 2 + 1)
        if d_text in used or d_text == c_text:
            d_text = str(big + 1)
    # 对于 A/B 为答案的情况，C/D 选项使用计算值
    if ans_key in ["A", "B"]:
        c_text = str(big + small)
        used = {a_text, b_text}
        if c_text in used:
            c_text = str(big + small + 1)
            if c_text in used:
                c_text = str(big + 1)

        d_text = str(abs(big - small) + 10)
        if d_text in used or d_text == c_text:
            d_text = str(abs(big - small) + 5)
            if d_text in used or d_text == c_text:
                d_text = str((big + small) // 2 + 1)
        if d_text in used or d_text == c_text:
            d_text = str(big + 1)

    # 最终检查：确保所有选项 text 唯一
    all_texts = [a_text, b_text, c_text, d_text]
    if len(set(all_texts)) < 4:
        # 有重复，调整 D 选项
        d_text = str(max(int(a_text), int(b_text), int(c_text)) + 1)
        if d_text in {a_text, b_text, c_text}:
            d_text = str(max(int(a_text), int(b_text), int(c_text)) + 2)

    choices = [
        {"key": "A", "text": a_text},
        {"key": "B", "text": b_text},
        {"key": "C", "text": c_text},
        {"key": "D", "text": d_text},
    ]

    verify = repr(ans_text)
    return {
        'prompt': prompt,
        'answer': ans_key,
        'choices': choices,
        'verify': verify,
        'type': 'choice',
        'explanation': explanation,
    }


def gen_count_numeric(params, difficulty='basic'):
    """数的数 (数数)"""
    if difficulty == 'basic':
        a = random.randint(1, 10)
        prompt = "数一下：图上有几个？(想象有 {a} 个)".format(a=a)
        ans = a
        explanation = "图上有 {a} 个物品。".format(a=a)
        return {
            'prompt': prompt,
            'answer': str(ans),
            'verify': str(ans),
            'type': 'numeric',
            'explanation': explanation,
        }
    else:
        # standard / challenge: ensure no negative results
        a = random.randint(10, 20)
        b = random.randint(1, min(10, a))  # ensure a >= b
        action = random.choice(['加', '减'])
        if action == '加':
            prompt = "有 {a} 个，又加了 {b} 个，现在有几个？".format(a=a, b=b)
            ans = a + b
            verify_expr = f"{a}+{b}"
            explanation = "一开始有 {a} 个，用掉或得到了 {b} 个，现在有 {ans} 个。".format(a=a, b=b, ans=ans)
        else:
            prompt = "有 {a} 个，用掉了 {b} 个，还剩几个？".format(a=a, b=b)
            ans = a - b
            verify_expr = f"{a}-{b}"
            explanation = "一开始有 {a} 个，用掉了 {b} 个，还剩 {ans} 个。".format(a=a, b=b, ans=ans)
        return {
            'prompt': prompt,
            'answer': str(ans),
            'verify': verify_expr,
            'type': 'numeric',
            'explanation': explanation,
        }


def gen_sequencing(params, difficulty='simple'):
    """数的数顺序"""
    if difficulty == 'basic':
        a = random.randint(1, 9)
        b = random.randint(a + 1, 10)
        ans = a + 1
        prompt = "{a} 和 {b} 之间是哪个数？".format(a=a, b=b)
        verify = f"{a}+1"
        explanation = "{a} 和 {b} 之间的数是 {ans}，因为 {a}+1={ans}。".format(a=a, b=b, ans=ans)
        return {
            'prompt': prompt,
            'answer': str(ans),
            'verify': verify,
            'type': 'numeric',
            'explanation': explanation,
        }
    else:
        # standard / challenge: position before
        a = random.randint(2, 15)
        ans = a - 1
        prompt = "从左边数，排在 {a} 前面的数是几号？".format(a=a)
        verify = f"{a}-1"
        explanation = "排在 {a} 前面的数是 {ans}，因为 {a}-1={ans}。".format(a=a, ans=ans)
        return {
            'prompt': prompt,
            'answer': str(ans),
            'verify': verify,
            'type': 'numeric',
            'explanation': explanation,
        }


def gen_mixed_challenge(params):
    """综合运算 (challenge) - 有情境"""
    ops = [
        ('+', lambda a, b: a + b, '加'),
        ('-', lambda a, b: a - b, '减'),
        ('*', lambda a, b: a * b, '乘'),
    ]
    op_sym, op_func, op_word = random.choice(ops)

    if op_sym == '-':
        b = random.randint(20, 80)
        a = random.randint(b + 10, b + 80)
    elif op_sym == '*':
        a = random.randint(5, 15)
        b = random.randint(5, 15)
    else:
        a = random.randint(50, 200)
        b = random.randint(10, 50)

    ans = op_func(a, b)
    prompt = "小明有 {a} 分，{op_word}了 {b} 分，现在有几个分？".format(a=a, op_word=op_word, b=b)
    verify = f"{a}{op_sym}{b}"
    explanation = "小明原有 {a} 分，{op_word}了 {b} 分，结果是 {a}{op_sym}{b} = {ans}。".format(a=a, op_word=op_word, b=b, op_sym=op_sym, ans=ans)
    return {
        'prompt': prompt,
        'answer': str(ans),
        'verify': verify,
        'type': 'numeric',
        'explanation': explanation,
    }


# KEYSKEW 阈值：单个答案位置占比上限
KEYSKEW_THRESHOLD = 0.45

def generate_for_topic(topic_id: str, need_basic: int = 10, need_standard: int = 10, need_challenge: int = 40) -> list:
    """为单个 topic 生成题目
    Args:
        topic_id: 知识点ID
        need_basic: basic难度题目数量
        need_standard: standard难度题目数量
        need_challenge: challenge难度题目数量
    """
    topics = json.load(io.open(TOPNS_PATH, encoding='utf-8'))
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        print(f"Topic not found: {topic_id}")
        return []

    params = {
        'topicId': topic_id,
        'grade': topic.get('grade', 1),
        'subject': subject_of(topic),
        'stage': stage(topic),
        'classification': classify_topic(topic),
        'description': topic.get('description'),
        'name': topic.get('name'),
    }

    ktype = params.get('classification')
    qs = []
    seen = set()
    # 跟踪 choice 题的答案分布
    choice_answer_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}

    def can_add_answer(key, total):
        """检查添加答案 key 是否会触发 KEYSKEW"""
        if total == 0:
            return True
        new_count = choice_answer_counts.get(key, 0) + 1
        return new_count / (total + 1) < KEYSKEW_THRESHOLD

    def add_choice_answer(q):
        """为 choice 题设置答案，确保分布均匀"""
        ans_key = q.get('answer')
        total_choice = sum(choice_answer_counts.values())
        if can_add_answer(ans_key, total_choice):
            choice_answer_counts[ans_key] += 1
            return True
        # 如果当前答案会触发 KEYSKEW，尝试换一个选项
        for alt_key in ['C', 'B', 'A']:
            if alt_key != ans_key and can_add_answer(alt_key, total_choice):
                q['answer'] = alt_key
                choice_answer_counts[alt_key] += 1
                # 更新 verify 以匹配新的答案
                choices = q.get('choices', [])
                if choices:
                    for c in choices:
                        if c['key'] == alt_key:
                            q['verify'] = repr(c['text'])
                            break
                return True
        # 都不行，接受当前答案
        choice_answer_counts[ans_key] += 1
        return True

    def add(q):
        key = (q['prompt'], q.get('answer'))
        if key in seen:
            return
        seen.add(key)
        q['topicId'] = topic_id
        if q.get('type') == 'choice':
            add_choice_answer(q)
        else:
            pass  # numeric 题不计入 KEYSKEW
        qs.append(q)

    # Basic: 填充 basic 题目
    for _ in range(need_basic):
        added = False
        if ktype == 'comparison':
            add(gen_compare_basic(params))
            added = True
        elif ktype == 'addition':
            add(gen_add_basic(params))
            added = True
        elif ktype == 'subtraction':
            add(gen_sub_basic(params))
            added = True
        elif ktype == 'multiplication':
            add(gen_mul_basic(params))
            added = True
        elif ktype == 'division':
            if 'add' not in [q.get('prompt', '').lower() for q in qs[-3:]]:
                add(gen_add_basic(params))
                add(gen_sub_basic(params))
            else:
                add(gen_mul_basic(params))
        elif ktype == 'number_recognition':
            template = ['equality', 'count', 'sequencing', 'compare_order']
            add_template = template[len(qs) % 4]
            if add_template == 'equality':
                add(gen_equality(params, 'basic'))
            elif add_template == 'count':
                add(gen_count_numeric(params, 'basic'))
            elif add_template == 'sequencing':
                add(gen_sequencing(params, 'basic'))
            else:
                add(gen_compare_order(params, 'basic'))
        elif ktype == 'sequence':
            add(gen_sequencing(params, 'basic'))
        elif ktype == 'position':
            add(gen_position_basic(params))
        elif ktype == 'partition':
            add(gen_partition_basic(params))
        else:
            add(gen_add_basic(params))
            add(gen_sub_basic(params))

    # Standard: 填充 standard 题目
    for _ in range(need_standard):
        added = False
        if ktype == 'comparison':
            add(gen_compare_standard(params))
            added = True
        elif ktype == 'addition':
            add(gen_add_standard(params))
            add(gen_sub_standard(params))
            add(gen_story_standard(params))
        elif ktype == 'subtraction':
            add(gen_sub_standard(params))
            add(gen_add_standard(params))
        elif ktype == 'multiplication':
            add(gen_mul_standard(params))
            add(gen_add_standard(params))
        elif ktype == 'division':
            add(gen_add_standard(params))
            add(gen_sub_standard(params))
            add(gen_mul_standard(params))
            add(gen_compare_standard(params))
        elif ktype == 'number_recognition':
            template = ['equality', 'count', 'sequencing', 'compare_order']
            add_template = template[len(qs) % 4]
            if add_template == 'equality':
                add(gen_equality(params, 'standard'))
            elif add_template == 'count':
                add(gen_count_numeric(params, 'standard'))
            elif add_template == 'sequencing':
                add(gen_sequencing(params, 'standard'))
            else:
                add(gen_compare_order(params, 'standard'))
        elif ktype == 'sequence':
            add(gen_sequencing(params, 'standard'))
        elif ktype == 'position':
            add(gen_position_standard(params))
        elif ktype == 'partition':
            add(gen_partition_standard(params))
        else:
            add(gen_add_standard(params))
            add(gen_sub_standard(params))

    # Challenge: 为 number_recognition 生成专属题目
    if ktype == 'number_recognition':
        add(gen_compare_order(params, 'challenge'))
        add(gen_sequencing(params, 'challenge'))
        add(gen_equality(params, 'challenge'))
        add(gen_count_numeric(params, 'challenge'))

        # 填充到 40 题 challenge - 采用循环变体
        while len(qs) < (need_basic + need_standard + need_challenge):
            add(gen_equality(params, 'challenge'))
            add(gen_sequencing(params, 'challenge'))
            add(gen_compare_order(params, 'challenge'))
            add(gen_count_numeric(params, 'challenge'))
    elif ktype == 'position':
        add(gen_position_challenge(params))
        add(gen_position_standard(params))
        while len(qs) < (need_basic + need_standard + need_challenge):
            add(gen_position_challenge(params))
            add(gen_sequencing(params, 'challenge'))
    elif ktype == 'partition':
        add(gen_partition_challenge(params))
        add(gen_partition_standard(params))
        while len(qs) < (need_basic + need_standard + need_challenge):
            add(gen_partition_challenge(params))
            add(gen_sequencing(params, 'challenge'))
    else:
        # 其它类型使用通用 challenge 题目
        add(gen_add_challenge(params))
        add(gen_sub_challenge(params))
        add(gen_mul_challenge(params))
        add(gen_story_challenge(params))
        add(gen_compare_challenge(params))
        add(gen_mixed_challenge(params))

        # 填充到所需总数
        while len(qs) < (need_basic + need_standard + need_challenge):
            add(gen_add_challenge(params))
            add(gen_sub_challenge(params))
            add(gen_mul_challenge(params))
            add(gen_story_challenge(params))
            add(gen_compare_challenge(params))
            add(gen_mixed_challenge(params))

    # 按需分配 difficulty
    basic_end = need_basic
    standard_end = need_basic + need_standard
    for i, q in enumerate(qs):
        if i < basic_end:
            q['difficulty'] = 'basic'
        elif i < standard_end:
            q['difficulty'] = 'standard'
        else:
            q['difficulty'] = 'challenge'

    # 确保每个题目都有 type 字段
    for q in qs:
        if 'type' not in q:
            q['type'] = 'numeric' if 'choices' not in q else 'choice'

    return qs[:need_basic + need_standard + need_challenge]


def create_math_batch_templates():
    """Create math batch template files based on manifest"""
    topics = json.load(io.open(TOPNS_PATH, encoding='utf-8'))
    topics_by_id = {t['id']: t for t in topics}

    manifest_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(io.open(manifest_path, encoding='utf-8'))

    for entry in manifest:
        if entry.get('subject') != 'math':
            continue

        batch_file = entry['file']
        batch_path = os.path.join(OUT, batch_file)

        # Read existing batch file or create from scratch using topic IDs from manifest
        if os.path.exists(batch_path):
            batch = json.load(io.open(batch_path, encoding='utf-8'))
        else:
            # Create template based on count and stage
            count = entry['count']
            batch_stage = entry['stage']
            math_topics = [t for t in topics if t.get('subject') == 'math' and stage(t) == batch_stage]
            # Just take first 'count' topics as templates
            math_topics = math_topics[:count]
            batch = []
            for t in math_topics:
                batch.append({
                    "topicId": t['id'],
                    "subject": t.get('subject', 'math'),
                    "stage": stage(t),
                    "name": t.get('name'),
                    "grade": t.get('grade'),
                    "semester": t.get('semester'),
                    "chapter": t.get('chapter'),
                    "domain": t.get('domain'),
                    "description": t.get('description'),
                    "mastery_criteria": t.get('mastery_criteria'),
                    "need": {
                        "basic": 10,
                        "standard": 10,
                        "challenge": 40
                    }
                })

        json.dump(batch, io.open(batch_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"Created template: {batch_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', help='单个 topic_id')
    parser.add_argument('--count', type=int, default=60)
    parser.add_argument('--batch', action='store_true', help='遍历 manifest')
    parser.add_argument('--all-math', action='store_true', help='生成所有数学 topic 的问题')
    parser.add_argument('--create-math-batches', action='store_true', help='创建所有数学 batch 模板')
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)

    if args.topic:
        qs = generate_for_topic(args.topic, need_basic=10, need_standard=10, need_challenge=40)
        out_file = os.path.join(OUT, f"{args.topic}.json")
        json.dump(qs, io.open(out_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f"Written {len(qs)} questions to {out_file}")
        return

    if args.create_math_batches:
        create_math_batch_templates()
        return

    if args.all_math:
        topics = json.load(io.open(TOPNS_PATH, encoding='utf-8'))
        math_topics = [t for t in topics if t.get('subject') == 'math' or t['id'].startswith('cnm_')]
        print(f"Found {len(math_topics)} math topics")
        questions = []
        for t in math_topics:
            tid = t['id']
            qs = generate_for_topic(tid, need_basic=10, need_standard=10, need_challenge=40)
            questions.extend(qs)
            print(f"Generated {len(qs)} for {tid}")
        out_file = os.path.join(OUT, "math_all.json")
        json.dump(questions, io.open(out_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f"Written {len(questions)} questions to {out_file}")
        return

    if args.batch:
        manifest_path = os.path.join(OUT, "manifest.json")
        if not os.path.exists(manifest_path):
            print("No manifest found. Run qgen_prep.py first.")
            return

        manifest = json.load(io.open(manifest_path, encoding='utf-8'))
        for entry in manifest:
            if entry.get('subject') != 'math':
                continue
            batch_file = entry['file']
            batch_path = os.path.join(OUT, batch_file)

            # Read template batch file
            if not os.path.exists(batch_path):
                print(f"No template found: {batch_file}")
                continue

            topics = json.load(io.open(TOPNS_PATH, encoding='utf-8'))
            batch_data = json.load(io.open(batch_path, encoding='utf-8'))

            questions = []
            for t in batch_data:
                tid = t["topicId"]
                need_challenge = t["need"].get("challenge", 0)
                need_basic = t["need"].get("basic", 0)
                need_standard = t["need"].get("standard", 0)

                qs = generate_for_topic(tid, need_basic, need_standard, need_challenge)
                questions.extend(qs)

            if questions:
                json.dump(questions, io.open(batch_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                print(f"Written {len(questions)} questions to {batch_file}")


if __name__ == "__main__":
    main()