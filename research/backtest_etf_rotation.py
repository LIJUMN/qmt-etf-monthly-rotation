# -*- coding: utf-8 -*-
# ETF高波动轮动研究：真实行情(腾讯K线) -> 动量轮动回测 -> 参数网格 -> 分段稳健性
# 产出: 数据输出/etf_rotation_results.json, 数据输出/etf_rotation_equity.png
import json, time, urllib.request, os, sys
import numpy as np
import pandas as pd

BASE = r'C:/Users/Administrator/Desktop/QMT'
OUT = os.path.join(BASE, '数据输出')
os.makedirs(OUT, exist_ok=True)

CANDIDATES = {
    'sh512480': '半导体ETF',
    'sh517400': '黄金股ETF',
    'sh512000': '券商ETF',
    'sh512660': '军工ETF',
    'sh515790': '光伏ETF',
    'sh512400': '有色金属ETF',
    'sh518880': '黄金ETF(避险)',
    'sh159915': '创业板ETF',
    'sh510300': '沪深300(基准)',
}
START = '2019-01-01'
END = '2026-12-31'

def fetch_day(code, start=START, end=END):
    """腾讯日K，等比前复权。从end向前按640根分页。返回 pd.Series(close, index=date)"""
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
        time.sleep(0.25)
    s = pd.Series(out).sort_index()
    s.index = pd.to_datetime(s.index)
    return s

print('拉取行情中...')
closes = {}
for code, name in CANDIDATES.items():
    try:
        s = fetch_day(code)
        closes[code] = s
        print(f'  {code} {name}: {len(s)}根  {s.index[0].date()} ~ {s.index[-1].date()}')
    except Exception as e:
        print(f'  {code} {name}: 失败 {e}')
df = pd.DataFrame(closes).dropna(how='all').sort_index()
df = df.ffill(limit=5)

# 数据体检: 单日跌幅>18% 视为除权/坏点
bad = []
for c in df.columns:
    r = df[c].pct_change()
    n_bad = int((r < -0.18).sum())
    if n_bad: bad.append((c, n_bad))
print('坏点检查(单日<-18%):', bad if bad else '无')

# ---- 轮动池: 6条高波动腿 (剔除基准和避险腿, 避险腿作为绝对动量兜底) ----
MODE = sys.argv[1] if len(sys.argv) > 1 else 'short'
if MODE == 'short':
    POOL = ['sh512480', 'sh517400', 'sh512000', 'sh512660', 'sh515790', 'sh512400']
    SAFE = 'sh518880'
else:  # long: 全部用上市早的ETF, 2020-12起 5.8年验证
    POOL = ['sh512480', 'sh159915', 'sh512000', 'sh512660', 'sh515790', 'sh512400']
    SAFE = 'sh518880'
    CANDIDATES['sh159915'] = '创业板ETF'
    CANDIDATES.pop('sh517400', None)
sub = df[POOL + [SAFE]].dropna()
print(f'轮动池共同历史: {len(sub)}个交易日  {sub.index[0].date()} ~ {sub.index[-1].date()}')

# 相关性
corr = df[POOL].dropna().pct_change().corr()
print('池内平均两两相关: %.3f' % corr.values[np.triu_indices(len(POOL), 1)].mean())

def backtest(df, l1, l2, safe_mode, topn=1, cost=0.001, rebal_wday=4):
    """信号: 0.5*r(l1)+0.5*r(l2); 周五信号, 次日收盘成交; safe_mode: none/gold/cash"""
    closes = df[POOL]
    safe_c = df[SAFE]
    mom = closes.pct_change(l1) * 0.5 + closes.pct_change(l2) * 0.5
    mom_safe = safe_c.pct_change(l1) * 0.5 + safe_c.pct_change(l2) * 0.5
    week_end = df.index.to_series().groupby(df.index.isocalendar().week.astype(int) * 100 + df.index.year).max()
    is_sig = pd.Series(df.index.isin(week_end.values), index=df.index)
    holdings = {}  # date -> asset chosen at that close (trade next close)
    for dt in df.index:
        if is_sig.loc[dt]:
            m = mom.loc[dt]
            m = m.dropna()
            if len(m) == 0: continue
            best = m.idxmax()
            if safe_mode == 'gold' and m.max() <= 0:
                best = SAFE if mom_safe.loc[dt] > 0 else 'CASH'
            elif safe_mode == 'cash' and m.max() <= 0:
                best = 'CASH'
            holdings[dt] = best
    # 执行: 信号日收盘决定, 次日收盘换仓
    idx = df.index
    dates = list(idx)
    rets = df.pct_change()
    equity = 1.0
    curve = {}
    cur_asset = 'CASH'
    for i in range(1, len(dates)):
        dt = dates[i]
        prev_sig = holdings.get(dates[i-1])
        trade_cost = 0.0
        if prev_sig is not None and prev_sig != cur_asset:
            trade_cost = cost * 2  # 卖旧+买新
            cur_asset = prev_sig
        if cur_asset == 'CASH':
            r = 0.0
        else:
            r = rets[POOL + [SAFE]].loc[dt].get(cur_asset, 0.0)
            r = 0.0 if pd.isna(r) else float(r)
        equity *= (1 + r - trade_cost)
        curve[dt] = equity
    return pd.Series(curve)

