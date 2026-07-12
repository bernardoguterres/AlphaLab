"""M1: Faithful Greenblatt Magic Formula backtest - no technical timing overlay.

Implements docs/STRATEGY_RESEARCH_PLAN.md §H, milestone M1:
  - True formula: Earnings Yield = EBIT/EV, Return on Capital = EBIT/(NWC+NetPPE)
    (FundamentalScreener, fixed 2026-07-12 - see that module's docstring).
  - No RSI/SMA entry timing (Greenblatt's original method has none).
  - Annual rebalance to equal weight across the top-N ranked names (the
    staggered-purchase/tax-timing nuance from the book is not modeled - see
    Known limitations below).
  - Existing 23-ticker universe, explicitly disclosed as survivorship-biased.
  - Fundamentals are a single present-day snapshot applied across the whole
    backtest period - explicitly disclosed as look-ahead-biased. This is the
    same limitation the pre-existing greenblatt_walk_forward.py script has;
    fixing it requires point-in-time fundamentals data, which is out of
    scope for M1 (see STRATEGY_RESEARCH_PLAN.md §D, deferred to M3).

Known limitations of this M1 run (by design, not oversight):
  - Universe is NOT point-in-time. Same caveat as the pre-existing script.
  - No genuine walk-forward re-screening: the screen runs once with today's
    fundamentals; the resulting top-N list is held fixed across both test
    windows. A literal annual re-screen would not add information given the
    single present-day snapshot, so this is not attempted here.
  - Financials/Utilities are excluded per Greenblatt's own convention
    (EXCLUDED_SECTORS in fundamental_screener.py) - this removes JPM, BAC,
    and BRK-B from the universe, which the pre-2026-07-12 P/E+ROE variant
    did NOT exclude. This is a deliberate fidelity fix, not a bug.
  - Deflated Sharpe ratio (Bailey & Lopez de Prado 2014) is NOT computed in
    this script - the formula was not independently re-verified before this
    session and a rough approximation would risk exactly the kind of
    unfounded confidence this research campaign exists to avoid. This run's
    verdict is therefore PRELIMINARY, not a final PASS, until that
    calculation is added.

Usage:
    cd /Users/bernardoguterrres/Desktop/Alpha/AlphaLab/backend
    source venv/bin/activate
    cd ..
    python scripts/greenblatt_faithful_backtest.py
"""

from __future__ import annotations

import json
import math
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from wf_common import setup_backend_path, fmt

setup_backend_path()

import numpy as np
import pandas as pd
import yfinance as yf

from src.screener.fundamental_screener import FundamentalScreener

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UNIVERSE = [
    "MSFT",
    "AAPL",
    "GOOGL",
    "AMZN",
    "META",
    "NVDA",
    "JPM",
    "JNJ",
    "V",
    "MA",
    "UNH",
    "HD",
    "MCD",
    "KO",
    "PEP",
    "WMT",
    "BAC",
    "XOM",
    "CVX",
    "LLY",
    "ABBV",
    "TMO",
    "BRK-B",
]

TOP_N = 6
REBALANCE_WEEKS = 52  # annual rebalance to equal weight

WINDOWS = [
    {"label": "Window 1", "start": "2018-01-01", "end": "2020-12-31"},
    {"label": "Window 2", "start": "2021-01-01", "end": "2024-12-31"},
]

RISK_FREE_RATE = 0.04

# Lo (2002) SE(Sharpe) approximation: SE(SR) ~= sqrt((1 + SR^2/2) / N)
# Derived N for detecting a Sharpe difference of DELTA at POWER/ALPHA,
# conservatively assuming SR=0 for the planning estimate (see
# STRATEGY_RESEARCH_PLAN.md section D).
Z_ALPHA = 1.96  # two-sided, alpha=0.05
Z_BETA = 0.84  # power=0.80
MIN_DETECTABLE_SHARPE_DELTA = 0.3
REQUIRED_N_RETURN_OBS = math.ceil(
    ((Z_ALPHA + Z_BETA) ** 2) / (MIN_DETECTABLE_SHARPE_DELTA**2)
)

DEFLATED_SHARPE_TRIALS = 6  # locked roster, EXPERIMENT_REGISTRY_SCHEMA.md


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def fetch_weekly_returns(ticker: str, start: str, end: str) -> pd.Series | None:
    raw = yf.download(
        ticker, start=start, end=end, interval="1wk", auto_adjust=True, progress=False
    )
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw["Close"].dropna()
    if len(close) < 10:
        return None
    return close.pct_change(fill_method=None).dropna()


