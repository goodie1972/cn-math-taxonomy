# -*- coding: utf-8 -*-
"""把生成器产物合回既有数据文件，不冲掉生成器不认识的内容。

zh/mor/sci 三个构建脚本原先按「先剥掉本学科、再拼接新产物」写回。总题库在补题阶段给
同一知识点加过第 5 题以后的一道道题目，那些题的 topicId 属于本学科，于是每次重跑构建都
被当成非本学科数据删干净（实测一次跑掉 7607 道）。这里改成按 key 原地替换：

- 生成器重新产出的条目，替换在原位置；
- 生成器新增的条目，追加在末尾；
- 只有确实被删掉的知识点带走的条目才删除；
- 其余条目（其他学科、以及补题阶段加的额外题目）按原顺序保留。

所以重复运行构建脚本的结果是可复现的，也不会破坏题库。
"""


def merge_generated(existing, generated, key, owned):
    """owned(item) 说明这条记录归本次构建的学科管，交给 generated 覆盖。

    返回 (合并后的列表, 被删掉的旧条目列表)。
    """
    gen_by_key = {}
    for item in generated:
        k = key(item)
        if k in gen_by_key:
            raise SystemExit("生成器自己产出了重复的条目：%r" % (k,))
        gen_by_key[k] = item
    out = []
    placed = set()
    dropped = []
    for item in existing:
        k = key(item)
        if not owned(item):
            out.append(item)
            continue
        if k in gen_by_key:
            out.append(gen_by_key[k])
            placed.add(k)
        else:
            dropped.append(item)
    for item in generated:
        k = key(item)
        if k not in placed:
            out.append(item)
            placed.add(k)
    return out, dropped
