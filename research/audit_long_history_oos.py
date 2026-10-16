# -*- coding: utf-8 -*-
# 审计补课①: 用指数代理把核心卫星规则回测拉回2014年(IS/OOS真检验)
# 规则: 与已部署策略完全一致(50%黄金打底+48%月频60/250双动量), 参数不做任何重调
# 指数代理: 沪深300/中证500/上证50/创业板指 + 黄金ETF 518880(2013年上市)
# 覆盖: 2015股灾, 2016熔断, 2018贸易战熊, 2019-2021牛, 2022-2024熊, 2025牛
import json, time, urllib.request
import numpy as np
import pandas as pd

def fetch_day(code, start='2013-01-01', end='2026-12-31'):
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

NAMES = {'sh000300': '沪深300', 'sh000905': '中证500', 'sh000016': '上证50',
         'sz399006': '创业板指', 'sh518880': '黄金ETF'}
print('拉取长历史(2013起)...')
df = pd.DataFrame({c: fetch_day(c) for c in NAMES}).sort_index().ffill(limit=5)
for c in df.columns:
    s = df[c].dropna()
    print(f'  {NAMES[c]:8s} {len(s)}根 {s.index[0].date()}~{s.index[-1].date()}')

GOLD = 'sh518880'
POOL = ['sh000300', 'sh000905', 'sh000016', 'sz399006']
sub = df[POOL + [GOLD]].dropna()
print('共同窗口:', sub.index[0].date(), '~', sub.index[-1].date(), len(sub), '天')

def stats(curve):
    c = curve.dropna()
    ret = c.pct_change().dropna()
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    cagr = (c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1
    dd = (c / c.cummax() - 1).min()
    shp = ret.mean() / ret.std() * np.sqrt(244) if ret.std() > 0 else 0
    return dict(cagr=round(cagr * 100, 1), maxdd=round(dd * 100, 1),
                calmar=round(cagr / abs(dd), 2), sharpe=round(shp, 2))

def run_coresat(df, l1=60, l2=250, w_gold=0.5, w_risk=0.48, cost=0.001):
    """与已部署QMT策略完全同规则: 月末信号, 次日收盘成交, 风险腿动量<=0则现金"""
    idx = df.index
    rets = df.pct_change()
    mom = df[POOL].pct_change(l1) * 0.5 + df[POOL].pct_change(l2) * 0.5
    me = df.index.to_series().groupby([df.index.year, df.index.month]).max()
    is_sig = pd.Series(df.index.isin(me.values), index=df.index)
    dates = list(idx)
    gold_eq, rot_eq, cur, curve = 1.0, 1.0, 'CASH', {}
    for i in range(1, len(dates)):
        dt = dates[i]
        ps = None
        if is_sig.loc[dt]:
            m = mom.loc[dt].dropna()
            if len(m):
                b = m.idxmax()
                ps = b if m[b] > 0 else 'CASH'
        tc = 0.0
        if ps is not None and ps != cur:
            tc = cost * 2
            cur = ps
        r = 0.0 if cur == 'CASH' else (0.0 if pd.isna(rets.loc[dt, cur]) else float(rets.loc[dt, cur]))
        rot_eq *= (1 + r - tc)
        g = 0.0 if pd.isna(rets.loc[dt, GOLD]) else float(rets.loc[dt, GOLD])
        gold_eq *= (1 + g)
        curve[dt] = w_gold * gold_eq + w_risk * rot_eq
    return pd.Series(curve)

cv = run_coresat(sub)
print('\n=== 2014-2026 全窗口(12.8年, 三轮熊市) 核心卫星同规则 ===')
print('全窗口:', stats(cv))
for a, b, name in [('2014-01-01', '2015-12-31', '2014-2015(含股灾)'),
                   ('2016-01-01', '2018-12-31', '2016-2018(含贸易战熊)'),
                   ('2019-01-01', '2021-12-31', '2019-2021(结构牛)'),
                   ('2022-01-01', '2026-10-16', '2022-2026(本轮)')]:
    seg = cv[(cv.index >= a) & (cv.index <= b)]
    if len(seg) > 100:
        print(f'  {name}:', stats(seg))
yr = cv.groupby(cv.index.year).last()
ys = pd.concat([pd.Series([1.0], index=[cv.index[:1][0] - pd.Timedelta(days=1)]), yr.iloc[:-1]])
print('年度%:', {int(a): round(float(b), 1) for a, b in zip(yr.index, (yr.values / ys.values - 1) * 100)})
cv.to_csv(r'C:/Users/Administrator/Desktop/QMT/数据输出/longhistory_coresat_curve.csv', encoding='utf-8')

# 基准
b300 = df['sh000300'].dropna(); b300 = b300[b300.index >= sub.index[0]]
print('\n同期沪深300买入持有:', stats(b300 / b300.iloc[0]))
bg = df[GOLD].dropna(); bg = bg[bg.index >= sub.index[0]]
print('同期黄金ETF买入持有:', stats(bg / bg.iloc[0]))
print('DONE')
