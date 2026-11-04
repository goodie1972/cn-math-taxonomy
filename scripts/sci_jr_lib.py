# -*- coding: utf-8 -*-
"""初中科学（7~9 年级 + 五四制六年级）数据的登记与题目生成。由 scripts/sci_jr_build.py 调用。

目录依据（2026-11-04 双源取证，记录见 _scratch/junior_toc/sci_junior.json）：
- 沪科技版（五四制，上海科学技术出版社，主编俞立中，2024 起修订）：六年级上册/下册。
  上海 2026 秋起七年级不再开设科学（生物学提前至七、化学提前至八），国家目录五四制科学
  止于六年级下册；六年级属初中段（上海目录教参代码 SD-CJ-*）。
- 浙教版（浙江教育出版社，2024 起修订）：七年级上册~九年级上册五册已启用；
  九年级下册修订版按计划 2027 春季启用，当前学年在用旧版（2011 课标）目录，故九下按旧版建点。
  六三制初中科学国家目录仅浙教版在册（华东师大版宁波已停用、武汉版现况未核到，暂不建池）。

建点粒度：一节一点（每节一个知识点，4 题）。领域按章归属：物质科学/生命科学/
地球与宇宙科学/技术与工程。
"""

import re

TOPICS = []
HARD = []

# (年级, 学期, 单元) -> (章名, 领域, 默认课标符号)
UNITS = {
    # 沪科技版（五四制）六年级
    (6, "上", 1): ("变化的物质世界", "物质科学", "wz4_chg"),
    (6, "上", 2): ("能与生活", "物质科学", "wz4_en"),
    (6, "上", 3): ("生命的延续", "生命科学", "sm4_evo"),
    (6, "上", 4): ("小小工程师——节能小屋", "技术与工程", "jg4_eng"),
    (6, "下", 1): ("人体与健康", "生命科学", "sm4_body"),
    (6, "下", 2): ("步入青春期", "生命科学", "sm4_body"),
    (6, "下", 3): ("宇宙探秘", "地球与宇宙科学", "dq4_sys"),
    (6, "下", 4): ("小小工程师——火星车", "技术与工程", "jg4_eng"),
    # 浙教版七年级
    (7, "上", 1): ("第1章 探索自然的科学", "物质科学", "wz4_mot"),
    (7, "上", 2): ("第2章 丰富多彩的生命世界", "生命科学", "sm4_sys"),
    (7, "上", 3): ("第3章 广袤浩瀚的宇宙", "地球与宇宙科学", "dq4_sys"),
    (7, "上", 4): ("第4章 多种多样的运动", "物质科学", "wz4_mot"),
    (7, "上", 5): ("第5章 探索技术与工程的世界", "技术与工程", "jg4_tech"),
    (7, "下", 1): ("第1章 生物的结构与生殖", "生命科学", "sm4_sys"),
    (7, "下", 2): ("第2章 物质的微观结构", "物质科学", "wz4_mat"),
    (7, "下", 3): ("第3章 物质的特性", "物质科学", "wz4_mat"),
    (7, "下", 4): ("第4章 我们生活的大地", "地球与宇宙科学", "dq4_sys"),
    (7, "下", 5): ("第5章 制造技术与工程", "技术与工程", "jg4_eng"),
    # 浙教版八年级
    (8, "上", 1): ("第1章 对环境的察觉", "生命科学", "sm4_body"),
    (8, "上", 2): ("第2章 力与空间探索", "物质科学", "wz4_mot"),
    (8, "上", 3): ("第3章 电路探秘", "物质科学", "wz4_en"),
    (8, "上", 4): ("第4章 水与人类", "地球与宇宙科学", "dq4_human"),
    (8, "上", 5): ("第5章 建筑结构与工程", "技术与工程", "jg4_eng"),
    (8, "下", 1): ("第1章 我们呼吸的空气", "物质科学", "wz4_chg"),
    (8, "下", 2): ("第2章 大气与气候变化", "地球与宇宙科学", "dq4_human"),
    (8, "下", 3): ("第3章 电磁及其应用", "物质科学", "wz4_en"),
    (8, "下", 4): ("第4章 人体的系统", "生命科学", "sm4_body"),
    (8, "下", 5): ("第5章 控制系统与工程", "技术与工程", "jg4_eng"),
    # 浙教版九年级
    (9, "上", 1): ("第1章 酸碱盐的性质及其变化", "物质科学", "wz4_chg"),
    (9, "上", 2): ("第2章 能的转化与能量守恒", "物质科学", "wz4_en"),
    (9, "上", 3): ("第3章 生命的稳态与调节", "生命科学", "sm4_body"),
    (9, "上", 4): ("第4章 生命的起源与变化", "生命科学", "sm4_evo"),
    (9, "上", 5): ("第5章 能源及其利用", "物质科学", "wz4_en"),
    (9, "下", 1): ("第1章 演化的自然", "地球与宇宙科学", "sm4_evo"),
    (9, "下", 2): ("第2章 生物与环境", "生命科学", "sm4_env"),
    (9, "下", 3): ("第3章 人的健康", "生命科学", "sm4_body"),
    (9, "下", 4): ("第4章 可持续发展", "地球与宇宙科学", "dq4_human"),
}

