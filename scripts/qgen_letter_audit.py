# -*- coding: utf-8 -*-
"""全库审计：解析里断言「正确项是 X」的字母，是否等于 answer 的字母。
打散选项位置时会重写解析字母，这条检查用来证明重写没写错；顺带能抓出出题时
解析和答案本来就不一致的题。只认「断言正确项」的写法，干扰项的「B 错」不算。
"""
import io
import json
import re
import sys

ANS_RE = re.compile(r"(?:所以选|因此选|应选|故选|答案(?:是|为)|正确答案(?:是|为))\s*([ABCD])(?![A-Za-z])")
RIGHT_RE = re.compile(r"([ABCD])(?:选项)?(?:正确|最恰当|最能|符合题意|无误)")

path = sys.argv[1] if len(sys.argv) > 1 else "data/questions.json"
qs = json.load(io.open(path, encoding="utf-8"))
bad = []
for q in qs:
    if q.get("type") != "choice" or not q.get("choices"):
        continue
    ans = str(q.get("answer") or "").strip().upper()
    if ans not in "ABCD":
        continue
    expl = str(q.get("explanation") or "")
    claim = set(ANS_RE.findall(expl)) | set(RIGHT_RE.findall(expl))
    if not claim:
        continue
    if ans not in claim:
        bad.append({"id": q.get("id"), "topicId": q.get("topicId"), "answer": ans,
                    "claim": sorted(claim), "difficulty": q.get("difficulty"),
                    "prompt": str(q.get("prompt") or "")[:60],
                    "explanation": expl[:160]})
    elif len(claim) > 1:
        bad.append({"id": q.get("id"), "topicId": q.get("topicId"), "answer": ans,
                    "claim": sorted(claim), "difficulty": q.get("difficulty"),
                    "prompt": str(q.get("prompt") or "")[:60],
                    "explanation": expl[:160], "multi": 1})

out = io.open("_scratch/qgen/_tmp/letter_audit.txt", "w", encoding="utf-8")
out.write("检查 choice 题 %d 道，解析里点了字母的题中发现疑点 %d 条\n\n" % (
    sum(1 for q in qs if q.get("type") == "choice"), len(bad)))
for b in bad:
    out.write("%s | %s | ans=%s claim=%s%s\n  题干：%s\n  解析：%s\n\n" % (
        b.get("id"), b.get("topicId"), b["answer"], ",".join(b["claim"]),
        "（多字母）" if b.get("multi") else "", b["prompt"], b["explanation"]))
out.close()
print("choice_items=%d suspects=%d" % (
    sum(1 for q in qs if q.get("type") == "choice"), len(bad)))
