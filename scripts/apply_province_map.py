# -*- coding: utf-8 -*-
"""把「省 × 年级 → 版本」取证表落成 registry 可用的 borrowed 登记。

输入  _scratch/province_map/province_map.json（由 scripts/province_map_parse.py 产出）
      data/editions/registry.json、data/topics.json
输出  data/editions/registry.json（就地扩写）+ docs/registry_from_map.md（新增台账）

原则：没有该版该学科的目录，就不编章名。topicIds 只按人教池子的年级范围圈，
origin/status 一律 borrowed，并把证据来源（省、年级、取证置信度）写进条目。
"""
import io
import json
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_JSON = os.path.join(ROOT, "_scratch", "province_map", "province_map.json")
MAP_COPY = os.path.join(ROOT, "data", "editions", "province_map.json")
if not os.path.exists(MAP_JSON):
    MAP_JSON = MAP_COPY
REG = os.path.join(ROOT, "data", "editions", "registry.json")
TOPICS = os.path.join(ROOT, "data", "topics.json")
LEDGER = os.path.join(ROOT, "docs", "registry_from_map.md")

SUBJ_CN = {"math": "数学", "english": "英语", "chinese": "语文", "physics": "物理",
           "science": "科学", "morality": "道德与法治", "history": "历史",
           "geography": "地理"}
NO_POOL = {"chemistry": "化学", "biology": "生物", "politics": "政治", "information": "信息科技"}

# 规范化版名 → registry id。只给实际出现的版名建 slug。
SLUG = {
    "人教版": "cn_renjiao", "人教A版": "cn_renjiao_a", "人教B版": "cn_renjiao_b",
    "人教PEP": "cn_renjiao_pep", "人教精通版": "cn_renjiao_jingtong",
    "统编版": "cn_tongbian", "北师大版": "cn_beishida", "浙教版": "cn_zhejiao",
    "苏教版": "cn_sujiao", "苏科版": "cn_suke", "外研版": "cn_waiyan",
    "译林版": "cn_yilin", "教科版": "cn_jiaoke", "沪教版": "hujiao_math",
    "沪教牛津版": "cn_hujiao_oxford", "沪科版": "cn_huke", "沪科技版": "cn_hukeji",
    "沪粤版": "cn_huyue", "沪科粤教版": "cn_huke_yuejiao", "粤教版": "cn_yuejiao",
    "粤教沪外版": "cn_yuejiao_huwait", "科粤版": "cn_keyue", "粤人版": "cn_yueren",
    "湘教版": "cn_xiangjiao", "湘科版": "cn_xiangke", "湘鲁版": "cn_xianglu",
    "湘少版": "cn_xiangshao", "鲁教版": "cn_lujiao", "鲁科版": "cn_luke",
    # 「青岛版」不再单独指向某一条目：六三制与五四制是两套目录（青岛出版社都出），
    # 鲁教版数学只存在于五四制初中段。取证表必须写成带学制的显式版名，
    # 落到裸名「青岛版」时这里查不到 slug，会进台账的「未落地」而不是悄悄挂到五四制条目上。
    "青岛版（六三制）": "cn_qd63", "青岛版（五四制）": "sd54_math",
    "鲁教版（五四制）": "lujiao54_junior",
    "济南版": "cn_jinan", "冀教版": "cn_jijiao",
    "冀少版": "cn_jishao", "河北教版": "cn_hebeijiao", "河北人民版": "cn_hebeirenmin",
    "河北大学版": "cn_hebeidaxue", "北京课改版": "cn_beijingkaiban",
    "华东师大版": "cn_huadongshida", "西南师大版": "cn_xinan", "陕师大版": "cn_shanshida",
    "东北师大版": "cn_dongbeishida", "中图版": "cn_zhongtu", "中华地图学社版": "cn_zhonghuaditu",
    "星球版": "cn_xingqiu", "商务星球版": "cn_swxingqiu", "大象版": "cn_daxiang",
    "科普版": "cn_kepu", "科学版": "cn_kexue", "接力版": "cn_jieli",
    "闽教版": "cn_minjiao", "云教版": "cn_yunjiao", "川教版": "cn_chuanjiao",
    "黔教版": "cn_qianjiao", "武汉版": "cn_wuhan", "重大版": "cn_chongda",
    "地质版": "cn_dizhi", "语文版": "cn_yuwenban", "藏文版": "cn_zangwen",
    "岳麓版": "cn_yuelu", "人教版（藏汉双语）": "cn_renjiao_zang",
}

# 取证表点不到名的条目：某版的一条子范围，只在特定省区成立。
STATIC_PROVINCES = {
    "hujiao54_junior": {"math": ["上海"]},
}

