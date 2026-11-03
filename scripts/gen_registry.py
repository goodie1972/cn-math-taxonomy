#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 data/editions/registry.json —— 教材版本注册表。

版本不是内容层，是「同一批知识点排在哪一册哪一章」的映射层（见 docs/edition-mappings.md）。
所以每个学科挂进来的点，必须说清它是哪一种来源，不能只按册名同名就挂到别版名下：

  native   —— 池子（data/topics.json）本身就是按这套教材的目录编的，直接全量挂载。
              依据是各学科建库脚本自己写的编排版本，见 POOL_EDITION。
  mapping  —— 该版有真实对照表 data/mappings/<版本 id>.json，逐点登记该版的册/单元。
  borrowed —— 没有该版目录，只按「册键同名」把人教编排的点划成一个年级范围。
              章名、顺序都不是该版的，前端必须如实说明。

用法：python3 scripts/gen_registry.py [--check]
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS_PATH = os.path.join(ROOT, "data", "topics.json")
MAPPINGS_DIR = os.path.join(ROOT, "data", "mappings")
OUT_PATH = os.path.join(ROOT, "data", "editions", "registry.json")
REPORT_PATH = os.path.join(ROOT, "data", "editions", "registry_report.md")

SUBJ_CN = {
    "math": "数学", "english": "英语", "chinese": "语文", "physics": "物理",
    "science": "科学", "morality": "道德与法治", "history": "历史", "geography": "地理",
}
PREFIX2SUBJ = {
    "cne_": "english", "cnp_": "physics", "cnc_": "chinese", "cns_": "science",
    "cnd_": "morality", "cnh_": "history", "cng_": "geography",
}

# 池子各学科按哪套教材编排：逐条抄自本仓库建库脚本的自述，不是推测。
POOL_EDITION = {
    "math": ("renjiao", "小学按人教版 2024/2025/2026 修订目录逐节对齐（scripts/align_g*_toc.py），"
                      "初中按人教 2024，高中按人教 A 版（2019）必修与选择性必修。"),
    "english": ("renjiao", "小学按人教 PEP 三年级起点常见目录（scripts/en_build.py），"
                          "初中按人教版 Go for it!（scripts/enj_build.py），高中按人教版 2019（scripts/enh_build.py）。"
                          "三个脚本都注明「册次待核」，未逐页核对人教社目录。"),
    "physics": ("renjiao", "初中按人教版（2024/2025 修订）八上、八下、九全到节（scripts/phy_build.py）；"
                          "高中按人教版 2019 审定必修一二三、选必一二三，印次未逐册核对（scripts/phy_hs_build.py）。"),
    "geography": ("renjiao", "七上~八下按 2024 审定人教版目录（scripts/geo_build.py、scripts/geo_lib.py）。"),
    "chinese": ("tongbian", "一上~六下按统编教材 2024~2026 修订目录逐课覆盖（scripts/zh_build.py）。"),
    "history": ("tongbian", "七上~九下按统编《中国历史》2024~2026 修订目录；九下修订目录未上线，暂按现行统编（scripts/his_build.py）。"),
    "morality": ("tongbian", "一上~六下按统编《道德与法治》2024~2026 修订目录；四下、五下、六下按现行统编（scripts/mor_build.py）。"),
    "science": ("jiaoke", "一上~六下按教科版（教育科学出版社）2024~2026 修订目录；四下、五下、六下修订版未发行，暂按现行教科版（scripts/sci_build.py）。"),
}

