# QMT (XunTou) Quant Research Chronicle: A-Share ETF Monthly Momentum Rotation (passorder Built-in Python Backtest · 7-Leg Rotation · Monthly Rebalance · Retail Quant · Long-Horizon Audit · Final Verdict)

**Keywords**: QMT · XunTou · A-share · China stock · ETF · momentum rotation · monthly rebalance · backtest · passorder · ContextInfo · retail quant · personal quant · high-frequency trading · institutional vs retail · AI quant · final verdict

[简体中文](README.md) | [繁體中文](README.zh-TW.md) | [English](README.en.md)

> ⚠️ Disclaimer: Everything in this repository is for educational and research purposes only. Nothing here constitutes investment advice. A-share markets are risky; past backtests do not guarantee future returns. Trade at your own risk.

One-line intro: a complete research chronicle of an A-share ETF monthly momentum rotation strategy — QMT built-in Python strategies, standalone backtest scripts, a 12.8-year out-of-sample audit, lessons learned the hard way, and the final verdict after days of research. No backtest numbers are shown here on purpose: run the scripts yourself and draw your own conclusions.

## What's In Here · What Each Piece Does

| Location | Purpose |
|---|---|
| `strategies/etf_rotation_monthly_live.py` | **Live strategy**: paste into the QMT strategy editor and run (GBK + pure-ASCII source, dodging encoding pitfalls); auto-rebalances via `passorder` at 14:45 on the last trading day of each month |
| `strategies/etf_rotation_monthly_backtest.py` | **Backtest strategy**: same logic with built-in NAV accounting; produces equity curves inside QMT's backtest panel |
| `strategies/template_decade_skeleton.py` | **Decade-scale live-trading skeleton template**: starting point for writing your own long-horizon strategy |
| `research/backtest_etf_rotation.py` | **Main backtest script**: local Python3 + pandas, quotes auto-fetched from Tencent's free API, no QMT needed |
| `research/audit_long_history_oos.py` | **Long-horizon audit**: 12.8-year out-of-sample validation — does the favorable-window result survive bear markets |
| `research/sweep_ten_year_window.py` | Ten-year window sweep: run different eras separately to see whether parameters only worked in a few years |
| `research/cross_validation.py` | Cross-source data validation: multiple data providers, so dirty data can't fool you |
| `research/data_health_check.py` | Adjustment-consistency check: if forward-adjusted and raw prices disagree, that's a trap |
| `tools/qmt_code_checker.py` | **QMT strategy checker**: static checks on encoding/syntax/entry functions — run it before pasting into QMT |
| `tools/weekly_monitor.py` | Weekly auto-monitoring + report generation |
| `docs/` | **9 documents**: backtest methodology (look-ahead bias / costs / overfitting / out-of-sample), audit reports, go-live checklist, compliance notes, PTrade migration |
| `results/` | Backtest outputs (equity curves, result JSONs). Look at the numbers yourself; draw your own conclusions |

**How to use**: read [docs/backtest_methodology.md](docs/backtest_methodology.md) first (look-ahead bias, costs, parameter overfitting, out-of-sample validation — skip any of these four gates and every backtest is self-deception), then reproduce with `research/backtest_etf_rotation.py`, and only then decide whether to touch QMT.

## The Final Verdict: For Ordinary People, This Theory Is Useless

After all these days of research, the math boils down to one sentence: **for an ordinary person, building your own QMT setup is useless.**

Before you object, look at the context.

### What Era Are We In

Compute is inflating, and large models are in an arms race. On the institutional side: trading desks wired straight into the exchange, colocation squeezing latency down to microseconds, Level-2 tick data burned like air, large models digging for factors around the clock, a dozen researchers and an entire IT department behind every single strategy.

On your side: a Windows PC, a brokerage-issued client, free daily bars, latency measured in milliseconds, one person doing the jobs of researcher, sysadmin, risk manager, and trader all at once, parameters tuned by hand, the whole thing revocable by a single regulatory notice.

This is not the same game. The two fields aren't even in the same hemisphere.

### Institutional QMT vs. Your DIY QMT

| | Institutional QMT | Your DIY QMT |
|---|---|---|
| Speed | Colocated, microseconds | Home broadband, milliseconds — three orders of magnitude apart |
| Data | Full Level-2 tick feed | Free daily bars, real-time feed gutted |
| Compute | Clusters + LLMs mining factors 24/7 | You probably don't even own a consumer GPU |
| Team | Researchers / IT / risk, all specialized | One person doing everything |
| Lifeline | A compliance team tracking regulation | One regulatory notice wipes it to zero |

Bluntly: an institutional QMT is a weapon; a DIY QMT is a toy. Nothing wrong with playing with a toy — as long as you know what you're playing with.

### So What Happens When an Individual Trades QMT — Especially High-Frequency?

To be blunt: an individual running HFT on QMT has one of three scripted deaths:

1. **Killed by speed.** By the time you see the signal, the institution's order is already queued at the exchange. Every "opportunity" you catch is liquidity someone else handed you.
2. **Ground down by costs.** HFT margins are razor-thin to begin with. Commissions, slippage, and market impact shave off three layers; even at retail-friendly rates, you're working for your broker.
3. **Killed by yourself.** No risk team to hit the brakes for you. One crash candle plus one manual intervention, and a hundred days of discipline go up in smoke.

### The Stronger AI Gets, the Clearer This Should Be

This wave of large models has pushed the cost of factor mining and report parsing down to the floor. You think using AI for quant means you've caught up with the times — but institutions run the same AI, faster, deeper, and cheaper than you. **In an era of compute inflation, information asymmetry is no longer a moat, because your opponent's information updates faster than yours.**

What advantage does an individual still have? Exactly one: **no redemption pressure, free to sit in cash, free to be slow.** And slow strategies — monthly rotation, say — are precisely the ones that need no QMT at all. That's the cruelest irony of this whole project: after all the tinkering, we found the only defensible way to play is one that never needed this system.

### So

After all these days of research, the conclusion fits in one line: **for ordinary people, this QMT theory is useless — its entire value is letting you see, with your own eyes, the gap between you and the institutions, and then slow down willingly.**

Once you see it, treat QMT as a learning project, not a money machine. The code stays in this repository; the lessons live in docs. As for high-frequency — that's the institutions' arms race. When an individual walks onto that field, they're the fuel.

## License

[MIT](LICENSE) — use the code freely; carry the risk yourself.
