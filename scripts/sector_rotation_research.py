"""Relative-strength sector rotation research - single, reusable, parameterized script.

Consolidates 2 one-shot scripts from the 2026-07-12 research session
(sector_rotation_backtest.py, and the sector-rotation half of
regime_robustness_test.py) into one tool. Results remain permanently
recorded in docs/experiments/registry.jsonl (EXP-2026-07-12-SR01,
REGIME01) - this script reproduces or extends that research, it does not
itself write new registry entries.

Levy (1967): rank sectors by price / 26-week trailing SMA, hold the top N,
equal-weight, re-rank every rebalance using PortfolioConstructor's dynamic
rank_fn mode (no look-ahead - trailing data only). Handles sector-ETF
inception dates explicitly (XLC launched 2018-06, XLRE launched 2015-10) so
a late-listed ETF can't silently truncate a backtest via
PortfolioConstructor's full-universe date intersection.

Usage:
    cd AlphaLab/backend && source venv/bin/activate && cd ..
    python scripts/sector_rotation_research.py
    python scripts/sector_rotation_research.py --windows 2022 2020
    python scripts/sector_rotation_research.py --top-n 4 --rebalance-weeks 4 --sma-weeks 26
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

from src.screener.relative_strength_ranker import (
    RelativeStrengthRanker,
    SPDR_SECTOR_ETFS,
)
from src.backtest.portfolio_constructor import PortfolioConstructor
from src.backtest.equal_weight_benchmark import equal_weight_benchmark

N_TRIALS = 6  # locked roster, EXPERIMENT_REGISTRY_SCHEMA.md

SECTOR_INCEPTIONS = {
    "XLC": "2018-06-19",
    "XLRE": "2015-10-07",
    # all other SPDR sector ETFs: 1998-12-16
}


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--top-n", type=int, default=4)
    p.add_argument(
        "--rebalance-weeks",
        type=int,
        default=4,
        help="~monthly on weekly bars, practitioner convention",
    )
    p.add_argument(
        "--sma-weeks", type=int, default=26, help="Levy (1967) original window"
    )
    p.add_argument(
        "--windows",
        nargs="*",
        default=None,
        help="Only run windows whose label contains one of these substrings",
    )
    return p.parse_args()


def universe_for_window(window_start: str, sma_weeks: int) -> list[str]:
    """Only include sector ETFs that existed (with warmup room) before the
    window starts - prevents a late-inception ETF from silently truncating
    the whole backtest."""
    warmup_weeks = sma_weeks + 5
    ws = pd.Timestamp(window_start)
    return [
        t
        for t in SPDR_SECTOR_ETFS
        if pd.Timestamp(SECTOR_INCEPTIONS.get(t, "1998-12-16"))
        + pd.Timedelta(weeks=warmup_weeks)
        <= ws
    ]


def main():
    args = parse_args()
    windows = STANDARD_REGIME_WINDOWS
    if args.windows:
        windows = [
            w
            for w in STANDARD_REGIME_WINDOWS
            if any(s in w["label"] for s in args.windows)
        ]
    warmup_weeks = args.sma_weeks + 5

    print("=" * 80)
    print("  AlphaLab - Sector rotation research (Levy 1967 relative strength)")
    print(
        f"  top_n={args.top_n}  rebalance={args.rebalance_weeks}w  sma={args.sma_weeks}w  windows={[w['label'] for w in windows]}"
    )
    print("=" * 80)

    ranker = RelativeStrengthRanker(sma_weeks=args.sma_weeks)
    results = {}

    for window in windows:
        label = window["label"]
        print(f"\n[{label}] {window['start']} -> {window['end']}")

        universe = universe_for_window(window["start"], args.sma_weeks)
        warmup_start = (
            pd.Timestamp(window["start"]) - pd.Timedelta(weeks=warmup_weeks)
        ).strftime("%Y-%m-%d")

        price_data = {}
        for t in universe:
            df = fetch_weekly_close(t, warmup_start, window["end"])
            if df is not None:
                price_data[t] = df
        print(f"    Universe: {universe} ({len(universe)} of {len(SPDR_SECTOR_ETFS)})")
        if len(price_data) < 2:
            print("    Insufficient data - skipping")
            continue

        window_start_ts = pd.Timestamp(window["start"])

        pc = PortfolioConstructor(
            top_n=min(args.top_n, len(price_data)),
            rebalance_period_bars=args.rebalance_weeks,
        )
        strat_result = pc.run(price_data=price_data, rank_fn=ranker.rank)
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

        print(
            f"    Rotation: CAGR={fmt(strat_m['cagr_pct'], '.1f')}%  Sharpe={fmt(strat_m['sharpe'], '.3f')}"
            + (
                f"  DSR={strat_m['dsr'].deflated_sharpe_ratio:.3f}"
                if strat_m["dsr"]
                else ""
            )
            + f"  ({len(strat_result.tickers_used)} distinct sectors held over the window)"
        )
        print(
            f"    Equal-weight sectors: CAGR={fmt(ew_m['cagr_pct'], '.1f')}%  Sharpe={fmt(ew_m['sharpe'], '.3f')}"
        )
        print(
            f"    SPY buy-and-hold: CAGR={fmt(spy['cagr_pct'] if spy else None, '.1f')}%  Sharpe={fmt(spy['sharpe'] if spy else None, '.3f')}"
        )
        print(
            f"    Faber 10mo-SMA overlay: CAGR={fmt(faber['cagr_pct'] if faber else None, '.1f')}%  Sharpe={fmt(faber['sharpe'] if faber else None, '.3f')}"
        )
        beats_ew = strat_m["sharpe"] > ew_m["sharpe"]
        print(f"    Beats plain diversification (Sharpe): {beats_ew}")

        results[label] = {
            "universe": universe,
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
                "sectors_held": strat_result.tickers_used,
            },
            "equal_weight_sectors": {
                "cagr_pct": ew_m["cagr_pct"],
                "sharpe": ew_m["sharpe"],
            },
            "spy_buyhold": spy,
            "faber_overlay": faber,
            "beats_diversification_sharpe": beats_ew,
        }

    out_path = "scripts/sector_rotation_research_result.json"
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
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