# 借用范围：CSF（ChinaStudyFree）里挂在该版名下、但只按册键同名圈定的范围。
# CSF 的 outlines 是 LLM 归纳，不是教材目录；这些 id 的单元名与人教版逐条相同，
# 所以只能当「该年级段的知识点范围」，不能当该版的章次。
BORROWED = [
    ("cn_beishida", "北师大版", [
        ("math", ["一上", "七上", "八上"], "题源来自 CSF 北师大版目录（3 册），知识点落点按人教版册键圈定。"),
        ("english", ["三下", "必修一"], "题源来自 CSF 北师大版目录（2 册），单元名与人教版相同。"),
    ]),
    ("cn_zhejiao", "浙教版", [
        ("math", ["七上", "八上"], "题源来自 CSF 浙教版目录（2 册），落点按人教版册键圈定。浙教版初中数学实际 7 册（七上~九下 + 高中另算），其余册未取目录。"),
    ]),
    ("cn_sujiao", "苏教版", [
        ("math", ["一上", "八上"], "题源来自 CSF 苏教版目录（2 册）。注意：小学/高中数学才是苏教版（江苏凤凰教育出版社），"
                                   "初中数学是苏科版（江苏凤凰科学技术出版社），两者不能混挂，当前范围里含初中册，版本归属存疑。"),
    ]),
    ("cn_waiyan", "外研版", [
        ("english", ["三上", "三下", "七上", "八上", "必修一"],
         "题源来自 CSF 外研版与外研社版目录（两者同一出版社，已合并为一个版本）。"),
    ]),
    ("cn_yilin", "译林版", [
        ("english", ["三下", "七上", "八上", "必修一"], "题源来自 CSF 译林版目录（4 册），单元名与人教版相同。"),
    ]),
    ("hujiao54_junior", "沪教版（五四制）初中段", [
        ("math", ["六上", "七上"],
         "上海五四制的六年级是初中预备班，沪教版六上=有理数、简单的代数式、一元一次方程、线段与角。"
         "本范围取人教六上+七上（分数与圆、有理数、代数式、一元一次方程）作内容近似，"
         "约等于沪教版六上~七上，但章名与册次未与沪教版目录逐点对照。"),
    ]),
]


def subject_of(topic):
    s = topic.get("subject")
    if s in SUBJ_CN:
        return s
    tid = str(topic.get("id") or "")
    for p, s in PREFIX2SUBJ.items():
        if tid.startswith(p):
            return s
    return "math"


def norm_vol(raw):
    """把 chapter 首段归一成册键：一年级上册→一上、选择性必修第一册→选必一、高一/九全原样。"""
    v = (raw or "").strip()
    m = re.match(r"^(?:.*?)([一二三四五六七八九])年级(上|下)册", v)
    if m:
        return m.group(1) + m.group(2)
    m = re.search(r"选择性必修第([一二三四])册", v)
    if m:
        return "选必" + m.group(1)
    m = re.search(r"必修第([一二三四])册", v)
    if m:
        return "必修" + m.group(1)
    m = re.search(r"九全|全一册", v)
    if m:
        return "九全"
    return v


def load_pool():
    topics = json.load(open(TOPICS_PATH, encoding="utf-8"))
    by_subject = collections.defaultdict(list)
    by_vol = collections.defaultdict(list)
    for t in topics:
        if t.get("external"):
            continue
        s = subject_of(t)
        v = norm_vol((t.get("chapter") or "").strip().split(" ")[0])
        by_subject[s].append(t["id"])
        by_vol[(s, v)].append(t["id"])
    return topics, by_subject, by_vol


def edition_entry(subject, ids, origin, scope, evidence, status, placement=None, gap=""):
    d = {
        "label": SUBJ_CN[subject],
        "topicIds": ids,
        "scope": scope,
        "origin": origin,
        "status": status,
        "evidence": evidence,
    }
    if placement:
        d["placement"] = placement
    if gap:
        d["gap"] = gap
    return d


# 各真实对照表版本的补充说明（教材组合、学制差异这类无法从对照表本身推出来的信息）。
MAPPING_EXTRA_NOTE = {
    "hujiao_math": "上海另两科：语文=统编版（选「统编版」即可，全国同源）；"
                   "英语=沪教牛津上海版，本项目没有该版对照表——池子里的英语单元名来自人教 PEP 与 Go for it!，"
                   "不能当沪教牛津的目录用。五四制的六年级是初中预备班，与六三制「六年级=小学」不同名，"
                   "页内年级/册切换仍按六三制册次。",
    "sd54_math": "本版＝青岛出版社《义务教育教科书（五·四学制）》，山东五四制地区（烟台/威海/东营/泰安等）"
                 "小学 1–5 年级在用。五四制的初中段（六年级～九年级）数学不是青岛社这套，是鲁教版"
                 "（山东教育出版社），registry 里另立 lujiao54_junior；山东六三地区的青岛版另立 cn_qd63。"
                 "2026-11-03 订正：此前本条目误把山东全部「青岛版」格值（含六三制小学/初中与五四制初中）"
                 "都挂在自己名下。",
}

MAPPING_EXTRA_GAP = {
    # 五四制小学只有五年，人教池的六年级点（小学最后一年）在该版没有对应册次。
    "sd54_math": " 本版只到小学 1–5 年级（五四制小学五年），六三制青岛版属 cn_qd63、"
                 "五四制初中段属 lujiao54_junior；人教池六年级的 48 点在五四制口径下被摊到五下~六上，"
                 "本版与初中段都不圈它，是真实的归属空隙。",
}


