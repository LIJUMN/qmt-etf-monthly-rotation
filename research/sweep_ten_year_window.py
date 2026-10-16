# -*- coding: utf-8 -*-
"""十年窗口扫掠:2016-10-14 ~ 2026-10-14,10万本金,收益最大化对比
- 满仓MACD(v3冠军逻辑) x 53品种
- 躺平持有
- 动量轮动(每月持有最强ETF,含/不含MA60过滤)
- 成本:佣金万2.5最低5元双边+滑点0.1%,个股卖出加印花税0.05%
"""
import json, os

DATA = r'C:/Users/Administrator/Desktop/QMT/数据与因子/历史数据_不复权'
OUT = r'C:/Users/Administrator/Desktop/QMT/我的策略/_十年窗口扫掠.json'
START = '2016-10-14'
CAPITAL = 100000.0


def desplit(c, kind='ETF'):
    lo, hi = (0.92, 1.08) if kind == 'STOCK' else (0.90, 1.12)
    c = list(c)
    for i in range(1, len(c)):
        if c[i - 1] <= 0:
            continue
        r = c[i] / c[i - 1]
        if r < lo or r > hi:
            c = [x * r for x in c[:i]] + c[i:]
    return c


def load_all():
    out = {}
    for fn in os.listdir(DATA):
        if not fn.endswith('.json') or fn.startswith('_'):
            continue
        d = json.load(open(os.path.join(DATA, fn), encoding='utf-8'))
        if d['count'] < 250:
            continue
        raw_c = [r['close'] for r in d['kline']]
        c = raw_c if d['kind'] == 'INDEX' else desplit(raw_c, d['kind'])
        out[fn.replace('.json', '')] = {
            'code': d['code'], 'kind': d['kind'], 'name': d.get('name', ''),
            'dates': [r['date'] for r in d['kline']], 'c': c,
        }
    return out