def stats(curve):
    c = curve.dropna()
    if len(c) < 100: return None
    ret = c.pct_change().dropna()
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    cagr = (c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1
    dd = (c / c.cummax() - 1).min()
    sharpe = ret.mean() / ret.std() * np.sqrt(244) if ret.std() > 0 else 0
    return dict(cagr=round(cagr*100,1), maxdd=round(dd*100,1),
                calmar=round(cagr/abs(dd),2) if dd != 0 else 0, sharpe=round(sharpe,2))

# ---- 参数网格 ----
grid = []
for (l1, l2) in [(10,40),(10,60),(20,60),(20,90),(20,120),(40,120),(60,120),(20,40),(10,120)]:
    for safe in ['gold','cash','none']:
        try:
            cv = backtest(sub, l1, l2, safe)
            st = stats(cv)
            if st: grid.append(dict(l1=l1, l2=l2, safe=safe, **st))
        except Exception as e:
            print('grid err', l1, l2, safe, e)
g = pd.DataFrame(grid).sort_values('calmar', ascending=False)
print('\n=== 参数网格 Top10 (按Calmar) ===')
print(g.head(10).to_string(index=False))

# ---- 基准对比 ----
bench = {}
for code in POOL + [SAFE, 'sh510300']:
    s = df[code].dropna()
    s = s[s.index >= sub.index[0]]
    st = stats(s / s.iloc[0])
    if st: bench[CANDIDATES[code]] = st
print('\n=== 买入持有基准 ===')
print(pd.DataFrame(bench).T.to_string())

# ---- 最优参数分段稳健性 ----
best = g.iloc[0]
i0, i1, i2 = sub.index[0], sub.index[len(sub)//2], sub.index[-1]
seg1 = backtest(sub[sub.index <= i1], int(best.l1), int(best.l2), best.safe)
seg2 = backtest(sub[sub.index >= i1], int(best.l1), int(best.l2), best.safe)
print('\n=== 最优参数(%s/%s/%s)分段 ===' % (best.l1, best.l2, best.safe))
print('前半段', stats(seg1), ' 后半段', stats(seg2))

# ---- 保存 ----
curve_all = backtest(sub, int(best.l1), int(best.l2), best.safe)
# 年度收益
yr = curve_all.groupby(curve_all.index.year).last()
yr_prev = pd.concat([pd.Series([1.0], index=[curve_all.index[0] - pd.Timedelta(days=1)]), yr.iloc[:-1]])
yr_ret = (yr.values / yr_prev.values - 1) * 100
yearly = {int(k): round(float(v), 1) for k, v in zip(yr.index, yr_ret)}
print('\n年度收益%:', yearly)
res = {
    'pool': {c: CANDIDATES[c] for c in POOL},
    'best_params': dict(best),
    'grid_top10': g.head(10).to_dict('records'),
    'bench': bench,
    'segments': {'H1': stats(seg1), 'H2': stats(seg2)},
    'window': [str(sub.index[0].date()), str(sub.index[-1].date())],
    'corr_mean': round(float(corr.values[np.triu_indices(len(POOL),1)].mean()), 3),
}
with open(os.path.join(OUT, f'etf_rotation_results_{MODE}.json'), 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2, default=str)

# 曲线图
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(11, 6))
    curve_all.plot(ax=ax, lw=2, label='轮动策略(最优参数)')
    b300 = df['sh510300'].dropna(); b300 = b300[b300.index >= sub.index[0]]
    (b300 / b300.iloc[0]).plot(ax=ax, lw=1.2, alpha=0.8, label='沪深300')
    for c in ['sh512480', 'sh517400', 'sh512000']:
        s = df[c].dropna(); s = s[s.index >= sub.index[0]]
        (s / s.iloc[0]).plot(ax=ax, lw=1, alpha=0.5, label=CANDIDATES[c])
    ax.legend(); ax.set_title('ETF动量轮动回测 %s ~ %s (含0.1%%单边成本)' % (res['window'][0], res['window'][1]))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f'etf_rotation_equity_{MODE}.png'), dpi=130)
    print('\n图已保存')
except Exception as e:
    print('绘图失败:', e)
print('\nDONE')
