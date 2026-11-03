# -*- coding: utf-8 -*-
"""补题碎片体检：入库之前把「答案格式自相矛盾、verify 只是抄答案、同型换数」这类硬伤挑出来。

qgen_merge.py 只卡字段和去重，verify_questions.py 只保证 verify 求值等于 answer；
两者都放行过一条「题干要求最简分数、答案却写成 13 位小数分数」的题，所以这里补一层内容级检查。

用法：
  python3 scripts/qgen_lint.py                 # 检查 _scratch/qgen/out/*.json
  python3 scripts/qgen_lint.py math_junior_01.json   # 只检查某个碎片

报告写 _scratch/qgen/lint_report.md（UTF-8）。stdout 只出 ASCII 计数，避免 Git Bash 乱码。
"""
import ast
import io
import json
import math
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_questions as VQ  # noqa: E402
import validate as V  # noqa: E402

QG = os.path.join(ROOT, "_scratch", "qgen")
SRC = os.path.join(QG, "out")
MERGED = os.path.join(QG, "merged")
REPORT = os.path.join(QG, "lint_report.md")

Q_FIELDS = V.Q_FIELDS
REQUIRED = ("topicId", "difficulty", "type", "prompt", "answer", "explanation")
PUNCT = re.compile(r"[\s，。、；：！？“”‘’（）《》,.;:!?'\"()\[\]{}\-—…]+")
FRAC_RE = re.compile(r"^-?\d+/\d+$")
DIGIT_MASK = re.compile(r"\d+")

RULES = ("PARSE", "FIELD", "VERIFY", "DIGITS", "FORMAT", "DRIFT", "CONST_VERIFY",
         "CHOICE_VERIFY", "DUP", "NEARDUP", "TIER", "ARITH", "KEYSKEW")

# 题干里的格式约定 → 答案必须满足的形状。只挑明确写了要求的题。
FORMAT_CLAIMS = (
    (re.compile(r"最简分数|分数形式|结果写成.*分数|用分数"), "frac", "题干要求分数，答案不是 a/b"),
    (re.compile(r"用小数|小数作答|写成小数|填小数|保留.*位小数|结果.*小数"), "dec", "题干要求小数，答案却写成分数"),
    (re.compile(r"只填数值|只填最后的值|只填得数|只填 ?[0-9a-zA-Z] ?的值"), "scalar",
     "题干要求只填一个数值，答案里有多个值（应用列表）"),
)
# 明确允许填多个值的说法
MULTI_OK = re.compile(r"依次|逗号|分别|两个|三个|和")


def norm(s):
    return PUNCT.sub("", str(s or "")).lower()


def mask(s):
    """数字全部打码：用来抓「同一种题换个数再出一遍」。"""
    return DIGIT_MASK.sub("#", norm(s))


def dup_key(raw):
    """题干 + 能区分内容的部分（选项文字，或答案）。
    「下列句子中没有语病的一项是」这类通用问法在库里会反复出现，
    只比题干会把换了选项的新题误判成重复。"""
    ch = raw.get("choices")
    if ch:
        opts = "|".join(sorted(norm(c.get("text")) for c in ch))
        return "%s|%s" % (norm(raw.get("prompt")), opts)
    return "%s|%s" % (norm(raw.get("prompt")), "|".join(sorted(norm(a) for a in answers_of(raw))))


def load(p):
    d = json.load(io.open(p, encoding="utf-8"))
    if isinstance(d, dict):
        d = d.get("questions") or []
    return d


def answers_of(raw):
    """answer 拆成若干字符串 token。"""
    a = raw.get("answer")
    if isinstance(a, list):
        return [str(x).strip() for x in a]
    return [str(a).strip()]


