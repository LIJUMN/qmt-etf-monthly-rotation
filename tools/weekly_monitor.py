# -*- coding: utf-8 -*-
# 策略周报生成器: 每周五自动拉数据, 计算核心卫星策略当前信号状态
# 产出: 数据输出/策略周报_YYYYMMDD.md
import json, time, urllib.request, os, datetime
import numpy as np
import pandas as pd

OUT = r'C:/Users/Administrator/Desktop/QMT/数据输出'
CORE = 'sh518880'
POOL = {'sh512480': '半导体', 'sz159995': '芯片', 'sh588000': '科创50',
        'sh512000': '券商', 'sh512660': '军工', 'sh512400': '有色',
        'sh515790': '光伏', 'sh512720': '软件', 'sz159915': '创业板',
        'sh515030': '新能源车', 'sh512890': '红利低波', 'sh518880': '黄金'}

def fetch_day(code, start='2024-01-01', end='2026-12-31'):
    out = {}
    import datetime as _dt
    cur_end = end
    while cur_end > start:
        url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
               f'?param={code},day,{start},{cur_end},640,qfq')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            js = json.loads(r.read().decode('utf-8'))
        d = js.get('data', {}).get(code, {})
        rows = d.get('qfqday') or d.get('day') or []
        if not rows:
            break
        for row in rows:
            out[row[0]] = float(row[2])
        first = rows[0][0]
        if first <= start or len(rows) < 640:
            break
        y, m, dd = map(int, first.split('-'))
        cur_end = (_dt.date(y, m, dd) - _dt.timedelta(days=1)).isoformat()
        time.sleep(0.2)
    s = pd.Series(out).sort_index()
    s.index = pd.to_datetime(s.index)
    return s

df = pd.DataFrame({c: fetch_day(c) for c in POOL}).sort_index().ffill(limit=5)
last = df.index[-1]
mom = df.pct_change(60) * 0.5 + df.pct_change(250) * 0.5
m = mom.loc[last].dropna()
best = m.idxmax()
target = best if m[best] > 0 else 'CASH'

risk_rank = m.drop(CORE).sort_values(ascending=False)
lines = []
lines.append('# 策略周报 %s\n' % last.date())
lines.append('## 核心卫星策略当前信号\n')
lines.append('- 黄金打底腿(518880): 永久持有50%')
lines.append('- 轮动腿目标: **%s (%s)**  动量分 %.4f' % (POOL.get(target, '空仓'), target, m[best] if target != 'CASH' else 0))
lines.append('- 若目标分<=0则轮动半仓空仓\n')
lines.append('## 12腿动量分排名(60/250日)\n')
lines.append('| 排名 | ETF | 代码 | 动量分 | 60日涨幅 |')
lines.append('|---|---|---|---|---|')
for i, (c, v) in enumerate(risk_rank.items(), 1):
    r60 = df[c].iloc[-1] / df[c].iloc[-61] - 1
    lines.append('| %d | %s | %s | %.4f | %.1f%% |' % (i, POOL[c], c, v, r60 * 100))
lines.append('\n数据: 腾讯K线前复权, 截至%s收盘。与QMT持仓核对: 若QMT轮动腿与目标不一致, 下月末调仓将自动纠正。' % last.date())
os.makedirs(OUT, exist_ok=True)
fp = os.path.join(OUT, '策略周报_%s.md' % last.strftime('%Y%m%d'))
open(fp, 'w', encoding='utf-8').write('\n'.join(lines))
# 追加信号日志
logfp = os.path.join(OUT, '策略信号日志.csv')
hdr = not os.path.exists(logfp)
with open(logfp, 'a', encoding='utf-8') as f:
    if hdr:
        f.write('date,target,score\n')
    f.write('%s,%s,%.4f\n' % (last.date(), target, m[best] if target != 'CASH' else 0))
print('REPORT:', fp)
print('TARGET:', target, 'SCORE: %.4f' % (m[best] if target != 'CASH' else 0))
