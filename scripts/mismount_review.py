# -*- coding: utf-8 -*-
"""n-gram 错挂疑点筛查 / 摘除 / 恢复。

筛查只产出「疑点」，不是定论，且精度随难度档剧变：basic/standard 约 80%，
challenge 只有约 24%（拓展题刻意用新材料，字面重叠天然低）。摘除时整题存进
data/mismount-review.json，按人工裁定分批恢复。

--apply 可反复跑：已有证据整条保留，只追加新命中；已裁定为 false_positive /
borderline / needs_fix 的题不再摘除（裁定优先于筛查）。

  python scripts/mismount_review.py                          # 只筛查，不改数据
  python scripts/mismount_review.py --apply                  # 摘除并合并写证据文件
  python scripts/mismount_review.py --regrade                # 把 VERDICTS 写回证据文件
  python scripts/mismount_review.py --restore                # 恢复全部
  python scripts/mismount_review.py --restore=false_positive # 只恢复裁定为误报的
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QP = os.path.join(ROOT, 'data', 'questions.json')
TP = os.path.join(ROOT, 'data', 'topics.json')
RP = os.path.join(ROOT, 'data', 'mismount-review.json')

MIN_INDEX = 11
OWN_MAX = 2
MARGIN_MIN = 6
NGRAM_SIZES = (2, 3)
CUT = re.compile(u'[^\\u4e00-\\u9fff]+')

# 人工已看过且结论不是「确属错挂」，筛查不得再次摘除。
HOLD_VERDICTS = frozenset(('false_positive', 'borderline', 'needs_fix'))

# 人工复核结论，逐题依据见 note。未列出的一律 pending。
VERDICTS = {
    'cnc_p047_q12': ('false_positive', u'题干本身就是童谣朗读理解，挂「快乐读书吧：读读童谣和儿歌」正确；n-gram 命中的「动物儿歌」是识字课，不是本题考点。'),
    'cnc_p367_q11': ('false_positive', u'材料即《祖父的园子》原文改写（黄瓜愿意爬上架、孩子铲地），挂载正确；n-gram 建议的形近字课与本题无关。'),
    'cnm_p152_q23': ('false_positive', u'4 个小正方体摆几何体、按正面视图数摆法，正是「根据三个方向辨认物体」。'),
    'cnm_p152_q19': ('false_positive', u'由正面/左面视图求最多块数，正是「根据三个方向辨认物体」。'),
    'cnm_010_q19': ('false_positive', u'16+(-25)+24+(-35) 必须用异号两数相加法则，属「有理数的加法法则」；运算律只是手段。'),
    'cnp_h044_q11': ('false_positive', u'粒子以 0.6c 飞行、实验室寿命变长，是时间延缓的直接应用，知识点描述已覆盖。'),
    'cnm_p258_q16': ('borderline', u'「个位 6 十位 4」考的是十位和个位，与「100 的认识」同单元相邻点，不算离谱但不够精确。'),
    'cnm_p024_q17': ('borderline', u'正方形平均分两份问形状，可算图形拼组的分割操作，也可算分数启蒙，两边都沾。'),
    'cnm_p210_q15': ('borderline', u'x=4/5y 求最简整数比，考的是六上「化简比」，不是六下「比例的意义和基本性质」；同域不同点。'),
    'cnm_p146_q12': ('confirmed_mismount', u'梯形面积公式，与「列方程解决实际问题」无关。'),
    'cnm_p276_q12': ('confirmed_mismount', u'三位数加三位数的和位数，与「乘法估算」无关。'),
    'cnm_p257_q14': ('confirmed_mismount', u'5,10,15,20 找规律，与「读法和写法」无关。'),
    'cnm_p073_q20': ('confirmed_mismount', u'长方形变正方形求周长，与「倍的认识」无关。'),
    'cnc_p415_q11': ('confirmed_mismount', u'心理描写的定义，与《狼牙山五壮士》课文理解无关。'),
    'cnm_p026_q11': ('confirmed_mismount', u'正方形四边相等，与「十几减 8、7、6」无关。'),
    'cnm_p238_q18': ('confirmed_mismount', u'摸球可能性大小，与「图形的运动」无关。'),
    'cnm_p130_q16': ('confirmed_mismount', u'除法算式各部分名称，与「复式条形统计图」无关。'),
    'cns_p151_q12': ('confirmed_mismount', u'摆的等时性发现者，与「用重物驱动小车」无关。'),
    'cnm_p062_q11': ('confirmed_mismount', u'与 3999 相邻的数，与「时、分、秒的进率」无关。'),
    'cnm_p281_q21': ('confirmed_mismount', u'往返方向判断，与「剪纸」轴对称无关。'),
    'cnc_p106_q11': ('confirmed_mismount', u'刘胡兰动作描写，与《朱德的扁担》无关。'),
    'cnm_p247_q28': ('confirmed_mismount', u'百分数增长，与「分数、小数混合运算」无关。另：答案 D=15% 本身也错，正解 115%（B），恢复前须先订正。'),
    'cnm_p134_q13': ('confirmed_mismount', u'数对表示列，与「小数乘法的应用」无关。'),
    'cnm_p193_q15': ('confirmed_mismount', u'比的前项后项比值可为分数，与「扇形的认识」无关。'),
    'cnm_219_q12': ('confirmed_mismount', u'太阳东升属必然事件，与「一元二次方程的概念」无关。'),
    'cnm_p040_q22': ('confirmed_mismount', u'含括号算式的运算顺序，与「认识厘米及用厘米量」无关。'),
    'cnm_p268_q13': ('confirmed_mismount', u'远近观察形状，与「解决连续两问的问题」无关。'),
    'cnm_p017_q16': ('confirmed_mismount', u'辨认球体，与「十位和个位」无关。'),
    'cnm_p044_q17': ('confirmed_mismount', u'由正面侧面视图辨认长方体，与「用 7～9 的乘法口诀求商」无关。'),
    'cnm_p231_q11': ('confirmed_mismount', u'看错因数导致的积差，属多位数乘两位数，不是「乘法模型」（总价/路程关系）。'),
    'cnm_p095_q11': ('confirmed_mismount', u'拼接长方形求周长，与「搭配问题」无关。'),
    # 以下 46 道 challenge 档已逐条读完（全量，非抽样）。
    'cnc_p005_q11': ('false_positive', u'「开学第一天走进教室、老师教第一个生字」正是入学教育「我上学了」的情景。'),
    'cnc_p046_q12': ('false_positive', u'「李江请王红帮他捡本子」谁帮谁，正是「请你帮个忙」的请托关系理解。'),
    'cnc_p065_q13': ('false_positive', u'正确项「不解藏踪迹，浮萍一道开」即白居易《池上》原句。'),
    'cnc_p098_q13': ('false_positive', u'「清晨薄雾、中午太阳高照、雨天朦胧」是《日月潭》课文原句，考不同时候的景色。'),
    'cnc_p114_q14': ('false_positive', u'以「手可摘星辰」辨夸张手法，正是《夜宿山寺》。'),
    'cnc_p120_q13': ('false_positive', u'题干直接点名《村居》，辨「二月春风似剪刀」属《咏柳》；n-gram 被选项里的诗句带偏。'),
    'cnc_p160_q14': ('confirmed_mismount', u'词语搭配（穿着校服和红领巾），与孙中山「不懂就要问」无关。'),
    'cnc_p173_q16': ('borderline', u'小猴学黄鹂的类文与《小狗学叫》同主题（别盲目学别人），但考点描述强调「预测结局」，本题考寓意。'),
    'cnc_p177_q14': ('borderline', u'「先在家练好再报名」与《一块奶酪》的以身作则主题关联弱，属泛阅读概括。'),
    'cnc_p187_q14': ('confirmed_mismount', u'小竹林段落收尾，与《香港，璀璨的明珠》无关。'),
    'cnc_p221_q11': ('false_positive', u'「这种设计是一个创举，既…又…」是《赵州桥》课文原句。'),
    'cnc_p231_q14': ('false_positive', u'《爱唠叨的妈妈》结尾照应前文，正是「身边那些有特点的人」。'),
    'cnc_p241_q17': ('false_positive', u'爷爷在乡下/城里/海边三次看星星，是巴金《繁星》三次看繁星的类文迁移。'),
    'cnc_p252_q13': ('false_positive', u'题干直接点名《雪梅》，正确项「梅须逊雪三分白，雪却输梅一段香」即原诗。'),
    'cnc_p333_q11': ('false_positive', u'四个选项考的正是模、弹、强这三个多音字。'),
    'cnc_p334_q11': ('false_positive', u'按语境选有始有终/守株待兔/亡羊补牢，正是「成语运用」。'),
    'cnc_p350_q14': ('false_positive', u'父亲算学费划掉烟和鞋、夜里摇船送考、把被子盖给孩子，全是《父爱之舟》情节。'),
    'cnc_p352_q14': ('false_positive', u'跟妈妈商量练琴时间该怎么说，正是「我想对您说」的交际任务。'),
    'cnc_p389_q21': ('false_positive', u'辨神态/动作/语言描写，正是《人物描写一组》的考点。'),
    'cnc_p416_q21': ('false_positive', u'点面结合写集体场面，是《开国大典》的写法考点。'),
    'cnc_p417_q19': ('false_positive', u'「火已经烧到了身上，他没有挪动半步」是《我的战友邱少云》课文原句。'),
    'cnc_p431_q29': ('false_positive', u'眼前→往事→眼前的倒叙与首尾呼应，正是《灯光》的写法。'),
    'cnc_p432_q28': ('false_positive', u'「盼去粮站取借书卡」类文考围绕一个意思写，对应《盼》。'),
    'cnc_p465_q12': ('false_positive', u'写《汤姆·索亚历险记》梗概该保留主要情节，正是「写作品梗概」。'),
    'cnc_p475_q11': ('borderline', u'句子用《竹石》《马诗》讲托物言志，但实际考的是「托物言志→借物喻志」近义替换，不是诗本身。'),
    'cnc_p485_q21': ('false_positive', u'回忆《那次拔河比赛》该详写哪部分，正是「回忆往事」的详略取舍。'),
    'cne_j009_q11': ('false_positive', u'child→children 不规则复数，正是「名词复数」；n-gram 命中的「可数名词复数」是近义点。'),
    'cne_j253_q11': ('confirmed_mismount', u'主动变被动加 be 加过去分词，属被动语态，与形式主语 it 无关。'),
    'cne_p081_q12': ('false_positive', u"What is his father's job? 正是「询问职业与 his、her」。"),
    'cne_p084_q13': ('false_positive', u'school/playground/library/classroom 全是学校场所。'),
    'cne_p225_q15': ('false_positive', u'What did you do during the holiday? 正是本点的目标句型。'),
    'cng_j007_q11': ('needs_fix', u'航线依次经过大洋属「大洲和大洋」，挂载对；但上海出发先经太平洋，选项里没有「太平洋、印度洋、大西洋」，答案 C 不完整。恢复前必须先订正选项与答案。'),
    'cng_j013_q11': ('false_positive', u'最冷月 3℃（>0）属温带、夏雨型 800mm 判温带季风，正是「世界的气候」。'),
    'cng_j014_q12': ('false_positive', u'人口增长过快带来的粮食/土地/生态问题，属「人口与人种」的人口增长部分；撒哈拉以南非洲只是情境。'),
    'cng_j032_q11': ('false_positive', u'人口由中西部向东部沿海迁移的成因，属中国人口分布变化。'),
    'cng_j036_q13': ('borderline', u'湖泊缩小的可持续对策（退田还湖）属湖泊保护，考点描述只写「外流河和主要湖泊的特征」。'),
    'cng_j053_q12': ('confirmed_mismount', u'珠江口海域生态对策，与港澳位置/特别行政区地位/与内地联系无关。'),
    'cnm_061_q11': ('false_positive', u'400m 跑道相邻道次周长差 2π×1.2=264/35，正是教材「设计学校田径运动会比赛场地」活动。'),
    'cnm_113_q13': ('confirmed_mismount', u'「全等与勾股定理常配合使用」，与三角形的中线无关。'),
    'cnp_046_q12': ('needs_fix', u'P=Fv=1500×20=30000 属「功率」，挂载对；但题干问「做的功是多少 J」且未给时间或距离，答案 30000 的单位应是 W。恢复前必须把题干改成问功率。'),
    'cnp_054_q11': ('false_positive', u'红墨水在 20℃/80℃ 扩散快慢之比，正是温度越高分子运动越剧烈。'),
    'cnp_h093_q13': ('false_positive', u'静止炸裂两块求速度，考点描述明确写了「爆炸等内力远大于外力的短暂过程可近似认为动量守恒」。'),
}


def ngrams(text):
    got = set()
    for seg in CUT.split(text or ''):
        for n in NGRAM_SIZES:
            for i in range(len(seg) - n + 1):
                got.add(seg[i:i + n])
    return got


def load_questions():
    return json.load(io.open(QP, encoding='utf-8'))


def save_questions(qs):
    io.open(QP, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(qs, ensure_ascii=False, indent=1))


def subject_of(tid):
    return tid[2] if len(tid) > 3 else '?'


def screen(qs, topics):
    lex = {}
    inv = defaultdict(Counter)
    for t in topics:
        txt = ' '.join(str(t.get(k) or '') for k in
                       ('name', 'title', 'description', 'summary', 'chapter'))
        g = ngrams(txt)
        lex[t['id']] = g
        for ng in g:
            inv[ng][t['id']] += 1
    hits = []
    scanned = 0
    for q in qs:
        m = re.search(r'_q(\d+)$', q['id'])
        if not m or int(m.group(1)) < MIN_INDEX:
            continue
        tp = q['topicId']
        if tp not in lex:
            continue
        scanned += 1
        text = str(q.get('prompt') or '') + ' ' + ' '.join(
            str(c.get('text') or '') for c in (q.get('choices') or []))
        mine = ngrams(text)
        own = len(lex[tp] & mine)
        cand = Counter()
        for ng in mine:
            for other in inv.get(ng, ()):
                if other != tp and subject_of(other) == subject_of(tp):
                    cand[other] += 1
        best, bscore = None, 0
        for other, _c in cand.most_common(5):
            s = len(lex[other] & mine)
            if s > bscore:
                best, bscore = other, s
        if own <= OWN_MAX and bscore >= own + MARGIN_MIN:
            hits.append({'qid': q['id'], 'topicId': tp, 'own': own,
                         'best': best, 'bscore': bscore, 'margin': bscore - own})
    return hits, scanned


def build_review(qs, topics, hits):
    tmap = {t['id']: t for t in topics}
    qmap = {q['id']: q for q in qs}
    items = []
    for h in sorted(hits, key=lambda z: z['qid']):
        t = tmap.get(h['topicId'], {})
        verdict, note = VERDICTS.get(h['qid'], ('pending', ''))
        items.append({
            'qid': h['qid'],
            'topicId': h['topicId'],
            'topic': {k: t.get(k) for k in
                      ('name', 'chapter', 'grade', 'subject', 'description')},
            'screen': {k: h[k] for k in ('own', 'best', 'bscore', 'margin')},
            'bestName': (tmap.get(h['best']) or {}).get('name', ''),
            'verdict': verdict,
            'note': note,
            'question': qmap[h['qid']],
        })
    return {
        'schema': 1,
        'createdAt': '2026-11-08',
        'reason': u'n-gram 错挂疑点整批摘除，题目与证据原样留存，待人工逐条裁定后恢复或改写。',
        'caveat': (u'筛查是疑点不是定论。分层复核 30 题（低/中/高 margin 各 10）：'
                   u'22 确属错挂、5 误报、3 存疑；另单独复核 cnp_h044_q11 为误报。'
                   u'未复核条目 verdict=pending，恢复前必须逐条看。'),
        'screen': {'minIndex': MIN_INDEX, 'ownMax': OWN_MAX,
                   'marginMin': MARGIN_MIN, 'ngramSizes': list(NGRAM_SIZES),
                   'sameSubjectOnly': True,
                   'lexiconFields': ['name', 'title', 'description', 'summary', 'chapter']},
        'stats': {
            'total': len(items),
            'byVerdict': dict(Counter(i['verdict'] for i in items)),
            'bySubject': dict(Counter(subject_of(i['topicId']) for i in items)),
        },
        'restore': 'python scripts/mismount_review.py --restore',
        'items': items,
    }


def gate_impact(qs, topics, drop):
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import version_gate as vg
    by = defaultdict(list)
    for q in qs:
        by[q['topicId']].append(q)
    tmap = {t['id']: t for t in topics}
    reg = json.load(io.open(os.path.join(ROOT, 'data', 'editions', 'registry.json'),
                            encoding='utf-8'))
    lost, emptied = [], []
    for v in reg['versions']:
        for subj, e in (v.get('subjects') or {}).items():
            for tid in set(e.get('topicIds') or []):
                if tid not in tmap:
                    continue
                mine = by.get(tid, [])
                keep = [q for q in mine if q['id'] not in drop]
                if not vg.bar_ok(tid, mine, subj) and vg.bar_ok(tid, keep, subj):
                    lost.append({'tid': tid, 'name': tmap[tid].get('name', ''),
                                 'subject': subj, 'before': len(mine),
                                 'after': len(keep),
                                 'reason': vg.bar_ok(tid, keep, subj)})
    for tid, mine in by.items():
        if mine and all(q['id'] in drop for q in mine):
            emptied.append(tid)
    return lost, emptied


def regrade(rev):
    for i in rev['items']:
        v, note = VERDICTS.get(i['qid'], ('pending', ''))
        i['verdict'], i['note'] = v, note
    rev['stats']['byVerdict'] = dict(Counter(i['verdict'] for i in rev['items']))
    rev['caveat'] = (
        u'筛查是疑点不是定论，且精度随难度档剧变。'
        u'basic/standard 分层复核 30 题：22 确属错挂、5 误报、3 存疑（精度约 80%）。'
        u'challenge 档 46 道已全量逐条读完：35 误报、5 确属错挂、4 存疑、2 挂载对但题目有硬伤（精度约 24%）。'
        u'原因是拓展题刻意用新材料/类文迁移，题干与考点名字面重叠天然低，n-gram 恰好惩罚了它该奖励的题型。'
        u'未复核条目 verdict=pending，恢复前必须逐条看。'
        u'verdict=needs_fix 的题挂载正确但答案或题干有硬伤，恢复前必须先订正。')
    return rev


def load_review():
    if not os.path.exists(RP):
        return None
    return json.load(io.open(RP, encoding='utf-8'))


def merge_review(prior, fresh):
    """已有条目连 question 原文、restoredAt 一起原样留下，只追加本轮新命中。"""
    rev = fresh if prior is None else prior
    if prior is not None:
        known = set(i['qid'] for i in prior['items'])
        rev['items'].extend(i for i in fresh['items'] if i['qid'] not in known)
        rev['items'].sort(key=lambda i: i['qid'])
    rev['stats']['total'] = len(rev['items'])
    rev['stats']['bySubject'] = dict(
        Counter(subject_of(i['topicId']) for i in rev['items']))
    rev['stats']['restored'] = sum(1 for i in rev['items'] if i.get('restoredAt'))
    return rev


def save_review(rev):
    io.open(RP, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(rev, ensure_ascii=False, indent=1) + '\n')


def main():
    args = sys.argv[1:]
    qs = load_questions()
    raw = json.load(io.open(TP, encoding='utf-8'))
    topics = raw if isinstance(raw, list) else raw.get('topics', [])

    if '--regrade' in args:
        rev = regrade(json.load(io.open(RP, encoding='utf-8')))
        save_review(rev)
        print('regraded=%d %s' % (len(rev['items']),
                                  json.dumps(rev['stats']['byVerdict'], ensure_ascii=False)))
        return

    if any(a == '--restore' or a.startswith('--restore=') for a in args):
        rev = json.load(io.open(RP, encoding='utf-8'))
        want = None
        for a in args:
            if a.startswith('--restore='):
                want = set(a.split('=', 1)[1].split(','))
        have = {q['id'] for q in qs}
        pick = [i for i in rev['items']
                if i['qid'] not in have and (want is None or i['verdict'] in want)]
        qs.extend(i['question'] for i in pick)
        for i in pick:
            i['restoredAt'] = '2026-11-08'
        save_questions(qs)
        rev['stats']['restored'] = sum(1 for i in rev['items'] if i.get('restoredAt'))
        save_review(rev)
        print('restored=%d total=%d verdicts=%s' % (
            len(pick), len(qs),
            json.dumps(dict(Counter(i['verdict'] for i in pick)), ensure_ascii=False)))
        return

    hits, scanned = screen(qs, topics)
    prior = load_review()
    held = set(i['qid'] for i in (prior['items'] if prior else [])
               if i['verdict'] in HOLD_VERDICTS)
    drop = set(h['qid'] for h in hits) - held
    lost, emptied = gate_impact(qs, topics, drop)
    print('scanned_q%dplus=%d suspects=%d held=%d removable=%d total=%d after=%d' % (
        MIN_INDEX, scanned, len(hits), len(set(h['qid'] for h in hits) & held),
        len(drop), len(qs), len(qs) - len(drop)))
    print('newly_broken_pairs=%d distinct_topics=%d emptied=%d' % (
        len(lost), len(set(x['tid'] for x in lost)), len(emptied)))
    for x in sorted(set((x['tid'], x['name'], x['reason']) for x in lost)):
        print('  NEEDS_TOPUP %s %s -> %s' % x)

    if '--apply' not in args:
        print('(dry run; pass --apply to remove and merge evidence)')
        return

    fresh = build_review(qs, topics, [h for h in hits if h['qid'] in drop])
    rev = regrade(merge_review(prior, fresh))
    save_review(rev)
    save_questions([q for q in qs if q['id'] not in drop])
    print('evidence=%s items=%d new=%d restored=%d' % (
        RP, len(rev['items']), len(fresh['items']), rev['stats']['restored']))


if __name__ == '__main__':
    main()