def ema(v, span):
    k = 2.0 / (span + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(out[-1] + k * (x - out[-1]))
    return out


def ma(v, span):
    out, s = [], 0.0
    for i, x in enumerate(v):
        s += x
        if i >= span:
            s -= v[i - span]
        out.append(s / min(i + 1, span))
    return out


def fee(kind, amt, side):
    f = max(5.0, amt * 0.00025)
    if kind == 'STOCK' and side == 'sell':
        f += amt * 0.0005
    return f


def run_single(d, strat='macd'):
    """满仓MACD:信号在收盘i确认,收盘i成交。窗口前用全历史热身EMA。"""
    c, dates = d['c'], d['dates']
    dif = [x - y for x, y in zip(ema(c, 12), ema(c, 26))]
    dea = ema(dif, 9)
    kind = d['kind']
    cash, shares, trades = CAPITAL, 0, 0
    peak, mdd = CAPITAL, 0.0
    eq_curve = []
    for i in range(1, len(c)):
        in_win = dates[i] >= START
        if in_win:
            if shares == 0 and dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
                px = c[i] * 1.001
                sh = int(cash * 0.98 / px / 100) * 100
                if sh >= 100:
                    cash -= sh * px + fee(kind, sh * px, 'buy')
                    shares = sh
                    trades += 1
            elif shares > 0 and dif[i] < dea[i] and dif[i - 1] >= dea[i - 1]:
                px = c[i] * 0.999
                cash += shares * px - fee(kind, shares * px, 'sell')
                shares = 0
                trades += 1
        eq = cash + shares * c[i]
        if in_win:
            peak = max(peak, eq)
            mdd = max(mdd, (peak - eq) / peak)
            eq_curve.append((dates[i], eq))
    fin = cash + shares * c[-1]
    return {'fin': fin, 'ret': fin / CAPITAL - 1, 'mdd': mdd, 'trades': trades,
            'holding': shares > 0, 'curve': eq_curve}


def bh_window(d):
    c, dates = d['c'], d['dates']
    idx = [i for i, x in enumerate(dates) if x >= START]
    i0 = idx[0]
    px0 = c[i0]
    sh = int(CAPITAL * 0.98 / (px0 * 1.001) / 100) * 100
    cash = CAPITAL - sh * px0 * 1.001 - fee(d['kind'], sh * px0 * 1.001, 'buy')
    kind = d['kind']
    fin = cash + sh * c[-1] - fee(kind, sh * c[-1], 'sell')
    return fin / CAPITAL - 1


def run_rotation(data, use_filter=True, top_n=1, mom_days=60):
    """动量轮动:每月首个交易日,用昨天收盘算动量排名,今天收盘调仓。只做ETF。"""
    pool = {k: d for k, d in data.items() if d['kind'] == 'ETF'}
    keys = sorted(pool)
    dates_set = set()
    for k in keys:
        dates_set.update(pool[k]['dates'])
    dates = sorted(dates_set)
    dates = [x for x in dates if x >= START]
    ma60 = {k: ma(pool[k]['c'], 60) for k in keys}
    di = {k: {dt: i for i, dt in enumerate(pool[k]['dates'])} for k in keys}
    close = {k: pool[k]['c'] for k in keys}

    def px_of(k, dt):
        i = di[k].get(dt)
        return close[k][i] if i is not None else None

    held, cash, trades = None, CAPITAL, 0
    peak, mdd, curve = CAPITAL, 0.0, []
    last_month = None
    for dt in dates:
        prev_dt = None
        # 昨天排名:对每只ETF,找 dt 当天的索引 i,用 i-1 的动量
        scores = []
        for k in keys:
            i = di[k].get(dt)
            if i is None or i < mom_days + 1:
                continue
            p_now = close[k][i - 1]
            p_past = close[k][i - 1 - mom_days]
            if p_past <= 0:
                continue
            mom = p_now / p_past - 1
            if use_filter and p_now < ma60[k][i - 1]:
                continue
            if mom <= 0 and use_filter:
                continue
            scores.append((mom, k))
        scores.sort(reverse=True)
        target = scores[0][1] if scores else None
        # 月度调仓:月份切换才动
        month = dt[:7]
        if month != last_month:
            last_month = month
            if target != held:
                if held is not None:
                    px = px_of(held, dt)
                    if px:
                        sh = shares_held
                        cash += sh * px * 0.999 - fee('ETF', sh * px * 0.999, 'sell')
                        trades += 1
                if target is not None:
                    px = px_of(target, dt)
                    if px:
                        sh = int(cash * 0.98 / (px * 1.001) / 100) * 100
                        if sh >= 100:
                            cash -= sh * px * 1.001 + fee('ETF', sh * px * 1.001, 'buy')
                            shares_held = sh
                            trades += 1
                            held = target
                            eqv = cash + shares_held * px
                            peak = max(peak, eqv)
                            curve.append((dt, eqv))
                            continue
                if target is None and held is not None:
                    held = None
        # 记净值
        if held is not None:
            px = px_of(held, dt)
            if px is None:
                i = di[held].get(dt)
            eqv = cash + (shares_held * px if px else cash * 0)
        else:
            eqv = cash
        peak = max(peak, eqv)
        mdd = max(mdd, (peak - eqv) / peak)
        curve.append((dt, eqv))
    fin = eqv
    return {'fin': fin, 'ret': fin / CAPITAL - 1, 'mdd': mdd, 'trades': trades,
            'curve': curve}


data = load_all()
print('品种数:', len(data), ' 窗口:', START, '~ 最新')

# 1) 单品种满仓MACD + 躺平
rows = []
for key in sorted(data):
    d = data[key]
    if d['dates'][-1] < START:
        continue
    r = run_single(d)
    bh = bh_window(d)
    in_win = sum(1 for x in d['dates'] if x >= START)
    if in_win < 200:
        continue
    rows.append({'key': key, 'code': d['code'], 'kind': d['kind'], 'name': d.get('name', ''),
                 'strat_fin': round(r['fin']), 'strat_ret': r['ret'], 'mdd': r['mdd'],
                 'trades': r['trades'], 'holding': r['holding'],
                 'bh_ret': bh, 'years': in_win / 244.0,
                 'first_in_win': next(x for x in d['dates'] if x >= START)})

rows.sort(key=lambda x: -x['strat_fin'])
print('\n=== 满仓MACD 十年窗口 TOP 20(按期末资产) ===')
print('%-16s %-8s %10s %8s %7s %6s %8s %s' % ('品种', '代码', '期末资产', '策略收益', '躺平', '回撤', '笔数', '窗口起点'))
for x in rows[:20]:
    print('%-16s %-8s %10d %7.1f%% %6.1f%% %5.1f%% %5d %s' % (
        x['key'], x['code'], x['strat_fin'], x['strat_ret'] * 100, x['bh_ret'] * 100,
        x['mdd'] * 100, x['trades'], x['first_in_win']))

# 2) 动量轮动
print('\n=== 动量轮动(每月最强ETF) ===')
for flt in (True, False):
    rr = run_rotation(data, use_filter=flt)
    print('  MA60过滤=%s: 期末 %d (%.1f%%)  回撤 %.1f%%  %d笔' % (
        flt, rr['fin'], rr['ret'] * 100, rr['mdd'] * 100, rr['trades']))
    if not flt:
        rot_noflt = rr
    else:
        rot_flt = rr

json.dump({'rows': rows, 'rotation_filter': {k: v for k, v in rot_flt.items() if k != 'curve'},
           'rotation_nofilter': {k: v for k, v in rot_noflt.items() if k != 'curve'},
           'rotation_curve_nofilter': rot_noflt['curve']},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n已存:', OUT)

# 3) 冠军明细:打印前十名各自的关键交易(供人工核对)
champ = rows[0]
d = data[champ['key']]
r = run_single(d)
print('\n冠军:', champ['key'], champ['name'], ' 期末:', round(r['fin']))