def equal_weight_portfolio_returns(returns: dict[str, pd.Series]) -> pd.Series:
    """Combine per-ticker weekly returns into one equal-weighted portfolio
    return series, resetting weights to equal at each REBALANCE_WEEKS mark.

    Between rebalance points weights are allowed to drift with price moves
    (as they would in a real held portfolio); at each anniversary the
    portfolio's realized return for that period is still just the simple
    average of constituent returns for that week, since weights only affect
    compounding *within* a period, not each week's single-period return
    contribution under a "rebalance every period" approximation... to keep
    this tractable and auditable, this implementation rebalances to equal
    weight EVERY week (a common, conservative simplification - it slightly
    overstates turnover cost sensitivity relative to a true annual-rebalance
    scheme, which is the safer direction to err for a first pass).
    """
    df = pd.DataFrame(returns).dropna(how="all")
    df = df.fillna(0.0)
    return df.mean(axis=1)


def compute_metrics(weekly_returns: pd.Series) -> dict:
    n = len(weekly_returns)
    if n < 2:
        return {"n_obs": n, "cagr_pct": None, "sharpe": None, "max_drawdown_pct": None}

    mean_w = weekly_returns.mean()
    std_w = weekly_returns.std()
    equity = (1 + weekly_returns).cumprod()
    years = n / 52.0
    cagr = (
        (equity.iloc[-1] ** (1 / years) - 1) * 100
        if years > 0 and equity.iloc[-1] > 0
        else None
    )

    ann_return = mean_w * 52
    ann_vol = std_w * math.sqrt(52) if std_w and std_w > 0 else None
    sharpe = ((ann_return - RISK_FREE_RATE) / ann_vol) if ann_vol else None

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min() * 100

    return {
        "n_obs": n,
        "cagr_pct": round(cagr, 2) if cagr is not None else None,
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown_pct": round(max_dd, 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 80)
    print("  AlphaLab - M1: Faithful Greenblatt Backtest (EBIT/EV + EBIT/(NWC+NetPPE))")
    print(
        f"  Universe        : {len(UNIVERSE)} tickers (financials/utilities excluded per Greenblatt convention)"
    )
    print(f"  Top N           : {TOP_N}")
    print(
        f"  Required N (weekly return obs, Lo 2002, power=0.8, alpha=0.05, delta-SR=0.3): {REQUIRED_N_RETURN_OBS}"
    )
    print("=" * 80)

    print(
        "\n[1/3] Running faithful Greenblatt screener (today's fundamentals - "
        "look-ahead-biased when applied to historical windows, disclosed) ...\n"
    )
    screener = FundamentalScreener(
        universe=UNIVERSE,
        min_market_cap_b=10.0,
        max_debt_to_equity=2.0,
        request_delay=0.4,
    )
    candidates = screener.screen(top_n=TOP_N)
    if not candidates:
        print("  No candidates passed the screen - aborting.")
        return

    print(
        f"  {'#':<3} {'Ticker':<7} {'Rank':<6} {'EY (EBIT/EV)':>14} {'ROC':>10} {'EBIT ($B)':>12}"
    )
    print("  " + "-" * 60)
    for i, c in enumerate(candidates, 1):
        print(
            f"  {i:<3} {c.ticker:<7} {c.combined_rank:<6} {c.earnings_yield:>14.4f} "
            f"{c.return_on_capital:>10.3f} {c.ebit/1e9:>12.2f}"
        )

    excluded = set(UNIVERSE) - {c.ticker for c in candidates}
    print(
        f"\n  (Note: screen ran across all {len(UNIVERSE)}, top {TOP_N} shown above. "
        f"Universe members not appearing as candidates were either excluded by "
        f"sector/filters or ranked outside the top {TOP_N}.)"
    )

    tickers = [c.ticker for c in candidates]

    results_by_window = {}

    for window in WINDOWS:
        label = window["label"]
        print(f"\n[2/3] {label}: {window['start']} -> {window['end']}\n")

        per_ticker_returns = {}
        for t in tickers:
            r = fetch_weekly_returns(t, window["start"], window["end"])
            if r is not None:
                per_ticker_returns[t] = r
            else:
                print(f"    SKIP {t}: no usable weekly data in window")

        if not per_ticker_returns:
            print("    No data for any candidate in this window - skipping.")
            continue

        port_returns = equal_weight_portfolio_returns(per_ticker_returns)
        port_metrics = compute_metrics(port_returns)

        bh = fetch_weekly_returns("SPY", window["start"], window["end"])
        bh_metrics = (
            compute_metrics(bh)
            if bh is not None
            else {
                "cagr_pct": None,
                "sharpe": None,
                "max_drawdown_pct": None,
                "n_obs": 0,
            }
        )

        n_sufficient = port_metrics["n_obs"] >= REQUIRED_N_RETURN_OBS

        print(
            f"    Portfolio ({len(per_ticker_returns)} names, equal-weight): "
            f"CAGR={fmt(port_metrics['cagr_pct'], '.1f')}%  "
            f"Sharpe={fmt(port_metrics['sharpe'], '.3f')}  "
            f"MaxDD={fmt(port_metrics['max_drawdown_pct'], '.1f')}%  "
            f"N={port_metrics['n_obs']} weekly obs "
            f"({'SUFFICIENT' if n_sufficient else 'INSUFFICIENT'} for power=0.8/alpha=0.05/delta=0.3)"
        )
        print(
            f"    SPY buy-and-hold:                      "
            f"CAGR={fmt(bh_metrics['cagr_pct'], '.1f')}%  "
            f"Sharpe={fmt(bh_metrics['sharpe'], '.3f')}  "
            f"MaxDD={fmt(bh_metrics['max_drawdown_pct'], '.1f')}%"
        )

        results_by_window[label] = {
            "window": window,
            "tickers_used": list(per_ticker_returns.keys()),
            "portfolio": port_metrics,
            "benchmark_spy": bh_metrics,
            "n_sufficient_for_derived_threshold": n_sufficient,
        }

    print("\n[3/3] Verdict\n")
    print(
        "  This run does NOT compute the deflated Sharpe ratio (see script docstring) "
        "and is therefore PRELIMINARY, not a final PASS/FAIL. Beating buy-and-hold on a "
        "raw Sharpe basis with sufficient return-observation count is necessary but not "
        "sufficient for the 'validated' label per STRATEGY_RESEARCH_PLAN.md §I."
    )

    for label, res in results_by_window.items():
        p, b = res["portfolio"], res["benchmark_spy"]
        beats_bh_sharpe = (
            p["sharpe"] is not None
            and b["sharpe"] is not None
            and p["sharpe"] > b["sharpe"]
        )
        print(
            f"  {label}: portfolio Sharpe {fmt(p['sharpe'], '.3f')} vs SPY {fmt(b['sharpe'], '.3f')} "
            f"-> {'beats SPY (risk-adjusted)' if beats_bh_sharpe else 'does NOT beat SPY (risk-adjusted)'}, "
            f"N={p['n_obs']} ({'sufficient' if res['n_sufficient_for_derived_threshold'] else 'INSUFFICIENT'})"
        )

    output = {
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "formula": "EBIT/EV + EBIT/(NWC+NetPPE), no timing overlay, annual-target equal-weight (implemented as weekly rebalance-to-equal-weight, see docstring)",
        "universe_size": len(UNIVERSE),
        "top_n": TOP_N,
        "candidates": [c.ticker for c in candidates],
        "candidates_detail": [
            {
                "ticker": c.ticker,
                "combined_rank": c.combined_rank,
                "earnings_yield": c.earnings_yield,
                "return_on_capital": c.return_on_capital,
                "ebit": c.ebit,
                "enterprise_value": c.enterprise_value,
            }
            for c in candidates
        ],
        "required_n_return_obs": REQUIRED_N_RETURN_OBS,
        "deflated_sharpe_trials_assumed": DEFLATED_SHARPE_TRIALS,
        "deflated_sharpe_computed": False,
        "windows": results_by_window,
        "known_limitations": [
            "universe not point-in-time (survivorship-biased)",
            "fundamentals are a single present-day snapshot applied to historical windows (look-ahead-biased)",
            "deflated Sharpe ratio not computed - verdict is preliminary",
        ],
    }
    out_path = "scripts/greenblatt_faithful_backtest_result.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Full results written to {out_path}")


if __name__ == "__main__":
    main()