# 同一出版社在不同学制下是两套书：新建版本条目时学制不能一律写「通用」。
SYSTEM_OF = {"cn_qd63": "六三制", "lujiao54_junior": "五四制", "cn_lujiao": "通用"}
NOTE_OF = {
    "cn_qd63": ("青岛出版社六三制系列，山东六三主体地区（济南、青岛主体、枣庄、德州、聊城、"
                "临沂、日照、菏泽）在用。没有逐点对照表，只按人教池同年级范围圈点；"
                "与青岛版（五四制，sd54_math）是两套目录。"),
    "lujiao54_junior": ("山东教育出版社《义务教育教科书（五·四学制）》初中段，烟台/威海/东营/泰安等"
                        "五四地区在用。数学册次是六年级～九年级（五四制初中四年），内容对应人教池 "
                        "7–9 年级册次；没有逐点对照表，只按人教年级范围圈点。"),
    "cn_lujiao": ("鲁教版（山东教育出版社）在义务教育阶段是五四学制（初中六~九年级）；"
                  "本条保留高中地理等跨学制通用的登记，五四制初中段数学另见 lujiao54_junior。"),
}
# 该版该学科相对人教年级键的真实册次，写进 gap 免得被当成小学口径。
SUBJECT_GAP = {
    ("sd54_math", "science"): " 五四制小学段为 1–5 年级，故不圈池子六年级的点。",
    ("lujiao54_junior", "math"): " 该版实际册次为六年级～九年级（五四制初中段），人教池 7–9 年级册次即其内容范围。",
    ("cn_qd63", "math"): " 与「青岛版（五四制）」（小学 1–5 年级）是两套目录，不可混用。",
    ("cn_lujiao", "english"): " 山东的义务教育段属五四制初中（六~九年级册次），本条只保留跨学制通用的部分。",
    ("cn_lujiao", "geography"): " 山东的义务教育段属五四制初中（六~九年级册次），本条只保留跨学制通用的部分。",
}
for _k in ("english", "physics", "geography", "science"):
    SUBJECT_GAP[("cn_qd63", _k)] = SUBJECT_GAP[("cn_qd63", "math")]


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def grade_bounds(gk):
    """取证表年级键 → 人教池子的 grade 取值集合。high 含全部高中档（>=10）。"""
    return "high" if gk == "high" else int(gk)


# 五四制初中四年（六年级～九年级）教人教 7–9 年级的内容：六年级是初中预备班，
# 人教池六年级（小学最后一年）在这套学制里没有对应册次。
# 只在版名自带「（五四制）」的切片上生效——混合学制省（山东）的六三制格子仍按原年级圈。
WU4_GRADE = {6: 7, 7: 8, 8: 9, 9: 9}


def pool_grades(canon, raw):
    if not canon.endswith(u"（五四制）"):
        return sorted(raw, key=lambda x: (x == "high", x))
    out = []
    for g in raw:
        v = WU4_GRADE.get(g, g)
        if v not in out:
            out.append(v)
    return sorted(out, key=lambda x: (x == "high", x))