def check_item(batch, raw, need, bank_prompts, topic, in_bank=False):
    """返回 [(rule, detail)]。need = 该知识点要求的档位集合。"""
    out = []
    tid = str(raw.get("topicId") or "")
    typ = raw.get("type")
    ans = answers_of(raw)

    unknown = set(raw) - Q_FIELDS
    if unknown:
        out.append(("FIELD", "多余字段：" + ",".join(sorted(unknown))))
    miss = [k for k in REQUIRED if not str(raw.get(k) or "").strip()]
    if miss:
        out.append(("FIELD", "缺字段：" + ",".join(miss)))

    # 档位：碎片写难了但知识点其实缺 basic，也要能看见
    if need and raw.get("difficulty") not in need:
        out.append(("TIER", "difficulty=%s 而该点需要 %s" % (
            raw.get("difficulty"), ",".join(sorted(need)))))

    if typ == "choice":
        ch = raw.get("choices") or []
        keys = [c.get("key") for c in ch]
        text_of = {c.get("key"): str(c.get("text") or "") for c in ch}
        right = text_of.get(str(raw.get("answer")).strip())
        if right is None:
            out.append(("CHOICE_VERIFY", "answer 不在选项 key 里"))
        v = raw.get("verify")
        if isinstance(v, str):
            try:
                res = VQ.safe_eval(v)
            except Exception as ex:  # noqa: BLE001
                # 「三条边」这种裸中文名会被 AST 白名单拒掉——必须写成字符串字面量
                out.append(("CHOICE_VERIFY", "verify 求值失败 %s: %s" % (type(ex).__name__, ex)))
            else:
                def as_num(t):
                    pv = V.parse_numeric_answer(str(t).strip().replace("−", "-"))
                    return pv[0] if pv is not None and len(pv) == 1 else None

                rv = as_num(right) if right is not None else None
                if rv is not None:
                    # 选项本身就是数：verify 返回该数即可，一致性交给 verify_all（不一致会进 VERIFY）
                    pass
                elif not isinstance(res, str):
                    out.append(("CHOICE_VERIFY", "verify 应返回选项文字（带引号的字面量），实得 %r" % (res,)))
                elif str(res).strip() != right.strip():
                    out.append(("CHOICE_VERIFY", "verify 得 %r，正确选项文字是 %r" % (res, right)))
                else:
                    dup = [k for k, t in text_of.items() if k != raw.get("answer") and str(t).strip() == right.strip()]
                    if dup:
                        out.append(("CHOICE_VERIFY", "有第二个选项与正确项文字相同：" + ",".join(dup)))
        elif right is not None and not re.match(r"^-?[\d./]+$", right.strip()):
            out.append(("CHOICE_VERIFY", "正确选项不是数字，必须补带引号的 verify"))

    if typ == "numeric":
        for a in ans:
            if FRAC_RE.match(a):
                p, q = a.split("/")
                if max(len(p.lstrip("-")), len(q)) > 6:
                    out.append(("DIGITS", "答案 %s 位数异常（多半是浮点转分数没约分）" % a))
                elif math.gcd(abs(int(p)), int(q)) > 1:
                    out.append(("DIGITS", "答案 %s 未约分" % a))
            elif re.match(r"^-?\d+\.\d+$", a):
                dp = a.split(".")[1]
                # 题干本来就要求写成小数（如 0.00007）时不算异常，只在没来由的长小数上报警
                if len(dp) > 6 or (len(dp) > 4 and "小数" not in str(raw.get("prompt") or "")):
                    out.append(("DIGITS", "答案 %s 小数位过多" % a))

        prompt = str(raw.get("prompt") or "")
        joined = "，".join(ans)
        for rx, kind, msg in FORMAT_CLAIMS:
            if not rx.search(prompt):
                continue
            if kind == "frac" and not any(FRAC_RE.match(a) for a in ans):
                out.append(("FORMAT", msg + "：" + joined))
            elif kind == "dec" and any(FRAC_RE.match(a) for a in ans):
                out.append(("FORMAT", msg + "：" + joined))
            elif kind == "scalar" and len(ans) > 1 and not MULTI_OK.search(prompt):
                out.append(("FORMAT", msg + "：" + joined))

        expl = str(raw.get("explanation") or "").replace("−", "-")
        for a in ans:
            a = a.replace("−", "-")
            if re.match(r"^-?[\d./]+$", a) and a not in expl:
                # 答案是数、解析里却一次都没出现——cnm_080 那类「答案和解析对不上」就是这么漏的
                out.append(("DRIFT", "答案 %s 未出现在 explanation 中" % a))

        v = raw.get("verify")
        if isinstance(v, str):
            # basic 档就是「一步套定义」，verify 写成常数可以接受；standard 以上必须有算式
            if raw.get("difficulty") == "basic":
                pass
            elif v.strip() in ans or norm(v) == norm(joined):
                out.append(("CONST_VERIFY", "verify 只是把答案抄了一遍，没有独立算式"))
            else:
                try:
                    tree = ast.parse(v.strip(), mode="eval")
                except SyntaxError:
                    pass
                else:
                    if isinstance(tree.body, ast.Constant):
                        out.append(("CONST_VERIFY", "verify 是常量字面量：%s" % v))

    if not in_bank and dup_key(raw) in bank_prompts:
        # in_bank：merged/ 里的碎片本身已在总库中，自查必然全命中，只比碎片之间
        out.append(("DUP", "与总题库已有题目重复（题干+选项/答案全同）"))

    # 一至六年级：难题不能退化成纯计算（validate.py 同口径，这里提前在碎片阶段拦）
    g = topic.get("grade")
    if isinstance(g, str) and g.strip().isdigit():
        g = int(g.strip())
    if str(topic.get("id", "")).startswith("cnm_") and isinstance(g, int) and g <= 6 \
            and raw.get("difficulty") in ("challenge", "advanced"):
        p = str(raw.get("prompt") or "")
        if V.PURE_ARITH_PROMPT_RE.search(p.strip()) or p.strip().startswith("计算："):
            out.append(("ARITH", "1-6 年级 challenge 退化成纯计算"))
    return out