def scope_text(subject, by_vol, pool_order):
    known = [v for v in pool_order[subject] if (subject, v) in by_vol]
    return "%d 册（%s）" % (len(known), " ".join(known)) if known else "无"


def build_native(by_subject, by_vol, pool_order):
    versions = []
    for vid, vlabel, system, extra_note in [
        ("cn_renjiao", "人教版", "六三制", "高中数学按人教 A 版（2019）。"),
        ("cn_tongbian", "统编版", "通用", "语文、历史、道德与法治全国统编，上海同样用这套。"),
        ("cn_jiaoke", "教科版", "六三制", "教育科学出版社《科学》，小学科学的主流版本。"),
    ]:
        owner = vid.replace("cn_", "")
        subs = {}
        for subj, (who, evidence) in POOL_EDITION.items():
            if who != owner:
                continue
            ids = by_subject[subj]
            subs[subj] = edition_entry(
                subj, ids, "native", scope_text(subj, by_vol, pool_order),
                evidence, "verified" if subj != "science" else "single-source",
                gap="" if subj != "science" else "编排版本按池子单元名与教科版目录比对得出，未做第二源逐册核对。")
        note = "本项目的知识点池子就是按这套教材的目录编排的，所以该学科全量挂载。%s" % extra_note
        versions.append({"id": vid, "label": vlabel, "system": system, "kind": "native",
                         "note": note, "subjects": subs})
    return versions


def build_from_mappings():
    versions = []
    for fn in sorted(os.listdir(MAPPINGS_DIR)) if os.path.isdir(MAPPINGS_DIR) else []:
        if not fn.endswith(".json") or ".example." in fn:
            continue
        path = os.path.join(MAPPINGS_DIR, fn)
        data = json.load(open(path, encoding="utf-8"))
        if data.get("status") == "example":
            continue
        edition = data.get("edition") or fn[:-5]
        subj = edition.split("_", 1)[1] if "_" in edition else "math"
        if subj not in SUBJ_CN:
            subj = "math"
        ids, placement, books, units = [], {}, collections.OrderedDict(), collections.OrderedDict()
        for e in data.get("entries") or []:
            tid = e.get("topicId")
            if not tid or tid in ids:
                continue
            ids.append(tid)
            book = "%d%s" % (e.get("grade", 0), e.get("term") or "")
            books.setdefault(book, 0)
            books[book] += 1
            if e.get("unit") or e.get("chapter") or e.get("note"):
                placement[tid] = {k: e[k] for k in ("grade", "term", "unit", "chapter", "note") if k in e}
            if e.get("unit"):
                units.setdefault(book, [])
                if e["unit"] not in units[book]:
                    units[book].append(e["unit"])
        if not ids:
            continue
        book_text = " ".join("%s(%d)" % (b, n) for b, n in sorted(books.items()))
        gap = ("对照表目前只覆盖 %s 共 %d 个知识点；该版其余册次没有逐点对照，选这个版本时不在范围内。"
               % (" ".join(sorted(books)), len(ids))
               + MAPPING_EXTRA_GAP.get(edition, ""))
        label = data.get("label") or edition
        if label.endswith(SUBJ_CN[subj]):
            label = label[: -len(SUBJ_CN[subj])].rstrip()
        versions.append({
            "id": edition,
            "label": label,
            "system": "五四制" if "54" in edition or edition.startswith("hujiao") else "六三制",
            "kind": "mapping",
            "note": "逐点对照该版教材目录登记，来源见 data/mappings/%s.json 的 source 字段。%s"
                    % (edition, MAPPING_EXTRA_NOTE.get(edition, "")),
            "source": data.get("source"),
            "mapping_status": data.get("status"),
            "subjects": {subj: edition_entry(
                subj, ids, "mapping",
                "该版册次：%s" % book_text,
                "data/mappings/%s（status=%s）" % (fn, data.get("status")),
                data.get("status") or "draft",
                placement=placement,
                gap=gap)},
        })
    for v in versions:
        if v.get("sd54_note"):
            v["note"] += u" " + v.pop("sd54_note")
    return versions


