"""M2 Part A: PortfolioConstructor exercised on the faithful Greenblatt screen.

Uses backend/src/backtest/portfolio_constructor.py (rank -> top-N -> sized
basket via the real Portfolio order-execution/cost model) instead of the
weekly-rebalance-to-equal-weight approximation used in
scripts/greenblatt_faithful_backtest.py (M1). Same universe, same screener,
same windows, same disclosed limitations (survivorship-biased universe,
look-ahead-biased single-snapshot fundamentals, no deflated Sharpe computed
here) - see that script's docstring and docs/STRATEGY_RESEARCH_PLAN.md §D/§H.

This is a genuine portfolio backtest (real slippage/commission per order,
real cash tracking, real annual rebalance-driven buy/sell orders) rather than
a returns-averaging approximation, so its numbers are expected to differ
slightly from the M1 script's - that's expected, not a bug, since M1 was
explicitly documented as "a common, conservative simplification."

Usage:
    cd /Users/bernardoguterrres/Desktop/Alpha/AlphaLab/backend
    source venv/bin/activate
    cd ..
    python scripts/greenblatt_portfolio_backtest.py
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
from src.backtest.portfolio_constructor import PortfolioConstructor
from src.backtest.metrics import PerformanceMetrics

UNIVERSE = [
    "MSFT", "AAPL", "GOOGL", "AMZN", "META", "NVDA", "JPM", "JNJ",
    "V", "MA", "UNH", "HD", "MCD", "KO", "PEP", "WMT", "BAC",
    "XOM", "CVX", "LLY", "ABBV", "TMO", "BRK-B",
]

TOP_N = 6
REBALANCE_WEEKS = 52  # annual, matching Greenblatt's own recommended cadence

WINDOWS = [
    {"label": "Window 1", "start": "2018-01-01", "end": "2020-12-31"},
    {"label": "Window 2", "start": "2021-01-01", "end": "2024-12-31"},
]


def fetch_weekly_close(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    raw = yf.download(ticker, start=start, end=end, interval="1wk",
                       auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw[["Close"]].dropna()
    if len(close) < 10:
        return None
    return close


def main():
    print("=" * 80)
    print("  AlphaLab - M2 Part A: PortfolioConstructor on faithful Greenblatt screen")
    print(f"  Universe: {len(UNIVERSE)} tickers, Top N: {TOP_N}, Rebalance: every {REBALANCE_WEEKS}w")
    print("=" * 80)

    screener = FundamentalScreener(
        universe=UNIVERSE, min_market_cap_b=10.0, max_debt_to_equity=2.0,
        request_delay=0.4,
    )
    candidates = screener.screen(top_n=TOP_N)
    if not candidates:
        print("  No candidates passed the screen - aborting.")
        return
    print(f"\n  Candidates: {[c.ticker for c in candidates]}\n")

    windows_out = {}

    for window in WINDOWS:
        label = window["label"]
        print(f"[{label}] {window['start']} -> {window['end']}")

        price_data = {}
        for c in candidates:
            df = fetch_weekly_close(c.ticker, window["start"], window["end"])
            if df is not None:
                price_data[c.ticker] = df
            else:
                print(f"    SKIP {c.ticker}: no usable weekly data in window")

        pc = PortfolioConstructor(top_n=TOP_N, rebalance_period_bars=REBALANCE_WEEKS)
        try:
            result = pc.run(candidates, price_data)
        except ValueError as exc:
            print(f"    Could not run: {exc}")
            continue

        calc = PerformanceMetrics(risk_free_rate=0.04)
        metrics = calc.calculate_all(
            equity_curve=result.equity_curve, trades=result.final_portfolio.ledger
        )
        sharpe = metrics.get("risk", {}).get("sharpe_ratio", 0.0) or 0.0
        cagr = metrics.get("returns", {}).get("cagr_pct", 0.0) or 0.0
        max_dd = metrics.get("drawdown", {}).get("max_drawdown_pct", 0.0) or 0.0
        n_trades = len([t for t in result.final_portfolio.ledger if t["status"] == "filled"])

        print(f"    Portfolio ({len(result.tickers_used)} names): "
              f"CAGR={fmt(cagr, '.1f')}%  Sharpe={fmt(sharpe, '.3f')}  "
              f"MaxDD={fmt(max_dd, '.1f')}%  Rebalance events="
              f"{len(set(r.date for r in result.rebalance_history))}  Fills={n_trades}\n")

        windows_out[label] = {
            "tickers_used": result.tickers_used,
            "cagr_pct": cagr,
            "sharpe": sharpe,
            "max_drawdown_pct": max_dd,
            "n_fills": n_trades,
            "n_rebalance_events": len(set(r.date for r in result.rebalance_history)),
            "n_equity_obs": len(result.equity_curve),
        }

    out = {
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "candidates": [c.ticker for c in candidates],
        "windows": windows_out,
    }
    out_path = "scripts/greenblatt_portfolio_backtest_result.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
