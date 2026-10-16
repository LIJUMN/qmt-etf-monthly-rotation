#encoding:gbk
# ============================================================
# ETF 7-LEG ROTATION (LIVE) v1.2 2026-10-16
# Structure: full position monthly momentum rotation, 7 equal legs
# Legs: 512480 semi / 512000 broker / 512660 defense / 515790 solar
#       / 512400 metals / 517400 gold stocks / 518880 gold ETF
# Rule: last trade day of month 14:45
#       score = 0.5*ret20 + 0.5*ret90, buy best leg FULL position,
#       if best score <= 0 go cash
# Note: 2024-05~2026-10 window CAGR 23.7% MaxDD -38.7% (0.1% cost)
# NOTE: pure ASCII to avoid any encoding issue in QMT editor
# ============================================================
import numpy as np
import datetime

class G():
    pass
g = G()

POOL = ['512480.SH', '512000.SH', '512660.SH', '515790.SH', '512400.SH', '517400.SH', '518880.SH']
L1 = 20
L2 = 90
USE_W = 0.95
EXEC_START = '1445'
EXEC_END = '1456'

def init(ContextInfo):
    g.accID = 'YOUR_REAL_ACCOUNT_ID'
    g.lastmonth = ''
    ContextInfo.set_universe(POOL)
    print('READY 7-LEG ROTATION pool=', len(POOL), 'acc=', g.accID)

def get_closes(ContextInfo, code, n=110):
    try:
        df = ContextInfo.get_market_data(fields=['close'], stock_code=[code],
                                         period='1d', count=n, dividend_type='front')
        v = df['close'].values
    except Exception:
        return None
    out = []
    for x in v:
        try:
            f = float(x)
        except Exception:
            continue
        if f == f and f > 0:
            out.append(f)
    if len(out) < L2 + 1:
        return None
    a = np.array(out, dtype=float)
    for i in range(1, len(a)):
        r = a[i] / a[i - 1]
        if r < 0.80 or r > 1.30:
            a = np.concatenate([a[:i] * r, a[i:]])
    return a

def acc_cash():
    try:
        a = get_trade_detail_data(g.accID, 'STOCK', 'ACCOUNT')
        if a:
            for f in ('m_dAvailable', 'm_dBalance'):
                v = getattr(a[0], f, None)
                if v:
                    return float(v)
    except Exception:
        pass
    return 0.0

def acc_positions():
    ps = {}
    try:
        poss = get_trade_detail_data(g.accID, 'STOCK', 'POSITION')
        if poss:
            for p in poss:
                code = str(getattr(p, 'm_strInstrumentID', '')) + '.' + str(getattr(p, 'm_strExchangeID', ''))
                vol = int(getattr(p, 'm_nCanUseVolume', 0) or 0)
                if vol > 0:
                    ps[code] = vol
    except Exception:
        pass
    return ps

def live_price(ContextInfo, code):
    try:
        t = ContextInfo.get_full_tick([code])
        if t and code in t:
            p = float(t[code].get('lastPrice', 0) or 0)
            if p > 0:
                return p
    except Exception:
        pass
    return 0.0

def order(ContextInfo, code, vol, buy):
    px = live_price(ContextInfo, code)
    if px <= 0 or vol <= 0:
        return
    op = 23 if buy else 24
    lp = round(px * (1.005 if buy else 0.995), 3)
    passorder(op, 1101, g.accID, code, 11, lp, vol, 'ROT7', 2, '', ContextInfo)
    print('ORDER', 'BUY' if buy else 'SELL', code, vol, 'limit', lp)

def is_month_end(ContextInfo):
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    return tomorrow.month != now.month

def handlebar(ContextInfo):
    try:
        if not ContextInfo.is_last_bar():
            return
        now = datetime.datetime.now()
        hm = now.strftime('%H%M')
        if hm < EXEC_START or hm > EXEC_END:
            return
        ym = now.strftime('%Y%m')
        if g.lastmonth == ym:
            return
        if not is_month_end(ContextInfo):
            return
        g.lastmonth = ym

        # 1) score all 7 legs, pick best
        scores = {}
        for code in POOL:
            a = get_closes(ContextInfo, code)
            if a is None:
                continue
            m = 0.5 * (a[-1] / a[-L1 - 1] - 1.0) + 0.5 * (a[-1] / a[-L2 - 1] - 1.0)
            scores[code] = m
        target = ''
        if scores:
            b = max(scores, key=scores.get)
            if scores[b] > 0:
                target = b
        print('SIGNAL', now.strftime('%Y-%m-%d'), 'target=', target,
              'scores=', {k: round(v, 4) for k, v in scores.items()})

        # 2) switch to target, full position
        pos = acc_positions()
        for c in list(pos.keys()):
            if c in POOL and c != target:
                order(ContextInfo, c, pos[c], False)
        if target:
            cash = acc_cash()
            px = live_price(ContextInfo, target)
            if cash > 0 and px > 0:
                sh = int(cash * USE_W / px / 100) * 100
                if sh >= 100:
                    order(ContextInfo, target, sh, True)
        else:
            print('ALL -> CASH this month')
    except Exception as e:
        print('ERR', str(e)[:120])