def main():
    pm = load(MAP_JSON)["provinces"]
    reg = load(REG)
    topics = load(TOPICS)
    items = topics if isinstance(topics, list) else topics.get("topics")

    def subj_of(t):
        s = t.get("subject")
        if s:
            return s
        p = t["id"].split("_")[0]
        return {"cnm": "math"}.get(p, p)

    by_subj_grade = collections.defaultdict(list)
    for t in items:
        s = subj_of(t)
        g = t.get("grade")
        if s in SUBJ_CN and isinstance(g, int):
            by_subj_grade[(s, "high" if g >= 10 else g)].append(t["id"])

    # (canon, subject) → grades / provinces
    agg = collections.defaultdict(lambda: {"grades": set(), "prov": set()})
    for pname, pd in pm.items():
        for gk, subs in (pd.get("grades") or {}).items():
            for s, vs in subs.items():
                for c in vs:
                    a = agg[(c, s)]
                    a["grades"].add(grade_bounds(gk))
                    a["prov"].add(pname)

    have = {v["id"] for v in reg["versions"]}
    reg_by_id = {v["id"]: v for v in reg["versions"]}
    new_rows, skipped_nopool, merged = [], [], []

    for (canon, s), a in sorted(agg.items()):
        if s in NO_POOL:
            skipped_nopool.append((canon, s, a))
            continue
        if s not in SUBJ_CN:
            continue
        vid = SLUG.get(canon)
        if vid is None:
            merged.append(("无 slug", canon, s, a))
            continue
        pool_ids = []
        pg = pool_grades(canon, a["grades"])
        for g in pg:
            pool_ids += by_subj_grade.get((s, g), [])
        if not pool_ids:
            merged.append(("池子该学科该年级无点", canon, s, a))
            continue
        seen, ids = set(), []
        for i in pool_ids:
            if i not in seen:
                seen.add(i)
                ids.append(i)
        grades_txt = "、".join("高中" if g == "high" else "%d 年级" % g for g in pg)
        if vid in have and s in reg_by_id[vid]["subjects"]:
            sd = reg_by_id[vid]["subjects"][s]
            sd["provinces"] = sorted(set(sd.get("provinces") or []) | a["prov"])
            # 只有 borrowed（本就无目录、按人教年级圈范围）才随取证表加宽；
            # native / mapping 的点是逐册对照出来的，不能被省份表改写。
            if sd.get("origin") == "borrowed":
                before = len(sd.get("topicIds") or [])
                ids = list(sd.get("topicIds") or [])
                seen = set(ids)
                for g in pg:
                    for i in by_subj_grade.get((s, g), []):
                        if i not in seen:
                            seen.add(i)
                            ids.append(i)
                if len(ids) != before:
                    gtxt = "、".join("高中" if g == "high" else "%d 年级" % g for g in pg)
                    sd["topicIds"] = ids
                    sd["scope"] = ("按人教版册键圈定（题源）+ 省份取证表加宽至：%s（共 %d 点）" % (gtxt, len(ids)))
                    sd["gap"] = (sd.get("gap") or "") + " 年级范围按省份取证表加宽，加宽的点没有该版目录。"
            continue
        if vid not in have:
            v = {"id": vid, "label": canon,
                 "system": SYSTEM_OF.get(vid, "通用"), "kind": "borrowed",
                 "note": NOTE_OF.get(vid, "由省份取证表登记：该版该学科无目录对照，只圈人教池子的同年级范围。"),
                 "subjects": {}}
            reg["versions"].append(v)
            reg_by_id[vid] = v
            have.add(vid)
        v = reg_by_id[vid]
        base = v["id"].split("_")[0]
        v["subjects"][s] = {
            "label": SUBJ_CN[s],
            "scope": "按人教册键圈定：%s（%d 点）" % (grades_txt, len(ids)),
            "origin": "borrowed",
            "status": "borrowed",
            "evidence": "来源=docs/province_textbook_map.md（省×年级取证，附 URL 与置信度）；使用省区 %d 个。" % len(a["prov"]),
            "gap": ("该版该学科未取教材目录，章名与册次沿用人教版；年级归属可能与该版差一个学年（五四制尤甚）。"
                    + SUBJECT_GAP.get((vid, s), "")),
            "provinces": sorted(a["prov"]),
            "topicIds": ids,
        }
        new_rows.append((canon, s, len(ids), grades_txt, sorted(a["prov"])))

    # 取证表点不到名的条目：某版的一条子范围，只在特定省区成立
    for vid, subs in STATIC_PROVINCES.items():
        v = reg_by_id.get(vid)
        if not v:
            continue
        for s, provs in subs.items():
            sd = (v.get("subjects") or {}).get(s)
            if sd:
                sd["provinces"] = provs

    reg["meta"]["generated"] = "2026-11-04"
    reg["meta"]["province_map"] = "docs/province_textbook_map.md；provinces 字段=该版该学科在取证表里出现于哪些省"
    json.dump(reg, io.open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 取证矩阵入库：_scratch 不进版本库，registry 要能重建
    json.dump({"generated_from": "scripts/province_map_parse.py",
               "note": "省 × 年级 → 该省在用的版本集合；格值空数组=取证未核",
               "provinces": pm},
              io.open(MAP_COPY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    out = ["# 由省份取证表落地的 registry 登记", "",
           "取证表里每个「版本 × 学科」落到哪条 registry 登记、圈了多少点、被哪些省用到。",
           "本表由 registry 现状回推，重复跑不会清空（`来源`：native=有教材目录逐册对照，"
           "mapping=逐点对照且只覆盖部分册次，borrowed=无目录、按人教年级范围圈点）。", "",
           "| 版本 | 学科 | 点数 | 年级范围 | 使用省区 | 来源 |", "|---|---|---|---|---|---|"]
    ledger_rows = []
    for (canon, s), a in sorted(agg.items()):
        if s not in SUBJ_CN or s in NO_POOL:
            continue
        v = reg_by_id.get(SLUG.get(canon, ""))
        sd = ((v or {}).get("subjects") or {}).get(s)
        if not sd or not sd.get("topicIds"):
            continue
        gtxt = "、".join("高中" if g == "high" else "%d 年级" % g for g in pool_grades(canon, a["grades"]))
        ledger_rows.append((canon, s, len(sd["topicIds"]), gtxt,
                            sorted(sd.get("provinces") or []), sd.get("origin", "?")))
    for canon, s, n, gtxt, provs, origin in sorted(ledger_rows, key=lambda r: (-r[2], r[0])):
        out.append("| %s | %s | %d | %s | %s | %s |" % (canon, SUBJ_CN[s], n, gtxt, " ".join(provs), origin))
    out += ["", "## 池子里没有的学科（无法登记，属知识点缺口不是版本缺口）", ""]
    agg2 = collections.defaultdict(set)
    for (canon, s), a in agg.items():
        if s in NO_POOL:
            agg2[s].add(canon)
    out.append("、".join("%s（涉及 %d 个版名）" % (NO_POOL[s], len(c)) for s, c in sorted(agg2.items())))
    if merged:
        out += ["", "## 未落地的", ""]
        for reason, canon, s, a in merged:
            out.append("- %s × %s：%s（%d 省）" % (canon, s, reason, len(a["prov"])))
    io.open(LEDGER, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("new=%d versions=%d nopool=%d unmapped=%d" % (len(new_rows), len(reg["versions"]), len(skipped_nopool), len(merged)))


if __name__ == "__main__":
    main()