def build_borrowed(by_vol, pool_order):
    versions = []
    for vid, vlabel, rows in BORROWED:
        subs = {}
        for subj, vols, evidence in rows:
            ids = []
            for v in vols:
                for tid in by_vol.get((subj, v), []):
                    if tid not in ids:
                        ids.append(tid)
            if not ids:
                continue
            subs[subj] = edition_entry(
                subj, ids, "borrowed", "按人教版册键圈定：%s" % " ".join(vols),
                evidence, "borrowed",
                gap="该版的真实章次、单元顺序未取目录，年级归属可能与该版不一致（如五四制与六三制差一个学年）。")
        if not subs:
            continue
        versions.append({
            "id": vid, "label": vlabel,
            "system": "五四制" if ("54" in vid or vid.startswith("hujiao")) else "六三制",
            "kind": "borrowed",
            "note": "该版没有逐点对照表，这里只是「同年级知识点范围」：知识点集合可用，章名与册次按人教版，"
                    "不能当作该版教材的目录。",
            "subjects": subs,
        })
    return versions


def main():
    check = "--check" in sys.argv
    topics, by_subject, by_vol = load_pool()
    pool_order = {}
    for subj, ids in by_subject.items():
        seen = []
        for t in topics:
            if t.get("external") or subject_of(t) != subj:
                continue
            v = norm_vol((t.get("chapter") or "").strip().split(" ")[0])
            if v not in seen:
                seen.append(v)
        pool_order[subj] = seen

    native = build_native(by_subject, by_vol, pool_order)
    mapped = build_from_mappings()
    borrowed = build_borrowed(by_vol, pool_order)
    versions = native + mapped + borrowed

    registry = {
        "meta": {
            "title": "教材版本注册表",
            "note": "版本只决定「同一批知识点排在哪一册、哪一章」，不另建一套知识点。"
                    "每个学科带 origin：native=池子本就按这套教材编；mapping=有逐点对照表；"
                    "borrowed=只按人教册键圈的同年级范围，章名非该版。"
                    "年级仍由诊断页的通用设置控制；选了版本后按该版本登记的点出题。"
                    "上海（五四制）没有独立的「组合版」条目：数学选沪教版（小学段有真实对照，"
                    "初中段另有一条章次待对照的范围），语文选统编版，英语暂无沪教牛津对照表，用「按年级通用」。",
            "origin_legend": {
                "native": "知识点池按该版教材目录编排，可直接当该版使用。",
                "mapping": "有 data/mappings 逐点对照表，含该版的册次与单元名。",
                "borrowed": "无该版目录，仅按人教版册键圈定的同年级范围，章名与顺序非该版。",
            },
            "generated": "2026-11-03",
            "generator": "scripts/gen_registry.py",
            "corrections": [
                "2026-11-03 sd54_math：原条目同时挂着山东全部「青岛版」格值，把六三制青岛版与五四制青岛版"
                "混成一条，且五四制初中段数学（鲁教版，山东教育出版社）无处登记。"
                "现拆成 cn_qd63（青岛版六三制）/ sd54_math（青岛版五四制，小学 1–5 年级）/ "
                "lujiao54_junior（鲁教版五四制初中段）。"
                "证据：docs/province_textbook_map.md 的学段粒度订正表 + _scratch/province_map/luyu.md "
                "（烟台/东营 2025-2026 官方目录、青岛 2025 秋免费教科书目录）。",
            ],
            "source": "data/topics.json（池子编排版本见各学科建库脚本自述）+ data/mappings/*.json（逐点对照表）"
                      "+ ChinaStudyFree 目录（仅作题源，其 outlines 为 LLM 归纳，不作目录用）",
        },
        "versions": versions,
    }

    body = json.dumps(registry, ensure_ascii=False, indent=1)
    if check:
        old = open(OUT_PATH, encoding="utf-8").read() if os.path.exists(OUT_PATH) else ""
        print("CHANGED" if old != body else "UNCHANGED")
        return 0
    with io.open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(body)

    lines = [u"# registry 生成报告", u"", u"版本数：%d" % len(versions), u""]
    for v in versions:
        tot = sum(len(s["topicIds"]) for s in v["subjects"].values())
        lines.append(u"## %s | %s | %s | %s | 共 %d 点" % (v["id"], v["label"], v["kind"], v["system"], tot))
        lines.append(u"- note: %s" % v["note"])
        for subj, s in v["subjects"].items():
            lines.append(u"  - %s：%s ｜ origin=%s status=%s ｜ %s" % (subj, s["scope"], s["origin"], s["status"], s["evidence"]))
            if s.get("gap"):
                lines.append(u"    缺口：%s" % s["gap"])
        lines.append(u"")
    with io.open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(u"\n".join(lines))
    print("OK %d versions -> %s" % (len(versions), OUT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