def key_skew(items):
    """选择题答案位置过于集中 = 学生可以猜中。整批统计一次，不逐题报。"""
    ks = [str(it.get("answer")).strip() for it in items if it.get("type") == "choice"]
    if len(ks) < 12:
        return None
    c = collections.Counter(ks)
    top, n = c.most_common(1)[0][0], len(ks)
    if c[top] / n >= 0.45:
        return "选择答案 %s 占 %d/%d（%.0f%%），需要打散选项位置" % (top, c[top], n, 100.0 * c[top] / n)
    return None


def main(only=None):
    if not os.path.isdir(SRC):
        print("no out dir")
        return 1
    # out/ 是待合并的碎片；已入库的批次挪到 merged/，指名复检时也要能扫
    paths = {}
    for d in (MERGED, SRC):
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".json") and not f.startswith("_"):
                    paths[f] = os.path.join(d, f)
    files = sorted(paths)
    if only:
        files = [f for f in files if f in only]
    if not files:
        print("no fragments")
        return 1

    topics = {t["id"]: t for t in load(os.path.join(ROOT, "data", "topics.json"))}
    # 批次规格：知识点 -> 需要补的档位
    need_of = {}
    for fn in load(os.path.join(QG, "manifest.json")):
        p = os.path.join(QG, fn["file"])
        if not os.path.exists(p):
            continue
        for x in load(p):
            need_of[x["topicId"]] = set(x.get("need") or [])

    bank_prompts = set()
    for q in load(os.path.join(ROOT, "data", "questions.json")):
        bank_prompts.add(dup_key(q))

    findings = []
    frag_stat = collections.Counter()
    seen_norm = {}
    seen_mask = {}
    total = 0
    for fn in files:
        try:
            items = load(paths[fn])
        except Exception as ex:  # noqa: BLE001
            # 写坏了不能跳过就算过：单独记一条，出题方必须重交
            findings.append({"batch": fn, "topicId": "-", "rule": "PARSE",
                             "detail": "碎片不是合法 JSON：%s" % ex, "difficulty": "-", "prompt": ""})
            frag_stat["PARSE"] += 1
            continue
        total += len(items)
        # 先跑一遍已有的 verify 求值闸门（临时 id，只为复用比较逻辑）
        tmp = [dict(it, id="%s#%d" % (fn, i)) for i, it in enumerate(items)]
        res = VQ.verify_all([t for t in tmp if t.get("type") in ("numeric", "choice") and t.get("verify")])
        vmap = {}
        for m in res["mismatch"]:
            vmap[m["id"]] = m.get("detail") or "verify 与 answer 不一致"
        for i, raw in enumerate(items):
            tid = str(raw.get("topicId") or "")
            t = topics.get(tid) or {}
            need = need_of.get(tid)
            if need:
                need = {str(x) for x in need}
            hs = check_item(fn, raw, need, bank_prompts, t, in_bank=os.path.dirname(paths[fn]) == MERGED)
            key = "%s#%d" % (fn, i)
            if key in vmap:
                hs.append(("VERIFY", "%s | answer=%s verify=%s" % (vmap[key], raw.get("answer"), raw.get("verify"))))
            for rule, detail in hs:
                findings.append({"batch": fn, "topicId": tid, "rule": rule, "detail": detail,
                                 "difficulty": raw.get("difficulty"), "prompt": str(raw.get("prompt") or "")[:90]})
                frag_stat[rule] += 1
            # 碎片之间的互相重复
            n = dup_key(raw)
            if n in seen_norm:
                findings.append({"batch": fn, "topicId": tid, "rule": "DUP",
                                 "detail": "与 %s 题干+选项/答案全同" % seen_norm[n],
                                 "difficulty": raw.get("difficulty"), "prompt": str(raw.get("prompt"))[:90]})
            else:
                seen_norm[n] = fn
            m = mask(raw.get("prompt"))
            if m in seen_mask and seen_mask[m] != (tid, fn):
                findings.append({"batch": fn, "topicId": tid, "rule": "NEARDUP",
                                 "detail": "与 %s/%s 同型换数" % seen_mask[m],
                                 "difficulty": raw.get("difficulty"), "prompt": str(raw.get("prompt"))[:90]})
            else:
                seen_mask[m] = (tid, fn)
        sk = key_skew(items)
        if sk:
            findings.append({"batch": fn, "topicId": "（整批）", "rule": "KEYSKEW", "detail": sk,
                             "difficulty": "-", "prompt": ""})
            frag_stat["KEYSKEW"] += 1

    lines = ["# 碎片体检报告", "",
             "碎片 %d 个 / 题目 %d 道，命中 %d 条。" % (len(files), total, len(findings)), "",
             "| rule | count |", "|---|---|"]
    for r in RULES:
        if frag_stat[r]:
            lines.append("| %s | %d |" % (r, frag_stat[r]))
    lines.append("")
    by = collections.defaultdict(list)
    for f in findings:
        by[f["rule"]].append(f)
    for r in RULES:
        if not by[r]:
            continue
        lines.append("## %s（%d）" % (r, len(by[r])))
        for f in by[r]:
            lines.append("- `%s` %s **%s** %s" % (f["batch"], f["topicId"], f["difficulty"], f["detail"]))
            lines.append("  - 题干：%s" % f["prompt"])
        lines.append("")
    io.open(REPORT, "w", encoding="utf-8").write("\n".join(lines))
    print("fragments=%d items=%d findings=%d" % (len(files), total, len(findings)))
    print(" ".join("%s=%d" % (r, frag_stat[r]) for r in RULES if frag_stat[r]))
    print("report " + REPORT.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main([os.path.basename(a) for a in sys.argv[1:] if not a.startswith("--")] or None))