DOMAINS = ("物质科学", "生命科学", "地球与宇宙科学", "技术与工程")
GRADE_CN = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
CODE_OF = {"WZ": "物质科学", "SM": "生命科学", "DQ": "地球与宇宙科学", "JG": "技术与工程"}

# 课标条目是《义务教育科学课程标准（2022年版）》第四学段内容要求的公开转述，不是逐页核对的原文。
# 学段 4 对应七~九年级（五四制六、七年级结合第四学段目标确定）。(符号, 学段, 代码, 核心概念, 转述)
STANDARD_ROWS = [
    ("wz4_mat", "4", "WZ", "物质的结构与性质", "知道已知的绝大多数物质由元素组成，由分子、原子等微观粒子构成，不同组成与结构的物质具有不同的性质与用途，能从微观视角初步认识物质及其变化，初步形成物质的性质决定用途、物质是不断变化的观念。"),
    ("wz4_chg", "4", "WZ", "物质的变化与化学反应", "认识化学变化可以产生新的物质，并伴随能的转化，其本质是原子的重新组合；能区分物理变化与化学变化，了解常见酸碱盐的性质及其变化。"),
    ("wz4_mot", "4", "WZ", "物质的运动与相互作用", "认识常见的几种运动形式，能解决匀速运动的基本问题；运用简单模型描述和解释物体间的相互作用，理解力与运动的关系、压强等概念。"),
    ("wz4_en", "4", "WZ", "能的转化与能量守恒", "基于证据论证能的转化与能量守恒，理解其在社会生活中的意义；认识电能、内能、机械能等形式的转化，理解能源的利用与开发。"),
    ("sm4_sys", "4", "SM", "生命系统的构成层次", "能说出生命系统的构成层次，认识生命系统的层次性、开放性和复杂性；理解生物体的结构与功能相适应。"),
    ("sm4_body", "4", "SM", "生物体的稳态与调节", "知道生物体的生命过程及其调节机制，解释生命系统能通过自我调节维持稳态；认识人体各系统的结构与功能。"),
    ("sm4_env", "4", "SM", "生物与环境的相互关系", "认识人与环境之间的相互关系；知道种群、群落与生态系统，说明生物多样性和适应性是进化的结果。"),
    ("sm4_evo", "4", "SM", "生命的延续与进化", "说明生物多样性和适应性是进化的结果；知道生命起源与进化的基本历程，初步形成进化与适应的观念。"),
    ("dq4_sys", "4", "DQ", "宇宙中的地球与地球系统", "知道不同层次的天体系统，认识地球所处的宇宙环境，能运用太阳、地球和月球的相对运动解释相关的自然现象，关注天文和航天事业的进展。"),
    ("dq4_human", "4", "DQ", "人类活动与环境", "知道不同圈层的相互作用驱动了地球系统的演化；知道资源短缺、环境污染和生态破坏等问题及其原因，了解解决这些问题的措施，初步形成人地协调的观念。"),
    ("jg4_tech", "4", "JG", "技术、工程与社会", "知道现代技术与工程具有系统性和复杂性，知道科学对技术与工程具有指导意义，体会技术推动社会进步。"),
    ("jg4_eng", "4", "JG", "工程设计与物化", "知道工程需要经历明确问题、设计方案、实施计划、检验作品、改进完善、发布成果等过程，能按流程完成设计与制作任务。"),
]

