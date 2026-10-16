# -*- coding: utf-8 -*-
import json, os

DIR = r'C:/Users/Administrator/Desktop/QMT/数据与因子/历史数据_不复权'

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

def load_all(prefix='ETF_'):
    out = {}
    for fn in sorted(os.listdir(DIR)):
        if not fn.startswith(prefix) or not fn.endswith('.json') or fn.startswith('_'):
            continue
        d = json.load(open(os.path.join(DIR, fn), encoding='utf-8'))
        if d['count'] < 250:
            continue
        out[fn.replace('.json', '')] = desplit([r['close'] for r in d['kline']], d['kind'])
    return out

def ema(v, span):
    k = 2.0 / (span + 1)
    o = [v[0]]
    for x in v[1:]:
        o.append(o[-1] + k * (x - o[-1]))
    return o

def ma(v, n):
    n = max(1, n)
    o, s = [], 0.0
    for i, x in enumerate(v):
        s += x
        if i >= n:
            s -= v[i - n]
        o.append(s / min(i + 1, n))
    return o

def run(c, sig):
    cash, sh, tr = 100000.0, 0, 0
    for i in range(1, len(c)):
        if sig[i] == 1 and sh == 0:
            px = c[i] * 1.001
            n = int(cash * 0.98 / px / 100) * 100
            if n >= 100:
                cash -= n * px + max(5.0, n * px * 0.00025)
                sh = n
                tr += 1
        elif sig[i] == -1 and sh > 0:
            px = c[i] * 0.999
            cash += sh * px - max(5.0, sh * px * 0.00025)
            sh = 0
            tr += 1
    return cash + sh * c[-1] - 100000, tr

def sig_macd(c, f, s, g, exma):
    dif = [x - y for x, y in zip(ema(c, f), ema(c, s))]
    dea = ema(dif, g)
    m = ma(c, exma) if exma > 0 else None
    sg = [0] * len(c)
    for i in range(2, len(c)):
        if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            sg[i] = 1
        elif (dif[i] < dea[i] and dif[i - 1] >= dea[i - 1]) or (m is not None and c[i] < m[i]):
            sg[i] = -1
    return sg

CANDS = [
    ('MACD12-26-9_ex0', (12, 26, 9, 0)),
    ('MACD6-19-6_ex20', (6, 19, 6, 20)),
    ('MACD5-35-5_ex20', (5, 35, 5, 20)),
    ('MACD8-17-9_ex20', (8, 17, 9, 20)),
    ('MACD8-17-9_ex10', (8, 17, 9, 10)),
    ('MACD10-20-7_ex20', (10, 20, 7, 20)),
    ('MACD12-26-9_ex20', (12, 26, 9, 20)),
    ('Don20-10', None),
]

def sig_don(c, n=20, m=10):
    sg = [0] * len(c)
    h = False
    for i in range(1, len(c)):
        hi = max(c[max(0, i - n):i]) if i > 1 else c[0]
        lo = min(c[max(0, i - m):i]) if i > 1 else c[0]
        if not h and c[i] > hi:
            sg[i] = 1
            h = True
        elif h and c[i] < lo:
            sg[i] = -1
            h = False
    return sg

etfs = load_all('ETF_')
print('ETF 品种数: %d' % len(etfs))
print('%-20s %8s %8s %8s %8s' % ('配置', '平均收益', '中位收益', '跑赢躺平', '正收益'))
summary = {}
for name, prm in CANDS:
    rets, bh_rets, wins, pos = [], [], 0, 0
    for k, c in etfs.items():
        sg = sig_don(c) if prm is None else sig_macd(c, *prm)
        p, tr = run(c, sg)
        b = c[-1] / c[0] * 100000 - 100000
        rets.append(p)
        bh_rets.append(b)
        wins += 1 if p > b else 0
        pos += 1 if p > 0 else 0
    n = len(rets)
    srt = sorted(rets)
    med = srt[n // 2]
    avg = sum(rets) / n
    summary[name] = {'avg': avg, 'med': med, 'win': wins, 'pos': pos, 'n': n}
    print('%-20s %8.0f %8.0f %5d/%d %5d/%d' % (name, avg, med, wins, n, pos, n))

json.dump(summary, open(r'C:/Users/Administrator/Desktop/QMT/我的策略/_交叉验证.json', 'w'), ensure_ascii=False, indent=1)
print('\n（赚的钱按 10 万本金、满仓、扣佣金滑点计的绝对金额）')
