# -*- coding: utf-8 -*-
"""解析字母双向审计：既查「解析说 X 正确」是否等于 answer，也查解析有没有把
answer 那一选项说成错误项。scripts/qgen_letter_audit.py 只认「正确」一侧的写法，
「B 错 / A 说反了 / 排除 C」这类干扰项描述它看不见，这条补上。
用法：python scripts/qgen_letter_pair_audit.py [data/questions.json]
有疑点时退出码 1，可当闸门用。"""
import io
import json
import re
import sys

RIGHT = re.compile(
    r"(?:所以选|因此选|应选|故选|答案(?:是|为)|正确答案(?:是|为))\s*([ABCD])(?![A-Za-z])"
    r"|([ABCD])(?:选项)?(?:正确|最恰当|最能|符合题意|无误|是对的|没错|判断正确|符合原文)"
    r"|([ABCD])(?:选项)?(?:是答案|说的就是)")
WRONG = re.compile(
    r"([ABCD])(?:选项)?(?:错|错误|不对|有误|不符|说反|说成|排除|应排除|站不住|不成立)"
    r"|排除\s*([ABCD])(?![A-Za-z])")


def letters(pattern, text):
    got = set()
    for groups in pattern.findall(text):
        for g in groups:
            if g:
                got.add(g)
    return got


def main(path):
    qs = json.load(io.open(path, encoding="utf-8"))
    bad = []
    n_right = n_wrong = 0
    for q in qs:
        if q.get("type") != "choice" or not q.get("choices"):
            continue
        ans = str(q.get("answer") or "").strip().upper()
        if ans not in "ABCD":
            continue
        expl = str(q.get("explanation") or "")
        right = letters(RIGHT, expl)
        wrong = letters(WRONG, expl)
        if right:
            n_right += 1
        if wrong:
            n_wrong += 1
        if not right and not wrong:
            continue
        if ans in right and ans in wrong:
            why = "解析里同一个字母既算正确又算错误"
        elif ans in wrong:
            why = "解析把正确项说成干扰项"
        elif right and ans not in right:
            why = "解析断言的正确字母不等于 answer"
        elif len(right) > 1:
            why = "解析里出现多个正确字母"
        else:
            continue
        bad.append({"id": q.get("id"), "topicId": q.get("topicId"), "answer": ans,
                    "right": sorted(right), "wrong": sorted(wrong), "why": why,
                    "prompt": str(q.get("prompt") or "")[:60],
                    "explanation": expl[:200]})
    out = io.open("_scratch/qgen/_tmp/letter_pair_audit.txt", "w", encoding="utf-8")
    out.write("choice 题里解析点了字母的：正确侧 %d 道、干扰侧 %d 道；疑点 %d 条\n\n" % (
        n_right, n_wrong, len(bad)))
    for b in bad:
        out.write("%s | %s | ans=%s right=%s wrong=%s | %s\n  题干：%s\n  解析：%s\n\n" % (
            b["id"], b["topicId"], b["answer"], ",".join(b["right"]),
            ",".join(b["wrong"]), b["why"], b["prompt"], b["explanation"]))
    out.close()
    print("right_claims=%d wrong_claims=%d suspects=%d" % (n_right, n_wrong, len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/questions.json"))
