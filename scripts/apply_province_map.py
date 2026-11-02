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
    "青岛版": "sd54_math", "济南版": "cn_jinan", "冀教版": "cn_jijiao",
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


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def grade_bounds(gk):
    """取证表年级键 → 人教池子的 grade 取值集合。high 含全部高中档（>=10）。"""
    return "high" if gk == "high" else int(gk)


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
        for g in sorted(a["grades"], key=lambda x: (x == "high", x)):
            pool_ids += by_subj_grade.get((s, g), [])
        if not pool_ids:
            merged.append(("池子该学科该年级无点", canon, s, a))
            continue
        seen, ids = set(), []
        for i in pool_ids:
            if i not in seen:
                seen.add(i)
                ids.append(i)
        grades_txt = "、".join("高中" if g == "high" else "%d 年级" % g
                              for g in sorted(a["grades"], key=lambda x: (x == "high", x)))
        if vid in have and s in reg_by_id[vid]["subjects"]:
            sd = reg_by_id[vid]["subjects"][s]
            sd["provinces"] = sorted(set(sd.get("provinces") or []) | a["prov"])
            # 只有 borrowed（本就无目录、按人教年级圈范围）才随取证表加宽；
            # native / mapping 的点是逐册对照出来的，不能被省份表改写。
            if sd.get("origin") == "borrowed":
                before = len(sd.get("topicIds") or [])
                ids = list(sd.get("topicIds") or [])
                seen = set(ids)
                for g in sorted(a["grades"], key=lambda x: (x == "high", x)):
                    for i in by_subj_grade.get((s, g), []):
                        if i not in seen:
                            seen.add(i)
                            ids.append(i)
                if len(ids) != before:
                    gtxt = "、".join("高中" if g == "high" else "%d 年级" % g
                                     for g in sorted(a["grades"], key=lambda x: (x == "high", x)))
                    sd["topicIds"] = ids
                    sd["scope"] = ("按人教版册键圈定（题源）+ 省份取证表加宽至：%s（共 %d 点）" % (gtxt, len(ids)))
                    sd["gap"] = (sd.get("gap") or "") + " 年级范围按省份取证表加宽，加宽的点没有该版目录。"
            continue
        if vid not in have:
            v = {"id": vid, "label": canon, "system": "通用", "kind": "borrowed",
                 "note": "由省份取证表登记：该版该学科无目录对照，只圈人教池子的同年级范围。",
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
            "gap": "该版该学科未取教材目录，章名与册次沿用人教版；年级归属可能与该版差一个学年（五四制尤甚）。",
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

    reg["meta"]["generated"] = "2026-11-03"
    reg["meta"]["province_map"] = "docs/province_textbook_map.md；provinces 字段=该版该学科在取证表里出现于哪些省"
    json.dump(reg, io.open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 取证矩阵入库：_scratch 不进版本库，registry 要能重建
    json.dump({"generated_from": "scripts/province_map_parse.py",
               "note": "省 × 年级 → 该省在用的版本集合；格值空数组=取证未核",
               "provinces": pm},
              io.open(MAP_COPY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    out = ["# 由省份取证表新增的 registry 登记（borrowed）", "",
           "共新增 **%d** 条「版本 × 学科」。每条只圈人教池子的同年级范围，不编该版章名。" % len(new_rows), "",
           "| 版本 | 学科 | 圈定点数 | 年级范围 | 使用省区 |", "|---|---|---|---|---|"]
    for canon, s, n, gtxt, provs in sorted(new_rows, key=lambda r: (-r[2], r[0])):
        out.append("| %s | %s | %d | %s | %s |" % (canon, SUBJ_CN[s], n, gtxt, " ".join(provs)))
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
