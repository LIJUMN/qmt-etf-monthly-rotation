#encoding:gbk
# ==============================================================
#  TEMPLATE: long-horizon (10y) LIVE-TRADING skeleton for QMT
#  Rule 0: read the official docs first (see the AI handover note).
#          Every API below was checked against the official KB.
#
#  Design rules baked in:
#   1) DAILY signal only. Never use 60m as the signal source.
#   2) Live model-trading mode runs at TICK level, regardless of the
#      period -> per-day de-dup is MANDATORY (see run()).
#   3) State must survive restart -> restore from the broker account
#      at init. An in-memory ledger alone WILL double-buy after a restart.
#   4) If the broker account cannot be read in live mode -> DO NOT TRADE.
#   5) The risk gate is separate from the strategy and can only REDUCE risk.
#   6) Logs are ASCII only (the GBK console swallows Chinese output).
#   7) Python 3.6 syntax. No walrus, no dataclasses.
#
#  Sections:  1 params  2 state  3 restore  4 data  5 indicators
#             6 signal/exec  7 risk gate  8 reconciliation
# ==============================================================
import numpy as np

# ---------- 1. PARAMS (single source of truth) ----------
STOCK      = '588000.SH'      # zero-adjustment ETF only (pitfall list #1)
ACC_ID     = '200000001'
CASH_INIT  = 100000.0
DATA_START = '20200101'

FAST, SLOW, SIG = 12, 26, 9   # textbook MACD, do NOT optimise
HIST_LEN   = 120
CASH_USE   = 0.97             # use 97% of cash per entry
LOT        = 100

MAX_DD     = 0.35             # halt new entries beyond -35% drawdown
DAY_LOSS   = 0.05             # halt for the rest of the day beyond -5%
LOSS_LIMIT = 3                # N consecutive losing trades ...
COOL_DAYS  = 20               # ... pause new entries for N trading days
STRAT_NAME = 'tenyear'


# ---------- 2. STATE (module-level, survives the ContextInfo rollback) ----------
class G():
    pass


g = G()


def init(ContextInfo):
    g.acc = ACC_ID
    g.stock = STOCK
    g.cash = CASH_INIT
    g.shares = 0
    g.entry_cost = 0.0
    g.peak = CASH_INIT
    g.day_start_eq = CASH_INIT
    g.last_day = ''
    g.loss_streak = 0
    g.cool = 0
    g.live_ok = False
    ContextInfo.set_universe([g.stock])
    try:
        download_history_data(g.stock, '1d', DATA_START, '')
    except Exception as e:
        print('INIT download ERR %s' % e)
    restore_state(ContextInfo)
    print('INIT ok %s cash %.2f shares %d' % (g.stock, g.cash, g.shares))


# ---------- 3. RESTORE / MODE ----------
def is_backtest(ContextInfo):
    try:
        return bool(ContextInfo.do_back_test)
    except Exception:
        return True          # safe default: treat as backtest, never touch the account


def restore_state(ContextInfo):
    if is_backtest(ContextInfo):
        g.live_ok = True     # backtest uses the local ledger (pitfall list #2)
        print('RESTORE backtest mode, local ledger')
        return
    try:
        accs = get_trade_detail_data(g.acc, 'STOCK', 'ACCOUNT')
        if not accs:
            print('RESTORE ALERT no account object -> TRADING DISABLED')
            return
        g.cash = float(accs[0].m_dAvailable)
        vol = 0
        for p in get_trade_detail_data(g.acc, 'STOCK', 'POSITION'):
            if '%s.%s' % (p.m_strInstrumentID, p.m_strExchangeID) == g.stock:
                vol = int(p.m_nVolume)
        g.shares = vol
        g.peak = max(g.cash + g.shares * 1.0, CASH_INIT)
        g.live_ok = True
        print('RESTORE live ok cash %.2f shares %d' % (g.cash, g.shares))
    except Exception as e:
        print('RESTORE ALERT %s -> TRADING DISABLED' % e)


# ---------- 4. DATA ----------
def day_of(ContextInfo):
    try:
        d = timetag_to_datetime(ContextInfo.get_bar_timetag(ContextInfo.barpos), '%Y%m%d')
        if d is not None and len(str(d)) == 8:
            return str(d)
    except Exception:
        pass
    import time
    return time.strftime('%Y%m%d')       # fallback for tick-level live mode


