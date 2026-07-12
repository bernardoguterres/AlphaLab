"""Faithful Greenblatt Magic Formula research - single, reusable, parameterized script.

Consolidates 5 one-shot scripts from the 2026-07-12 research session
(greenblatt_faithful_backtest.py, greenblatt_portfolio_backtest.py,
greenblatt_evidence_checklist.py, greenblatt_wide_universe_test.py, and the
Greenblatt half of regime_robustness_test.py) into one tool. Each of those
scripts' results remains permanently recorded in
docs/experiments/registry.jsonl (EXP-2026-07-12-M01, M02, M02-CHECKLIST,
M02-WIDEUNIV, REGIME01) - this script is how to REPRODUCE or EXTEND that
research, not a replacement for the registry, and it does not itself write
new registry entries (do that manually after reviewing a run's output, per
docs/EXPERIMENT_REGISTRY_SCHEMA.md's pre-registration convention).

Always uses the CORRECTED wide-universe methodology: screens ALL qualified
candidates (not pre-truncated to top_n), and lets PortfolioConstructor's
own top_n selection do the real work - see EXP-2026-07-12-M02-WIDEUNIV for
why the naive pre-truncated version silently made the equal-weight control
a no-op. Always computes the full evidence-checklist trio (SPY buy-and-
hold, Faber 10-month-SMA overlay, equal-weight-of-the-qualified-universe)
plus the deflated Sharpe ratio against the locked trial roster.

Usage:
    cd AlphaLab/backend && source venv/bin/activate && cd ..
    python scripts/greenblatt_research.py                       # all 6 standard regime windows
    python scripts/greenblatt_research.py --windows 2022 2020   # only windows whose label contains these substrings
    python scripts/greenblatt_research.py --top-n 6 --screen-top-n 25
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from wf_common import (
    setup_backend_path,
    fmt,
    fetch_weekly_close,
    compute_metrics_and_dsr,
    faber_benchmark_for_window,
    spy_buyhold_for_window,
    STANDARD_REGIME_WINDOWS,
)

setup_backend_path()

import pandas as pd

from src.screener.fundamental_screener import FundamentalScreener
from src.backtest.portfolio_constructor import PortfolioConstructor
from src.backtest.equal_weight_benchmark import equal_weight_benchmark

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
N_TRIALS = 6  # locked roster, EXPERIMENT_REGISTRY_SCHEMA.md


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=6,
        help="Positions the strategy holds (default 6, matching every prior registry entry)",
    )
    p.add_argument(
        "--screen-top-n",
        type=int,
        default=25,
        help="How many candidates to screen for ('all qualified' - default 25, effectively unbounded against a 23-ticker universe)",
    )
    p.add_argument(
        "--rebalance-weeks",
        type=int,
        default=52,
        help="Rebalance cadence in weeks (default 52, annual, matching Greenblatt's own recommendation)",
    )
    p.add_argument(
        "--windows",
        nargs="*",
        default=None,
        help="Only run windows whose label contains one of these substrings (default: all 6 standard regime windows)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    windows = STANDARD_REGIME_WINDOWS
    if args.windows:
        windows = [
            w
            for w in STANDARD_REGIME_WINDOWS
            if any(s in w["label"] for s in args.windows)
        ]

    print("=" * 80)
    print("  AlphaLab - Greenblatt faithful portfolio research")
    print(
        f"  top_n={args.top_n}  rebalance={args.rebalance_weeks}w  windows={[w['label'] for w in windows]}"
    )
    print("=" * 80)

    screener = FundamentalScreener(
        universe=UNIVERSE,
        min_market_cap_b=10.0,
        max_debt_to_equity=2.0,
        request_delay=0.3,
    )
    all_qualified = screener.screen(top_n=args.screen_top_n)
    print(
        f"\nAll qualified candidates ({len(all_qualified)} of {len(UNIVERSE)}): "
        f"{[(c.ticker, c.combined_rank) for c in all_qualified]}"
    )
    top = sorted(all_qualified, key=lambda c: c.combined_rank)[: args.top_n]
    print(f"Top {args.top_n} by rank: {[c.ticker for c in top]}\n")

    results = {}

    for window in windows:
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
        window_start_ts = pd.Timestamp(window["start"])

        pc = PortfolioConstructor(
            top_n=args.top_n, rebalance_period_bars=args.rebalance_weeks
        )
        strat_result = pc.run(candidates_with_data, price_data)
        strat_m = compute_metrics_and_dsr(
            strat_result.equity_curve,
            strat_result.final_portfolio.ledger,
            window_start_ts,
            N_TRIALS,
        )

        ew_result = equal_weight_benchmark(
            price_data, rebalance_period_bars=args.rebalance_weeks
        )
        ew_m = compute_metrics_and_dsr(
            ew_result.equity_curve,
            ew_result.final_portfolio.ledger,
            window_start_ts,
            N_TRIALS,
        )

        spy = spy_buyhold_for_window(window["start"], window["end"])
        faber = faber_benchmark_for_window(window["start"], window["end"])

        selected = sorted(strat_result.tickers_used)
        print(
            f"    Strategy (top {args.top_n} of {len(candidates_with_data)}): {selected}"
        )
        print(
            f"      CAGR={fmt(strat_m['cagr_pct'], '.1f')}%  Sharpe={fmt(strat_m['sharpe'], '.3f')}"
            + (
                f"  DSR={strat_m['dsr'].deflated_sharpe_ratio:.3f}"
                if strat_m["dsr"]
                else ""
            )
        )
        print(
            f"    Equal-weight (all {len(ew_result.tickers_used)} qualified): "
            f"CAGR={fmt(ew_m['cagr_pct'], '.1f')}%  Sharpe={fmt(ew_m['sharpe'], '.3f')}"
        )
        print(
            f"    SPY buy-and-hold: CAGR={fmt(spy['cagr_pct'] if spy else None, '.1f')}%  Sharpe={fmt(spy['sharpe'] if spy else None, '.3f')}"
        )
        print(
            f"    Faber 10mo-SMA overlay: CAGR={fmt(faber['cagr_pct'] if faber else None, '.1f')}%  Sharpe={fmt(faber['sharpe'] if faber else None, '.3f')}"
        )
        beats_ew = strat_m["sharpe"] > ew_m["sharpe"]
        print(f"    Beats plain diversification (Sharpe): {beats_ew}\n")

        results[label] = {
            "strategy": {
                "cagr_pct": strat_m["cagr_pct"],
                "sharpe": strat_m["sharpe"],
                "n_obs": strat_m["n_obs"],
                "deflated_sharpe_ratio": (
                    strat_m["dsr"].deflated_sharpe_ratio if strat_m["dsr"] else None
                ),
                "significant_at_95pct": (
                    strat_m["dsr"].significant_at_95pct if strat_m["dsr"] else None
                ),
                "selected": selected,
            },
            "equal_weight_all_qualified": {
                "cagr_pct": ew_m["cagr_pct"],
                "sharpe": ew_m["sharpe"],
            },
            "spy_buyhold": spy,
            "faber_overlay": faber,
            "beats_diversification_sharpe": beats_ew,
        }

    out_path = "scripts/greenblatt_research_result.json"
    with open(out_path, "w") as f:
        json.dump(
            {
                "run_date": datetime.now().strftime("%Y-%m-%d"),
                "n_trials": N_TRIALS,
                "params": vars(args),
                "windows": results,
            },
            f,
            indent=2,
            default=str,
        )
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
