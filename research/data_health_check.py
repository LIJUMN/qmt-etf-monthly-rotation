# -*- coding: utf-8 -*-
"""
数据体检: 扫一遍全部品种, 找出"复权数据会毁掉 QMT 回测"的标的。

背景
----
513100(纳指ETF) 在 2022-01-14 做了 1:5 份额拆分(份额折算), 不复权价当天
从 5.192 直接变成 1.015 (-80.4%), 成交量放大 5.7 倍。这是"假暴跌":
如果回测引擎的取价口径=不复权、又没把持仓股数同步放大 5 倍, 这一根K线
就会凭空吃掉账户一大块, 并且制造一笔假的最大回撤。

判据
----
把 (前复权价 / 不复权价) 逐日算出来, 它只会在"除权除息事件日"跳变:
  - 跳幅 > 15%  -> SPLIT  份额拆分/折算, 回测不处理必炸
  - 0.02~15%    -> DIV    普通分红(送股), 影响小但口径也要一致
  - 无跳变      -> CLEAN  可以放心回测
另附: 不复权序列单日最大跌幅。ETF 涨跌停 ±10%, 单日跌破 -11% 必是拆分/数据错。

输出: 数据与因子/_复权体检.csv
"""
import json
import os
import csv

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(BASE, '数据与因子')
START, END = '2016-10-13', '2026-10-13'


def load(tag, name):
    p = os.path.join(DAT, tag, name)
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    if not isinstance(d, dict) or 'kline' not in d:
        return None
    return {r['date']: float(r['close']) for r in d['kline']}


files = [f for f in sorted(os.listdir(os.path.join(DAT, '历史数据_不复权')))
         if f.endswith('.json') and f.startswith('ETF')]

rows = []
for f in files:
    adj = load('历史数据', f)
    raw = load('历史数据_不复权', f)
    if not adj or not raw:
        continue
    cal = sorted(set(adj) & set(raw))
    cal = [d for d in cal if START <= d <= END]
    if len(cal) < 60:
        continue

    events = []
    prev = adj[cal[0]] / raw[cal[0]]
    for d in cal:
        k = adj[d] / raw[d]
        if prev and abs(k / prev - 1.0) > 0.02:
            events.append((d, k / prev - 1.0))
        prev = k
    biggest = max((abs(e[1]) for e in events), default=0.0)
    big_dates = ','.join(d for d, m in events if abs(m) > 0.15)

    worst, worst_d = 0.0, ''
    for i in range(1, len(cal)):
        c0, c1 = raw[cal[i - 1]], raw[cal[i]]
        if c0 > 0:
            ch = c1 / c0 - 1.0
            if ch < worst:
                worst, worst_d = ch, cal[i]

    if biggest > 0.15:
        kind = 'SPLIT'
    elif events:
        kind = 'DIV'
    else:
        kind = 'CLEAN'

    rows.append([f.replace('ETF_', '').replace('.json', ''), len(cal),
                 '%.4f' % (adj[cal[0]] / raw[cal[0]]), '%.4f' % (adj[cal[-1]] / raw[cal[-1]]),
                 len(events), '%.1f%%' % (biggest * 100), big_dates,
                 '%.2f%%' % (worst * 100), worst_d, kind])

rows.sort(key=lambda r: (-float(r[5].rstrip('%')), r[0]))

out = os.path.join(DAT, '_复权体检.csv')
with open(out, 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['代码', '交易日数', '起点复权比值', '终点复权比值', '事件次数',
                '单次最大跳幅', '拆分事件日', '不复权最大单日跌幅', '出现日', '判定'])
    w.writerows(rows)

n_split = sum(1 for r in rows if r[9] == 'SPLIT')
n_div = sum(1 for r in rows if r[9] == 'DIV')
n_clean = sum(1 for r in rows if r[9] == 'CLEAN')
print('ETF 体检: %d 只   拆分(SPLIT) %d   分红(DIV) %d   干净(CLEAN) %d' % (
    len(rows), n_split, n_div, n_clean))
print()
print('== SPLIT: 回测不处理份额拆分, 结果必然失真 ==')
print('%-8s %8s %10s %10s %-26s %s' % ('代码', '交易日', '起比值', '单次跳幅', '拆分日', '单日最大跌幅/日'))
for r in rows:
    if r[9] == 'SPLIT':
        print('%-8s %8d %10s %10s %-26s %10s %s' % (r[0], r[1], r[2], r[5], r[6], r[7], r[8]))
print()
print('== DIV: 只有小额分红, 风险低 ==')
print('   ' + ', '.join(r[0] for r in rows if r[9] == 'DIV'))
print()
print('== CLEAN: 复权比值恒=1, 可直接回测 ==')
print('   ' + ', '.join(r[0] for r in rows if r[9] == 'CLEAN'))
print()
print('结果已写入: ' + out)
