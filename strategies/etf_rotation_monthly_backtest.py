#encoding:gbk
# ============================================================
# ETF 7-LEG ROTATION (BACKTEST) v1.4 2026-10-16
# Same logic as LIVE version: 7 legs full-position monthly
# momentum rotation. score = 0.5*ret20 + 0.5*ret90,
# buy best, best<=0 -> cash.
# v1.4 FIXES (vs v1.3):
# 1) daily mark-to-market was dead: get_closes(min-len check)
#    rejected 3-bar requests -> NAV frozen between rebalances.
#    now min-len adapts to request size.
# 2) data anchored with start_time/end_time at current bar
#    (count-only requests return LATEST bars in backtest = look-ahead)
# 3) real passorder orders on rebalance -> QMT stats panel,
#    position detail and trade history all populate.
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
FEE = 0.001

def init(ContextInfo):
    g.prev_month = ''
    g.target = ''
    g.nav = 1.0
    g.peak = 1.0
    g.mdd = 0.0
    ContextInfo.set_universe(POOL)
    print('BACKTEST READY v1.4: 7-LEG MONTHLY ROTATION (mtm fixed)')

def bar_date(ContextInfo):
    try:
        t = ContextInfo.get_bar_timetag(ContextInfo.barpos)
        return datetime.datetime.fromtimestamp(t / 1000.0)
    except Exception:
        return datetime.datetime.now()

def get_closes(ContextInfo, code, n, d):
    """closes strictly up to backtest bar date d. min-len adapts to n."""
    try:
        start = (d - datetime.timedelta(days=n * 2 + 30)).strftime('%Y%m%d')
        end = d.strftime('%Y%m%d')
        df = ContextInfo.get_market_data(fields=['close'], stock_code=[code],
                                         period='1d', start_time=start, end_time=end,
                                         count=n, dividend_type='front')
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
    need = 2 if n <= 10 else L2 + 1
    if len(out) < need:
        return None
    a = np.array(out, dtype=float)
    for i in range(1, len(a)):
        r = a[i] / a[i - 1]
        if r < 0.80 or r > 1.30:
            a = np.concatenate([a[:i] * r, a[i:]])
    return a

def bt_state(ContextInfo):
    cash, pos = 0.0, {}
    try:
        acc = ContextInfo.accID
        a = get_trade_detail_data(acc, 'STOCK', 'ACCOUNT')
        if a:
            for f in ('m_dAvailable', 'm_dBalance'):
                v = getattr(a[0], f, None)
                if v and float(v) > 0:
                    cash = float(v)
                    break
        ps = get_trade_detail_data(acc, 'STOCK', 'POSITION')
        if ps:
            for p in ps:
                code = str(getattr(p, 'm_strInstrumentID', '')) + '.' + str(getattr(p, 'm_strExchangeID', ''))
                vol = int(getattr(p, 'm_nCanUseVolume', 0) or 0)
                if vol > 0:
                    pos[code] = vol
    except Exception:
        pass
    return cash, pos

def bt_order(ContextInfo, code, vol, buy, d):
    try:
        a = get_closes(ContextInfo, code, 3, d)
        if a is None or vol <= 0:
            return
        px = a[-1]
        op = 23 if buy else 24
        lp = round(px * (1.005 if buy else 0.995), 3)
        passorder(op, 1101, ContextInfo.accID, code, 11, lp, vol, 'ROT7-BT', 2, '', ContextInfo)
        print('BT-ORDER', 'BUY' if buy else 'SELL', code, vol, 'limit', lp)
    except Exception as e:
        print('BT-ORDER SKIP', str(e)[:80])

def handlebar(ContextInfo):
    try:
        d = bar_date(ContextInfo)
        ym = '%04d%02d' % (d.year, d.month)

        # daily mark-to-market of current holding (anchored data)
        rr = 0.0
        if g.target:
            rk = get_closes(ContextInfo, g.target, 3, d)
            if rk is not None:
                pr = rk[-2] if len(rk) >= 2 else rk[-1]
                rr = rk[-1] / pr - 1.0
        g.nav *= (1.0 + rr)
        g.peak = max(g.peak, g.nav)
        if g.peak > 0:
            g.mdd = min(g.mdd, g.nav / g.peak - 1.0)
        try:
            ContextInfo.paint('NAV', g.nav, 'draw_above', 'line', 'red')
        except Exception:
            pass

        # rebalance at first bar of new month (signal = data up to prev bar)
        if ym != g.prev_month:
            g.prev_month = ym
            d_prev = d - datetime.timedelta(days=1)
            scores = {}
            for code in POOL:
                a = get_closes(ContextInfo, code, L2 + 2, d_prev)
                if a is None or len(a) < L2 + 1:
                    continue
                a_sig = a[:-1]
                if len(a_sig) < L2 + 1:
                    continue
                m = 0.5 * (a_sig[-1] / a_sig[-L1 - 1] - 1.0) + 0.5 * (a_sig[-1] / a_sig[-L2 - 1] - 1.0)
                scores[code] = m
            new_target = ''
            if scores:
                b = max(scores, key=scores.get)
                if scores[b] > 0:
                    new_target = b

            # engine orders so position detail / history populate
            cash, pos = bt_state(ContextInfo)
            if cash > 0 or pos:
                for c in list(pos.keys()):
                    if c in POOL and c != new_target:
                        bt_order(ContextInfo, c, pos[c], False, d)
                if new_target:
                    cash2, pos2 = bt_state(ContextInfo)
                    px = get_closes(ContextInfo, new_target, 3, d)
                    if px is not None and cash2 > 0:
                        sh = int(cash2 * 0.95 / px[-1] / 100) * 100
                        if sh >= 100:
                            bt_order(ContextInfo, new_target, sh, True, d)

            # virtual NAV accounting (independent cross-check)
            if new_target != g.target:
                g.nav *= (1.0 - FEE * 2)
            old = g.target
            g.target = new_target
            print('REBAL %04d-%02d target=%s (old=%s) NAV=%.4f MaxDD=%.1f%%' % (
                d.year, d.month, new_target if new_target else 'CASH',
                old if old else 'CASH', g.nav, g.mdd * 100))
    except Exception as e:
        print('ERR', str(e)[:120])