def get_closes(ContextInfo, day, n=HIST_LEN):
    try:
        d = ContextInfo.get_market_data_ex(['close'], [g.stock], period='1d',
                                           end_time=day, count=n,
                                           dividend_type='front', subscribe=False)
        df = d.get(g.stock)
        if df is None or len(df) == 0:
            return None
        v = [float(x) for x in df['close'].values]
    except Exception as e:
        print('FETCH_ERR %s' % e)
        return None
    out = [x for x in v if x == x and x > 0]
    if len(out) < n // 2:
        return None
    a = np.array(out, dtype=float)
    for i in range(1, len(a)):                    # corporate-action guard
        r = a[i] / a[i - 1]
        if r < 0.80 or r > 1.30:
            a = np.concatenate([a[:i] * r, a[i:]])
    return a


# ---------- 5. INDICATORS ----------
def ema(v, s):
    k = 2.0 / (s + 1)
    o = [v[0]]
    for x in v[1:]:
        o.append(o[-1] + k * (x - o[-1]))
    return np.array(o)


def equity(px):
    return g.cash + g.shares * px


# ---------- 7. RISK GATE (can only say "no") ----------
def allow_open(px):
    eq = equity(px)
    if eq > g.peak:
        g.peak = eq
    dd = 0.0 if g.peak <= 0 else (g.peak - eq) / g.peak
    if dd >= MAX_DD:
        print('RISK halt: drawdown %.1f%%' % (dd * 100))
        return False
    if g.cool > 0:
        print('RISK halt: cooling %d days' % g.cool)
        return False
    return True


# ---------- 8. RECONCILIATION (ledger vs broker) ----------
def verify(ContextInfo):
    if is_backtest(ContextInfo) or not g.live_ok:
        return
    try:
        real = 0
        for p in get_trade_detail_data(g.acc, 'STOCK', 'POSITION'):
            if '%s.%s' % (p.m_strInstrumentID, p.m_strExchangeID) == g.stock:
                real = int(p.m_nVolume)
        if real != g.shares:
            print('RECON ALERT ledger %d vs broker %d -> adopt broker' % (g.shares, real))
            g.shares = real
        accs = get_trade_detail_data(g.acc, 'STOCK', 'ACCOUNT')
        if accs:
            g.cash = float(accs[0].m_dAvailable)
        print('RECON ok cash %.2f shares %d' % (g.cash, g.shares))
    except Exception as e:
        print('RECON ERR %s' % e)


# ---------- 6. MAIN ----------
def handlebar(ContextInfo):
    try:
        run(ContextInfo)
    except Exception as e:
        print('ERR handlebar %s' % e)


def run(ContextInfo):
    day = day_of(ContextInfo)
    if day == '' or day == g.last_day:
        return                      # (2) live mode fires per tick -> act once per day

    a = get_closes(ContextInfo, day)
    if a is None:
        return                      # no data yet this day; retry on the next tick

    dif = ema(a, FAST) - ema(a, SLOW)
    dea = ema(dif, SIG)
    px = float(a[-1])
    eq = equity(px)
    if eq > g.peak:
        g.peak = eq

    if g.shares > 0 and g.day_start_eq > 0:
        if (eq - g.day_start_eq) / g.day_start_eq <= -DAY_LOSS:
            print('RISK halt for the day: day loss limit')
            g.last_day = day
            g.day_start_eq = eq
            return

    up = dif[-1] > dea[-1] and dif[-2] <= dea[-2]
    dn = dif[-1] < dea[-1] and dif[-2] >= dea[-2]

    if not g.live_ok:
        print('HALT: account not readable, no order sent')
        g.last_day = day
        return

    acted = True
    if g.shares == 0 and up:
        if allow_open(px):
            sh = int(g.cash * CASH_USE / px / LOT) * LOT
            if sh >= LOT:
                passorder(23, 1101, g.acc, g.stock, 5, 0, sh, STRAT_NAME, 1, '', ContextInfo)
                g.cash -= sh * px
                g.entry_cost = sh * px
                g.shares = sh
                print('BUY %s %d %.3f' % (day, sh, px))
            else:
                print('SKIP buy: cash too small')
        else:
            acted = False
    elif g.shares > 0 and dn:
        sell = int(g.shares)
        if sell >= LOT:
            passorder(24, 1101, g.acc, g.stock, 5, 0, sell, STRAT_NAME, 1, '', ContextInfo)
            pnl = sell * px - g.entry_cost
            g.cash += sell * px
            g.shares = 0
            g.entry_cost = 0.0
            if pnl < 0:
                g.loss_streak += 1
            else:
                g.loss_streak = 0
            if g.loss_streak >= LOSS_LIMIT:
                g.cool = COOL_DAYS
                g.loss_streak = 0
            print('SELL %s %d %.3f pnl %.2f' % (day, sell, px, pnl))
    else:
        acted = False

    if acted:
        g.last_day = day            # one action per day
    else:
        g.last_day = day            # no signal -> day is done, housekeeping below
    if g.cool > 0:
        g.cool -= 1
    g.day_start_eq = equity(px)
    verify(ContextInfo)
