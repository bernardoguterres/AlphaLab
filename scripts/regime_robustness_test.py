"""Multi-regime robustness test for the two live experiments (faithful
Greenblatt portfolio, sector rotation) - extends both to the full regime
set docs/STRATEGY_RESEARCH_PLAN.md section D calls for (2008 crisis,
2015-2019 grind, 2020 COVID crash, 2022 rate-hike bear), which had NOT
actually been run - only the two overlapping 2018-2020/2021-2024 windows
had. Also adds the equal-weight-of-the-same-universe benchmark
(equal_weight_benchmark.py, new 2026-07-12) alongside SPY buy-and-hold and
the Faber overlay, to control for the fact that 2018-2024 was a period of
extreme mega-cap-tech concentration in cap-weighted SPY - a confound that
made "beats SPY buy-and-hold" a weaker signal than it looked.

NOT a re-optimization: uses the exact same fixed parameters as the already-
registered experiments (Greenblatt: top_n=6, rebalance=52w; sector
rotation: top_n=4, rebalance=4w, sma=26w). No parameter was chosen or
adjusted based on this run's results - this is a robustness check on
already-fixed methodology, not a new search.

Sector ETF universe availability varies by window: XLC (Communication
Services) launched 2018-06-19, XLRE (Real Estate) launched 2015-10-07 - the
9 original SPDR sectors go back to 1998. Windows before those dates
automatically use a smaller, explicitly-reported universe rather than
silently truncating the whole backtest to whenever the last-listed ETF
started trading (which is what would happen if the full-universe date
intersection were used naively - see universe_for_window() below).

Usage:
    cd AlphaLab/backend && source venv/bin/activate && cd ..
    python scripts/regime_robustness_test.py
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from wf_common import setup_backend_path, fmt

setup_backend_path()

import pandas as pd
import yfinance as yf

from src.screener.fundamental_screener import FundamentalScreener
from src.screener.relative_strength_ranker import RelativeStrengthRanker, SPDR_SECTOR_ETFS
from src.backtest.portfolio_constructor import PortfolioConstructor
from src.backtest.equal_weight_benchmark import equal_weight_benchmark
from src.backtest.metrics import PerformanceMetrics
from src.backtest.deflated_sharpe import deflated_sharpe_ratio
from src.backtest.faber_overlay import faber_overlay_returns

N_TRIALS = 6
SMA_WEEKS = 26
WARMUP_WEEKS = SMA_WEEKS + 5

GREENBLATT_UNIVERSE = [
    "MSFT", "AAPL", "GOOGL", "AMZN", "META", "NVDA", "JPM", "JNJ",
    "V", "MA", "UNH", "HD", "MCD", "KO", "PEP", "WMT", "BAC",
    "XOM", "CVX", "LLY", "ABBV", "TMO", "BRK-B",
]
GREENBLATT_TOP_N = 6
GREENBLATT_REBALANCE_WEEKS = 52

SECTOR_TOP_N = 4
SECTOR_REBALANCE_WEEKS = 4

SECTOR_INCEPTIONS = {
    "XLC": "2018-06-19",
    "XLRE": "2015-10-07",
    # all other SPDR sector ETFs: 1998-12-16
}

REGIME_WINDOWS = [
    {"label": "2008 Crisis", "start": "2007-06-01", "end": "2009-12-31"},
    {"label": "2015-2019 Grind", "start": "2015-01-01", "end": "2019-12-31"},
    {"label": "2020 COVID", "start": "2020-01-01", "end": "2020-12-31"},
    {"label": "2022 Bear", "start": "2022-01-01", "end": "2022-12-31"},
]


def fetch_weekly_close(ticker: str, start: str, end: str, min_bars: int = 10) -> pd.DataFrame | None:
    raw = yf.download(ticker, start=start, end=end, interval="1wk", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw[["Close"]].dropna()
    return close if len(close) >= min_bars else None


def fetch_monthly_close(ticker: str, start: str, end: str, warmup_months: int = 12) -> pd.Series | None:
    warmup_start = (pd.Timestamp(start) - pd.DateOffset(months=warmup_months)).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=warmup_start, end=end, interval="1mo", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    return raw["Close"].dropna()


def sector_universe_for_window(window_start: str) -> list[str]:
    """Only include sector ETFs that existed (with warmup room) before the
    window starts - prevents a late-inception ETF from silently truncating
    the whole backtest via PortfolioConstructor's full-universe date
    intersection in dynamic mode."""
    ws = pd.Timestamp(window_start)
    usable = []
    for t in SPDR_SECTOR_ETFS:
        inception = pd.Timestamp(SECTOR_INCEPTIONS.get(t, "1998-12-16"))
        if inception + pd.Timedelta(weeks=WARMUP_WEEKS) <= ws:
            usable.append(t)
    return usable


def compute_metrics_and_dsr(equity_curve, ledger, window_start_ts):
    in_window = [p for p in equity_curve if p["date"] >= window_start_ts]
    calc = PerformanceMetrics(risk_free_rate=0.04)
    metrics = calc.calculate_all(equity_curve=in_window, trades=ledger)
    ret, risk = metrics["returns"], metrics["risk"]
    n_obs = len(in_window)
    sharpe = risk.get("sharpe_ratio", 0.0) or 0.0
    skew = ret.get("skewness", 0.0) or 0.0
    kurtosis_pearson = (ret.get("kurtosis", 0.0) or 0.0) + 3.0
    dsr = None
    if n_obs >= 2:
        dsr = deflated_sharpe_ratio(
            sharpe_annualized=sharpe, skewness=skew, kurtosis_pearson=kurtosis_pearson,
            n_observations=n_obs, n_trials=N_TRIALS, periods_per_year=52,
        )
    return {"cagr_pct": ret.get("cagr_pct"), "sharpe": sharpe, "n_obs": n_obs, "dsr": dsr}


def faber_benchmark_for_window(window_start: str, window_end: str) -> dict | None:
    spy_monthly = fetch_monthly_close("SPY", window_start, window_end)
    if spy_monthly is None:
        return None
    overlay_rets = faber_overlay_returns(spy_monthly, sma_months=10).dropna()
    in_window = overlay_rets[overlay_rets.index >= pd.Timestamp(window_start)]
    if len(in_window) <= 1:
        return None
    equity = (1 + in_window).cumprod()
    years = len(in_window) / 12.0
    cagr = (equity.iloc[-1] ** (1 / years) - 1) * 100 if years > 0 else None
    ann_vol = in_window.std() * (12 ** 0.5)
    ann_ret = in_window.mean() * 12
    sharpe = (ann_ret - 0.04) / ann_vol if ann_vol > 0 else None
    return {"cagr_pct": round(cagr, 2) if cagr is not None else None, "sharpe": round(sharpe, 3) if sharpe is not None else None}


def spy_buyhold_for_window(window_start: str, window_end: str) -> dict | None:
    # A plain single-asset buy-and-hold - NOT routed through
    # PortfolioConstructor/equal_weight_benchmark, which both require >= 2
    # tickers (a "basket" of one isn't meaningful there). Computed directly
    # from weekly returns, same style as scripts/greenblatt_faithful_backtest.py.
    df = fetch_weekly_close("SPY", window_start, window_end)
    if df is None:
        return None
    rets = df["Close"].pct_change().dropna()
    n = len(rets)
    if n < 2:
        return None
    equity = (1 + rets).cumprod()
    years = n / 52.0
    cagr = (equity.iloc[-1] ** (1 / years) - 1) * 100 if years > 0 else None
    ann_ret = rets.mean() * 52
    ann_vol = rets.std() * (52**0.5)
    sharpe = (ann_ret - 0.04) / ann_vol if ann_vol and ann_vol > 0 else None
    return {
        "cagr_pct": round(cagr, 2) if cagr is not None else None,
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
    }


def run_greenblatt_regime(window, candidates):
    price_data = {}
    for c in candidates:
        df = fetch_weekly_close(c.ticker, window["start"], window["end"])
        if df is not None:
            price_data[c.ticker] = df
    if len(price_data) < 2:
        return None, None

    pc = PortfolioConstructor(top_n=GREENBLATT_TOP_N, rebalance_period_bars=GREENBLATT_REBALANCE_WEEKS)
    result = pc.run([c for c in candidates if c.ticker in price_data], price_data)
    strat_metrics = compute_metrics_and_dsr(result.equity_curve, result.final_portfolio.ledger, pd.Timestamp(window["start"]))

    ew_result = equal_weight_benchmark(price_data, rebalance_period_bars=GREENBLATT_REBALANCE_WEEKS)
    ew_metrics = compute_metrics_and_dsr(ew_result.equity_curve, ew_result.final_portfolio.ledger, pd.Timestamp(window["start"]))

    return strat_metrics, ew_metrics


def run_sector_rotation_regime(window):
    universe = sector_universe_for_window(window["start"])
    if len(universe) < 2:
        return None, None, universe

    # Warmup buffer BEFORE window start, so the 26-week SMA is already warm
    # at the window's first rebalance - without this, ranker.rank() would
    # find every candidate below the sma_weeks history requirement at bar 0
    # and PortfolioConstructor would skip rebalancing until ~26 weeks in.
    warmup_start = (pd.Timestamp(window["start"]) - pd.Timedelta(weeks=WARMUP_WEEKS)).strftime("%Y-%m-%d")
    price_data = {}
    for t in universe:
        df = fetch_weekly_close(t, warmup_start, window["end"])
        if df is not None:
            price_data[t] = df
    if len(price_data) < 2:
        return None, None, universe

    ranker = RelativeStrengthRanker(sma_weeks=SMA_WEEKS)
    pc = PortfolioConstructor(top_n=min(SECTOR_TOP_N, len(price_data)), rebalance_period_bars=SECTOR_REBALANCE_WEEKS)
    result = pc.run(price_data=price_data, rank_fn=ranker.rank)
    strat_metrics = compute_metrics_and_dsr(result.equity_curve, result.final_portfolio.ledger, pd.Timestamp(window["start"]))

    ew_result = equal_weight_benchmark(price_data, rebalance_period_bars=SECTOR_REBALANCE_WEEKS)
    ew_metrics = compute_metrics_and_dsr(ew_result.equity_curve, ew_result.final_portfolio.ledger, pd.Timestamp(window["start"]))

    return strat_metrics, ew_metrics, universe


def print_row(label, strat, ew, spy, faber):
    def fmt_ms(m):
        if m is None:
            return "  N/A  "
        return f"CAGR={fmt(m['cagr_pct'], '.1f')}% Sharpe={fmt(m['sharpe'], '.3f')}"

    print(f"    {label}")
    print(f"      Strategy:    {fmt_ms(strat)}" + (f"  DSR={strat['dsr'].deflated_sharpe_ratio:.3f}" if strat and strat.get("dsr") else ""))
    print(f"      Equal-wt:    {fmt_ms(ew)}")
    print(f"      SPY B&H:     {fmt_ms(spy)}")
    print(f"      Faber (SPY): {fmt_ms(faber)}")


def main():
    print("=" * 80)
    print("  Regime robustness test: Greenblatt portfolio + sector rotation")
    print(f"  New windows: {[w['label'] for w in REGIME_WINDOWS]}")
    print("  NOTE: same fixed parameters as the already-registered experiments - no re-tuning")
    print("=" * 80)

    screener = FundamentalScreener(universe=GREENBLATT_UNIVERSE, min_market_cap_b=10.0, max_debt_to_equity=2.0, request_delay=0.4)
    candidates = screener.screen(top_n=GREENBLATT_TOP_N)
    print(f"\nGreenblatt candidates (fixed across all windows, same look-ahead caveat as before): {[c.ticker for c in candidates]}")

    all_results = {"greenblatt": {}, "sector_rotation": {}}

    for window in REGIME_WINDOWS:
        label = window["label"]
        print(f"\n[{label}] {window['start']} -> {window['end']}")

        spy = spy_buyhold_for_window(window["start"], window["end"])
        faber = faber_benchmark_for_window(window["start"], window["end"])

        gb_strat, gb_ew = run_greenblatt_regime(window, candidates)
        print_row("Greenblatt faithful portfolio:", gb_strat, gb_ew, spy, faber)

        sr_strat, sr_ew, sr_universe = run_sector_rotation_regime(window)
        print(f"    Sector rotation universe this window: {sr_universe} ({len(sr_universe)} of 11)")
        print_row("Sector rotation:", sr_strat, sr_ew, spy, faber)

        all_results["greenblatt"][label] = {
            "strategy": _serialize(gb_strat), "equal_weight": _serialize(gb_ew),
            "spy_buyhold": spy, "faber_overlay": faber,
        }
        all_results["sector_rotation"][label] = {
            "strategy": _serialize(sr_strat), "equal_weight": _serialize(sr_ew),
            "spy_buyhold": spy, "faber_overlay": faber, "universe": sr_universe,
        }

    out_path = "scripts/regime_robustness_test_result.json"
    with open(out_path, "w") as f:
        json.dump({"run_date": datetime.now().strftime("%Y-%m-%d"), "n_trials": N_TRIALS, "results": all_results}, f, indent=2, default=str)
    print(f"\nFull results written to {out_path}")


def _serialize(m):
    if m is None:
        return None
    out = {"cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"], "n_obs": m["n_obs"]}
    if m.get("dsr"):
        out["deflated_sharpe_ratio"] = m["dsr"].deflated_sharpe_ratio
        out["significant_at_95pct"] = m["dsr"].significant_at_95pct
    return out


if __name__ == "__main__":
    main()
