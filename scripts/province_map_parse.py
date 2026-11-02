#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 _scratch/province_map/*.md 的省级教材取证结果，产出结构化数据。

用法：
  python3 scripts/province_map_parse.py            # 解析并打印统计
  python3 scripts/province_map_parse.py --dump     # 额外写 _scratch/province_map/parsed.json
"""
import io
import json
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "_scratch", "province_map")

SUBJECT_ALIAS = {
    "数学": "math", "英语": "english", "语文": "chinese", "物理": "physics",
    "化学": "chemistry", "生物": "biology", "地理": "geography", "历史": "history",
    "道德与法治": "morality", "思想政治": "politics", "政治": "politics",
    "科学": "science", "小学科学": "science", "信息科技": "it", "信息技术": "it",
    "历史与社会": "history_society", "艺术": "art", "音乐": "music", "美术": "fine_art",
    "体育": "pe", "劳动": "labor", "书法": "calligraphy", "藏语文": "tibetan",
}
STAGE_GRADES = {
    "小学": ["1", "2", "3", "4", "5", "6"],
    "初中": ["7", "8", "9"],
    "高中": ["10", "11", "12"],
}


def split_row(line):
    """按未转义的 | 切分表格行。"""
    s = line.strip().strip("|")
    cells, buf = [], ""
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(buf.strip())
            buf = ""
            i += 1
            continue
        buf += s[i]
        i += 1
    cells.append(buf.strip())
    return cells


def subjects_of(cell):
    out = []
    for raw in re.split(r"[·、,，/]|＋|\+", cell):
        raw = re.sub(r"（[^）]*）", "", raw).strip()
        if not raw:
            continue
        for key, sid in SUBJECT_ALIAS.items():
            if key in raw:
                if sid not in out:
                    out.append(sid)
                break
    return out


def stages_of(cell):
    s = cell.replace(" ", "")
    out = []
    for stage in ("小学", "初中", "高中"):
        if stage in s:
            out.append(stage)
    if "义务" in s or "义教" in s:
        out += ["小学", "初中"]
    if not out or "各学段" in s or "全部" in s or "所有" in s or s in ("—", "-"):
        out = ["小学", "初中", "高中"]
    seen, res = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


VERSION_RE = re.compile(r"([A-Za-z\u4e00-\u9fa5·（）()]{1,12}版)")
EDITION_BLACKLIST = {"版", "出版", "第一版", "新版", "旧版", "本版", "统版本"}

# 规范化词典：命中顺序即优先级（具体的在前，泛化的「人教版」垫底）。
CANON = [
    ("人教A版", "人教A版"), ("人教B版", "人教B版"), ("数学(A版", "人教A版"),
    ("人教PEP", "人教PEP"), ("PEP", "人教PEP"), ("人教精通", "人教精通版"),
    ("人教部编", "统编版"), ("统编", "统编版"), ("部编", "统编版"),
    ("沪教牛津", "沪教牛津版"), ("牛津上海", "沪教牛津版"), ("牛津", "沪教牛津版"),
    ("沪科粤教", "沪科粤教版"), ("沪粤", "沪粤版"), ("粤教沪外", "粤教沪外版"),
    ("沪科技", "沪科技版"), ("沪科", "沪科版"), ("上海教育", "沪教版"), ("沪教", "沪教版"),
    ("北师大", "北师大版"), ("苏科", "苏科版"), ("苏教版", "苏教版"),
    ("浙科", "浙科版"), ("浙教", "浙教版"), ("外研", "外研版"), ("译林", "译林版"),
    ("鲁科", "鲁科版"), ("鲁教", "鲁教版"), ("冀少", "冀少版"), ("冀教", "冀教版"),
    ("湘鲁", "湘鲁版"), ("湘科", "湘科版"), ("湘少", "湘少版"), ("岳麓", "岳麓版"),
    ("湘教", "湘教版"), ("商务星球", "商务星球版"), ("星球", "星球版"),
    ("中图", "中图版"), ("中华地图", "中华地图学社版"),
    ("教科", "教科版"), ("济南版", "济南版"), ("闽教", "闽教版"),
    ("科粤", "科粤版"), ("粤人", "粤人版"), ("粤教", "粤教版"), ("科普版", "科普版"),
    ("接力", "接力版"), ("青岛", "青岛版"), ("北京课改", "北京课改版"),
    ("北京版", "北京课改版"), ("华东师大", "华东师大版"), ("华师", "华东师大版"),
    ("西南师大", "西南师大版"), ("西师", "西南师大版"), ("武汉出版社", "武汉版"),
    ("重大", "重大版"), ("川教", "川教版"), ("云教版", "云教版"), ("云南教育", "云教版"),
    ("贵州教育", "黔教版"), ("陕师大", "陕师大版"), ("大象", "大象版"),
    ("山东教育", "鲁教版"), ("江苏教育", "苏教版"),
    ("河北教育", "河北教版"), ("河北大学", "河北大学版"), ("河北人民", "河北人民版"),
    ("地质", "地质版"), ("语文版", "语文版"), ("西藏", "藏文版"),
    ("人教版", "人教版"), ("人民教育", "人教版"),
]



def versions_of(cell):
    """从自由文本里抽出版本名（含出版社括号的，一并记下出版社）。"""
    found = []
    for m in VERSION_RE.finditer(cell):
        name = m.group(1)
        if name in EDITION_BLACKLIST or len(name) < 2:
            continue
        if any(name.endswith(bad) for bad in ("出版社", "出版", "课本", "教材")):
            continue
        tail = cell[m.end():m.end() + 1]
        pub = ""
        pm = re.match(r"[（(]([^）]{2,40})[）)]", cell[m.end():])
        if pm:
            pub = pm.group(1)
        if name not in [f[0] for f in found]:
            found.append((name, pub, tail != ""))
    return found


NON_PROVINCE = ("证据最弱", "直接含义", "小结", "来源", "索引", "说明", "方法",
                "结论", "总览", "附录", "未决", "待办", "判据")


def parse_file(path):
    txt = io.open(path, encoding="utf-8").read()
    provs, meta = [], {}
    cur = None
    for line in txt.splitlines():
        m = re.match(r"^## (.+)$", line)
        if m:
            name = m.group(1).strip()
            if any(k in name for k in NON_PROVINCE):
                cur = None
                continue
            cur = {"province": name, "meta": {}, "rows": []}
            provs.append(cur)
            continue
        if cur is None:
            continue
        mb = re.match(r"^-\s*(学制|英语起始年级|换版状态)[:：]\s*(.*)$", line)
        if mb:
            cur["meta"][mb.group(1)] = mb.group(2).strip()
            continue
        if line.strip().startswith("|"):
            cells = split_row(line)
            if len(cells) < 6:
                continue
            if cells[0] in ("学段",) or set(cells[0]) <= set("-: "):
                continue
            cur["rows"].append(cells)
    return provs


def canon_of(text):
    """自由文本 -> 规范版本名集合。"""
    hits = []
    for pat, name in CANON:
        if pat in text and name not in hits:
            hits.append(name)
    return hits


SUBJECT_CN = {"math": "数学", "english": "英语", "chinese": "语文", "physics": "物理",
              "chemistry": "化学", "biology": "生物", "geography": "地理", "history": "历史",
              "morality": "道法", "politics": "政治", "science": "科学", "it": "信息科技",
              "other": "其他"}


def grade_stage_map(meta):
    """按该省学制，把年级 1~9 归到学段。五四制：1-5 小学、6-9 初中。"""
    s = (meta.get("学制") or "")
    wu4 = "五四" in s and "混合" not in s and "并存" not in s
    return {g: ("小学" if (g <= (5 if wu4 else 6)) else "初中") for g in range(1, 10)}, wu4


def cell_versions(cell, prov, subj, stage):
    v = cell.get((prov, subj, stage))
    if not v:
        return None, None
    return sorted(v["main"] | v["other"]), v["conf"]


def render_cell(cell, prov, subj, grade, meta):
    gsmap, wu4 = grade_stage_map(meta)
    if grade == "high":
        stage = "高中"
    else:
        stage = gsmap[grade]
        if subj == "english" and "三年级" in (meta.get("英语起始年级") or "") and grade <= 2:
            return "—（三年级起点）", None
    vers, conf = cell_versions(cell, prov, subj, stage)
    if not vers:
        return "未核", {"低"}
    weak = "†" if conf and ("低" in conf or any(c not in ("高", "中") for c in conf)) else ""
    return "/".join(vers) + weak, conf


REGISTRY_OF = {
    "人教版": "cn_renjiao", "人教A版": "cn_renjiao", "人教PEP": "cn_renjiao",
    "统编版": "cn_tongbian", "教科版": "cn_jiaoke",
    "沪教版": "hujiao_math", "北师大版": "cn_beishida", "浙教版": "cn_zhejiao",
    "苏教版": "cn_sujiao", "外研版": "cn_waiyan", "译林版": "cn_yilin",
    "青岛版": "sd54_math",
}
# 同一出版社的另一套目录：registry 里有该出版社的池子，但这套本身没建
SAME_PUBLISHER = {"人教B版": "人教（B 版未建）", "人教精通版": "人教（精通本未建）",
                  "语文版": "旧版语文课本（已被统编替代）"}


def registry_status(reg, canon, subj):
    ids = [v["id"] for v in reg["versions"] if v.get("label") == canon]
    rid = REGISTRY_OF.get(canon)
    if rid:
        ids.append(rid)
    for vid in ids:
        v = [x for x in reg["versions"] if x["id"] == vid]
        if not v:
            continue
        sub = (v[0].get("subjects") or {}).get(subj)
        if sub and sub.get("topicIds"):
            return "已登记（%d 点，%s）" % (len(sub["topicIds"]), sub.get("origin", "?"))
    if ids:
        return "有版本·该学科未建"
    return SAME_PUBLISHER.get(canon, "无版本")


def emit_durable(prov_meta, cell, need, need_prov, registry, outdir_docs, out_json):
    provinces = sorted(prov_meta)
    lines = ["# 省份 × 年级 → 教材版本（选用地图）", "",
             "> 由 `scripts/province_map_parse.py` 从 `_scratch/province_map/*.md` 汇总生成。",
             "> 每格是该省该年级该学科**在用的版本集合**，含主流与并存版本；",
             "> `†` = 该格证据只到地市/自媒体级或来源互斥，未达两源互核；`未核` = 没取到证据。",
             "> 版本归属证据：省级/地市级教育行政部门《教学用书目录》《教材选用结果公告》与出版社公告，逐格带 URL。",
             ""]
    lines.append("## 〇、学制与英语起始年级")
    lines.append("")
    lines.append("| 省/区 | 学制 | 英语起始年级 | 2026 换版状态 |")
    lines.append("|---|---|---|---|")
    for p in provinces:
        m = prov_meta[p]
        lines.append("| %s | %s | %s | %s |" % (p, m.get("学制", "—"), m.get("英语起始年级", "—"),
                                                (m.get("换版状态", "—"))[:80]))
    lines.append("")
    lines.append("### 年级 ↔ 池子册次")
    lines.append("")
    lines.append("- 六三制省份：该省 N 年级 = 池子里的人教 N 年级册次（一上~九下），无偏移。")
    lines.append("- 五四制省份（上海、山东烟台/威海/东营、黑龙江哈尔滨城区等）：**六年级属初中（预备班）**，"
                  "该省六年级 = 池子里的人教七年级（七上/七下），七年级=八上/八下，八年级=九上/九下，"
                  "八年级期末即学完初中内容，九年级多出一年用于复习与高中先修。")
    lines.append("- 因此同一套知识点池，五四制省的年级标签要整体下移一个学年；这一偏移属于「版本 = 归属层」，"
                  "不需要重建知识点。")
    lines.append("")
    tables = [("一、数学", "math", True), ("二、英语", "english", True),
              ("三、物理", "physics", False), ("四、化学", "chemistry", False),
              ("五、生物", "biology", False), ("六、地理", "geography", False),
              ("七、科学（含小学科学/初中科学）", "science", False),
              ("八、语文（全国统编）", "chinese", False),
              ("九、历史（全国统编）", "history", False),
              ("十、道德与法治 / 思想政治（全国统编）", "morality", False)]
    for title, subj, primary in tables:
        lines.append("## %s" % title)
        lines.append("")
        lines.append("| 省/区 | 一 | 二 | 三 | 四 | 五 | 六 | 七 | 八 | 九 | 高中 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for p in provinces:
            row = [p]
            for g in list(range(1, 10)) + ["high"]:
                txt, _ = render_cell(cell, p, subj, g, prov_meta[p])
                row.append(txt)
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    # registry 对账
    lines.append("## 十一、registry 对账：需要哪些版本、现在有没有")
    lines.append("")
    lines.append("| 版本（取证出现） | 涉及省数 | 涉及学科 | 数学 | 英语 | 物理 | 化学 | 生物 | 地理 | 科学 | 语文 | 历史 | 道法 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    subj_all = ["math", "english", "physics", "chemistry", "biology", "geography",
                "science", "chinese", "history", "morality"]
    ver_subj = collections.defaultdict(set)
    for (prov, subj, stage), v in cell.items():
        for e in (v["main"] | v["other"]):
            ver_subj[e].add(subj)
    for name, n in need.most_common():
        subs = [s for s in subj_all if s in ver_subj[name]]
        cols = []
        for s in subj_all:
            if s not in subs:
                cols.append("—")
            else:
                cols.append(registry_status(registry, name, s))
        lines.append("| %s | %d | %d | %s |" % (name, n, len(subs), " | ".join(cols)))
    lines.append("")
    # 覆盖判定：以「该学科在池子里有点」为前提，看每格现在能不能选到版本
    pool_subj = set()
    for v in registry["versions"]:
        for s, e in (v.get("subjects") or {}).items():
            if e.get("topicIds"):
                pool_subj.add(s)
    total = ok = unknown = 0
    gap_pairs = collections.defaultdict(set)
    for (prov, subj, stage), v in cell.items():
        if subj not in pool_subj:
            continue
        vers = v["main"] | v["other"]
        total += 1
        if not vers:
            unknown += 1
            continue
        usable = [e for e in vers if registry_status(registry, e, subj).startswith("已登记")]
        if usable:
            ok += 1
        for e in vers:
            if not registry_status(registry, e, subj).startswith("已登记"):
                gap_pairs[(e, subj)].add(prov)
    lines.append("### 覆盖判定")
    lines.append("")
    lines.append("- 已建库学科：%s" % "、".join(sorted(SUBJECT_CN.get(s, s) for s in pool_subj)))
    lines.append("- 未建库学科（本表里必然全是「有版本·该学科未建」）：%s"
                 % "、".join(sorted(SUBJECT_CN.get(s, s) for s in
                                    {"chemistry", "biology", "politics", "it"} )))
    lines.append("- 落在已建库学科上的格子：**%d** 格，其中现在就能选到已登记版本的 **%d** 格（%.0f%%），"
                  "取证未核 %d 格。" % (total, ok, 100.0 * ok / max(total, 1), unknown))
    lines.append("- 要每格都有版本可选，需要新增的「版本 × 学科」登记：**%d** 对（多数按同年级范围先落成 borrowed）。"
                 % len(gap_pairs))
    lines.append("")
    lines.append("| 需新增（版本 × 学科） | 涉及省 | 涉及省数 |")
    lines.append("|---|---|---|")
    for (e, s), ps in sorted(gap_pairs.items(), key=lambda x: (-len(x[1]), x[0][0])):
        lines.append("| %s × %s | %s | %d |" % (e, SUBJECT_CN.get(s, s), " ".join(sorted(ps)), len(ps)))
    lines.append("")
    io.open(outdir_docs, "w", encoding="utf-8").write("\n".join(lines))
    data = {"generated_from": "scripts/province_map_parse.py",
            "note": "格值为该省该年级在用的版本集合；confidence 取自取证表",
            "provinces": {}}
    for p in provinces:
        gsmap, wu4 = grade_stage_map(prov_meta[p])
        entry = {"system": "五四制" if wu4 else "六三制",
                 "meta": prov_meta[p], "grades": {}}
        for g in range(1, 10):
            stage = gsmap[g]
            entry["grades"][str(g)] = {
                s: (cell_versions(cell, p, s, stage)[0] or [])
                for s in subj_all}
        entry["grades"]["high"] = {s: (cell_versions(cell, p, s, "高中")[0] or [])
                                   for s in subj_all}
        data["provinces"][p] = entry
    io.open(out_json, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))


def main():
    files = sorted(f for f in os.listdir(SRC_DIR)
                   if f.endswith(".md") and not f.startswith("_") and f != "matrix.md")
    all_rows = []
    prov_meta = {}
    for f in files:
        for p in parse_file(os.path.join(SRC_DIR, f)):
            prov_meta[p["province"]] = p["meta"]
            for cells in p["rows"]:
                stage_cell, subj_cell, main_v, other_v, src, conf = cells[:6]
                for subj in subjects_of(subj_cell) or ["other"]:
                    for stage in stages_of(stage_cell):
                        all_rows.append({
                            "province": p["province"], "stage": stage, "subject": subj,
                            "main_raw": main_v, "other_raw": other_v,
                            "source": src, "confidence": conf,
                            "main_versions": versions_of(main_v),
                            "other_versions": versions_of(other_v),
                            "canon_main": canon_of(main_v),
                            "canon_other": canon_of(other_v),
                        })
    # 每（省, 学科, 学段）的候选版本全集
    cell = collections.defaultdict(lambda: {"main": set(), "other": set(), "conf": set(), "src": 0})
    for r in all_rows:
        # 语文/历史/道德与法治（思想政治）全国统一统编，取证里常写作「人教版（统编）」，归一
        if r["subject"] in ("chinese", "history", "morality", "politics"):
            r["canon_main"] = ["统编版"] if r["canon_main"] or r["canon_other"] else []
            r["canon_other"] = []
        k = (r["province"], r["subject"], r["stage"])
        cell[k]["main"] |= set(r["canon_main"])
        cell[k]["other"] |= set(r["canon_other"])
        cell[k]["conf"].add(r["confidence"][:1])
        cell[k]["src"] += 1
    need = collections.Counter()
    need_prov = collections.defaultdict(set)
    for (prov, subj, stage), v in cell.items():
        for e in (v["main"] | v["other"]):
            need[e] += 1
            need_prov[e].add(prov)
    out = ["取证文件=%d 省区=%d 记录=%d 单元格(省×学科×学段)=%d"
           % (len(files), len(prov_meta), len(all_rows), len(cell)),
           "省份: " + " ".join(sorted(prov_meta)), "",
           "规范化后的版本全集（出现格数 / 省数）:"]
    for name, n in need.most_common():
        out.append("  %-14s %3d / %2d" % (name, n, len(need_prov[name])))
    io.open(os.path.join(SRC_DIR, "_tokens.md"), "w", encoding="utf-8").write("\n".join(out))

    # 合并矩阵：按省输出「学科 × 学段 -> 版本」，供人读
    lines = ["# 省 × 学段 × 学科 -> 教材版本（取证合并表）", "",
             "> 由 scripts/province_map_parse.py 从 _scratch/province_map/*.md 生成；",
             "> 主流版本 = 省内多数地区选用；括号内是该省并存的其他版本。", ""]
    for prov in sorted(prov_meta):
        meta = prov_meta[prov]
        lines.append("## %s" % prov)
        for key in ("学制", "英语起始年级", "换版状态"):
            if meta.get(key):
                lines.append("- %s：%s" % (key, meta[key]))
        lines.append("")
        lines.append("| 学科 | 学段 | 主流版本 | 并存版本 | 置信度 |")
        lines.append("|---|---|---|---|---|")
        order = ["math", "english", "chinese", "physics", "chemistry", "biology",
                 "geography", "history", "morality", "politics", "science", "it", "other"]
        for subj in order:
            for stage in ("小学", "初中", "高中"):
                v = cell.get((prov, subj, stage))
                if not v:
                    continue
                main = "、".join(sorted(v["main"])) or "—"
                other = "、".join(sorted(v["other"] - v["main"])) or "—"
                lines.append("| %s | %s | %s | %s | %s |" %
                             (SUBJECT_CN.get(subj, subj), stage, main, other,
                              "/".join(sorted(v["conf"])) or "—"))
        lines.append("")
    io.open(os.path.join(SRC_DIR, "matrix.md"), "w", encoding="utf-8").write("\n".join(lines))
    json.dump({"rows": all_rows,
               "cells": {"|".join(k): {"main": sorted(v["main"]), "other": sorted(v["other"]),
                                        "conf": sorted(v["conf"])} for k, v in cell.items()}},
              io.open(os.path.join(SRC_DIR, "parsed.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    reg = json.load(io.open(os.path.join(ROOT, "data", "editions", "registry.json"), encoding="utf-8"))
    emit_durable(prov_meta, cell, need, need_prov, reg,
                 os.path.join(ROOT, "docs", "province_textbook_map.md"),
                 os.path.join(ROOT, "_scratch", "province_map", "province_map.json"))
    print("cells=%d canon_editions=%d" % (len(cell), len(need)))



if __name__ == "__main__":
    main()
