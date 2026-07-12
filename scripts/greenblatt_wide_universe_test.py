"""Fixes the equal-weight-benchmark gap found in EXP-2026-07-12-REGIME01:
FundamentalScreener.screen(top_n=6) was truncating to exactly 6 candidates
BEFORE PortfolioConstructor ever saw them, so PortfolioConstructor's own
top_n=6 was a no-op - "strategy" and "equal-weight of the same universe"
were identical in every window, meaning the ranking's marginal value over
plain diversification was never actually tested.

Fix: screen the full 23-ticker universe with a high top_n (25, effectively
"all qualified") to get every candidate that passes the market-cap/D-E/
sector filters - 14 of 23 in this universe as of 2026-07-12 - then let
PortfolioConstructor's own top_n=6 do the real selecting. The equal-weight
benchmark now runs over the SAME 14-candidate universe, so it's a genuine
test of "does the EBIT/EV + ROC ranking add value over passively holding
everything that qualifies."

Same fixed parameters as M02/SR01/REGIME01 (top_n=6, rebalance=52w) - no
re-tuning. Covers the same 6 windows as the campaign so far (original 2
overlapping windows + the 4 regimes from REGIME01) for full comparability.

Usage:
    cd AlphaLab/backend && source venv/bin/activate && cd ..
    python scripts/greenblatt_wide_universe_test.py
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
from src.backtest.equal_weight_benchmark import equal_weight_benchmark
from src.backtest.metrics import PerformanceMetrics
from src.backtest.deflated_sharpe import deflated_sharpe_ratio

UNIVERSE = [
    "MSFT", "AAPL", "GOOGL", "AMZN", "META", "NVDA", "JPM", "JNJ",
    "V", "MA", "UNH", "HD", "MCD", "KO", "PEP", "WMT", "BAC",
    "XOM", "CVX", "LLY", "ABBV", "TMO", "BRK-B",
]
TOP_N = 6  # unchanged from M02/REGIME01
REBALANCE_WEEKS = 52
N_TRIALS = 6

WINDOWS = [
    {"label": "Window 1 (2018-2020)", "start": "2018-01-01", "end": "2020-12-31"},
    {"label": "Window 2 (2021-2024)", "start": "2021-01-01", "end": "2024-12-31"},
    {"label": "2008 Crisis", "start": "2007-06-01", "end": "2009-12-31"},
    {"label": "2015-2019 Grind", "start": "2015-01-01", "end": "2019-12-31"},
    {"label": "2020 COVID", "start": "2020-01-01", "end": "2020-12-31"},
    {"label": "2022 Bear", "start": "2022-01-01", "end": "2022-12-31"},
]


def fetch_weekly_close(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    raw = yf.download(ticker, start=start, end=end, interval="1wk", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw[["Close"]].dropna()
    return close if len(close) >= 10 else None


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


def main():
    print("=" * 80)
    print("  Greenblatt wide-universe test: fixes the equal-weight-benchmark no-op")
    print("  Screens ALL qualified candidates (not pre-truncated to 6), lets")
    print("  PortfolioConstructor's own top_n=6 do the real selecting")
    print("=" * 80)

    screener = FundamentalScreener(universe=UNIVERSE, min_market_cap_b=10.0, max_debt_to_equity=2.0, request_delay=0.3)
    all_qualified = screener.screen(top_n=25)  # effectively "all that pass filters"
    print(f"\nAll qualified candidates ({len(all_qualified)} of {len(UNIVERSE)}): "
          f"{[(c.ticker, c.combined_rank) for c in all_qualified]}")
    print(f"Top {TOP_N} by rank (what the strategy will select): "
          f"{[c.ticker for c in sorted(all_qualified, key=lambda c: c.combined_rank)[:TOP_N]]}\n")

    results = {}

    for window in WINDOWS:
        label = window["label"]
        print(f"[{label}] {window['start']} -> {window['end']}")

        price_data = {}
        for c in all_qualified:
            df = fetch_weekly_close(c.ticker, window["start"], window["end"])
            if df is not None:
                price_data[c.ticker] = df

        if len(price_data) < 2:
            print("    Insufficient data - skipping\n")
            continue

        candidates_with_data = [c for c in all_qualified if c.ticker in price_data]

        pc = PortfolioConstructor(top_n=TOP_N, rebalance_period_bars=REBALANCE_WEEKS)
        strat_result = pc.run(candidates_with_data, price_data)
        strat_m = compute_metrics_and_dsr(strat_result.equity_curve, strat_result.final_portfolio.ledger, pd.Timestamp(window["start"]))

        ew_result = equal_weight_benchmark(price_data, rebalance_period_bars=REBALANCE_WEEKS)
        ew_m = compute_metrics_and_dsr(ew_result.equity_curve, ew_result.final_portfolio.ledger, pd.Timestamp(window["start"]))

        selected = sorted(strat_result.tickers_used)
        universe_held = sorted(ew_result.tickers_used)
        print(f"    Strategy (top {TOP_N} of {len(candidates_with_data)}): {selected}")
        print(f"      CAGR={fmt(strat_m['cagr_pct'], '.1f')}%  Sharpe={fmt(strat_m['sharpe'], '.3f')}"
              + (f"  DSR={strat_m['dsr'].deflated_sharpe_ratio:.3f}" if strat_m['dsr'] else ""))
        print(f"    Equal-weight (all {len(universe_held)} qualified): {universe_held}")
        print(f"      CAGR={fmt(ew_m['cagr_pct'], '.1f')}%  Sharpe={fmt(ew_m['sharpe'], '.3f')}")
        beats_ew = strat_m["sharpe"] > ew_m["sharpe"]
        print(f"    Ranking beats plain diversification (Sharpe): {beats_ew}\n")

        results[label] = {
            "strategy": {"cagr_pct": strat_m["cagr_pct"], "sharpe": strat_m["sharpe"], "n_obs": strat_m["n_obs"],
                         "deflated_sharpe_ratio": strat_m["dsr"].deflated_sharpe_ratio if strat_m["dsr"] else None,
                         "significant_at_95pct": strat_m["dsr"].significant_at_95pct if strat_m["dsr"] else None,
                         "selected": selected},
            "equal_weight_all_qualified": {"cagr_pct": ew_m["cagr_pct"], "sharpe": ew_m["sharpe"], "n_obs": ew_m["n_obs"],
                                            "universe": universe_held},
            "ranking_beats_diversification_sharpe": beats_ew,
        }

    out_path = "scripts/greenblatt_wide_universe_test_result.json"
    with open(out_path, "w") as f:
        json.dump({"run_date": datetime.now().strftime("%Y-%m-%d"), "n_trials": N_TRIALS,
                    "all_qualified": [(c.ticker, c.combined_rank) for c in all_qualified], "windows": results},
                   f, indent=2, default=str)
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