TYPES = ("conceptual", "procedural", "reasoning", "application", "modeling")
CRIT = {
    "物质科学": ["能说出物质变化与能的转化的本质", "能用模型或证据解释力、运动与相互作用"],
    "生命科学": ["能说明生命系统的层次与调节机制", "能解释稳态、进化与适应的关系"],
    "地球与宇宙科学": ["能运用日地月模型解释自然现象", "能说明人类活动与环境问题的关系"],
    "技术与工程": ["能说明科学与工程的关系", "能按设计、制作、测试、改进的流程完成任务"],
}
NOTE = "浙教版/沪科技版该节（课）的常见教学内容。条目是公开转述，不是逐页核对的原文。"
LEVEL_CN = {"1": "一", "2": "二", "3": "三", "4": "四"}
LEVEL_GRADES = {"1": "1–2", "2": "3–4", "3": "5–6", "4": "7–9"}


def stage_label():
    levels = sorted({row[1] for row in STANDARD_ROWS})
    return "第%s至第%s学段（%s年级）" % (
        LEVEL_CN[levels[0]], LEVEL_CN[levels[-1]], "、".join(LEVEL_GRADES[l] for l in levels))


def chapter(grade, sem, unit):
    cn = GRADE_CN[grade]
    title = UNITS[(grade, sem, unit)][0]
    if grade == 6:
        # 五四制六年级：单元号即教材单元号
        return "%s年级%s册 第%d单元 %s" % (cn, sem, unit, title)
    return "%s年级%s册 %s" % (cn, sem, title)


def hard(topic, prereq, reason):
    HARD.append((topic, prereq, reason))


_CUR = {}


def vol(grade, sem):
    _CUR["g"], _CUR["s"] = grade, sem


def K(key, name, unit, typ, desc, qs, std=None, domain=None):
    """登记一个知识点。qs 是 4 道选择题：(题干, 正确答案, [三个干扰项], 解析)，难度依次 basic、basic、standard、challenge。"""
    g, s = _CUR["g"], _CUR["s"]
    if (g, s, unit) not in UNITS:
        raise SystemExit("%s 单元未登记：%s%s 第%d单元" % (key, g, s, unit))
    _u, udom, ustd = UNITS[(g, s, unit)]
    domain = domain or udom
    if domain not in DOMAINS:
        raise SystemExit("%s 领域无法识别：%s" % (key, domain))
    if typ not in TYPES:
        raise SystemExit("%s type 非法：%s" % (key, typ))
    if len(qs) != 4:
        raise SystemExit("%s 需要恰好 4 题" % key)
    if any(t["key"] == key for t in TOPICS):
        raise SystemExit("知识点 key 重复：%s" % key)
    TOPICS.append({
        "key": key, "name": name, "domain": domain, "grade": g, "semester": s,
        "unit": unit, "type": typ, "description": desc,
        "mastery_criteria": list(CRIT[domain]), "std": std or ustd, "conf": "inferred", "note": NOTE,
        "items": [tuple(q) for q in qs],
    })


def materialise_questions(spec):
    diffs = ["basic", "basic", "standard", "challenge"]
    made = []
    for diff, item in zip(diffs, spec["items"]):
        prompt, answer, wrongs, expl = item
        if len(wrongs) != 3:
            raise SystemExit("%s 干扰项必须是 3 个：%s" % (spec["key"], prompt[:30]))
        made.append({"d": diff, "t": "choice", "p": str(prompt).strip(), "a": str(answer).strip(),
                     "w": [str(w).strip() for w in wrongs], "e": str(expl).strip()})
    return made


_BANNED_START = re.compile(r"^(同一|上题|该题|同上)")
_BANNED_META = re.compile(r"本知识点|课标|是否要求")
_BANNED_COPY = re.compile("\u514d\u8d39|AI\\s*\u521d\u7a3f")


def check_question(key, q):
    if _BANNED_START.match(q["p"]):
        raise SystemExit("%s 题干以禁用词开头：%s" % (key, q["p"][:20]))
    blob = "\n".join([q["p"], q["e"], q["a"]] + q["w"])
    if _BANNED_META.search(blob):
        raise SystemExit("%s 出现禁用元问题用语" % key)
    if _BANNED_COPY.search(blob):
        raise SystemExit("%s 出现不该出现的字样" % key)
    opts = [q["a"]] + q["w"]
    if len(set(re.sub(r"\s+", "", o) for o in opts)) != 4 or not all(opts):
        raise SystemExit("%s 选项重复或为空：%s" % (key, opts))
    if not q["e"]:
        raise SystemExit("%s 缺少解析" % key)
