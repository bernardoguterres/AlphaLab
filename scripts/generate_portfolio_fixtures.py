#!/usr/bin/env python3
"""Generate a deterministic portfolio-construction fixture for AlphaLive's parity test.

Produces one file in AlphaLive/tests/fixtures/:
  expected_portfolio_positions.csv - ticker,rank,target_weight,target_shares,price

AlphaLab is the oracle: this runs the REAL PortfolioConstructor
(backend/src/backtest/portfolio_constructor.py) against synthetic-but-fixed
candidates and prices (no network calls, fully reproducible), and exports
its rebalance-at-bar-0 output. AlphaLive's tests/test_portfolio_parity.py
independently recomputes the same scenario via
alphalive/portfolio/target_weights.py (a separately-written implementation,
not shared code) and diffs against this fixture - the same "AlphaLab
generates, AlphaLive independently reproduces and diffs" pattern used for
every other C1 parity fixture in this project.

Scenario (deliberately NOT vacuous - see the C1 "zero matched zero
vacuously" lesson in AlphaLive's CLAUDE.md): 6 candidates with distinct
ranks and distinct prices, top_n=4 so 2 lower-ranked candidates must be
excluded, and target_shares must differ per ticker (since prices differ)
even though target_weight is identical for all 4 selected names.

Usage:
    cd AlphaLab/backend
    source venv/bin/activate
    cd ..
    python scripts/generate_portfolio_fixtures.py
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.backtest.portfolio_constructor import PortfolioConstructor

OUT_PATH = (
    Path(__file__).parent.parent.parent
    / "AlphaLive"
    / "tests"
    / "fixtures"
    / "expected_portfolio_positions.csv"
)

TOP_N = 4
PORTFOLIO_VALUE = 100_000.0

# ticker -> (combined_rank, price). Ranks are NOT in ticker-alphabetical
# order and NOT in price order, specifically so a naive "sort by ticker" or
# "sort by price" bug in either implementation would be caught rather than
# accidentally passing.
CANDIDATES = {
    "AAA": (3, 100.0),
    "BBB": (1, 50.0),
    "CCC": (6, 200.0),  # rank 6 of 6 - must be excluded by top_n=4
    "DDD": (4, 25.0),
    "EEE": (2, 150.0),
    "FFF": (5, 80.0),  # rank 5 of 6 - must be excluded by top_n=4
}


@dataclass
class _FakeCandidate:
    ticker: str
    combined_rank: int


def main():
    candidates = [_FakeCandidate(t, rank) for t, (rank, _price) in CANDIDATES.items()]
    price_data = {
        t: pd.DataFrame({"Close": [price]}, index=pd.DatetimeIndex(["2024-01-05"]))
        for t, (_rank, price) in CANDIDATES.items()
    }

    pc = PortfolioConstructor(
        top_n=TOP_N, rebalance_period_bars=1, initial_capital=PORTFOLIO_VALUE
    )
    result = pc.run(candidates, price_data)

    rebalance_date = result.rebalance_history[0].date
    rows = [r for r in result.rebalance_history if r.date == rebalance_date]
    assert len(rows) == TOP_N, f"expected {TOP_N} rebalance rows, got {len(rows)}"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "rank", "target_weight", "target_shares", "price"])
        for r in sorted(rows, key=lambda r: r.ticker):
            writer.writerow([r.ticker, r.rank, r.target_weight, r.target_shares, r.price])

    print(f"Wrote {len(rows)} rows to {OUT_PATH}")
    for r in sorted(rows, key=lambda r: r.ticker):
        print(f"  {r.ticker}: rank={r.rank} weight={r.target_weight:.4f} shares={r.target_shares} price={r.price}")


if __name__ == "__main__":
    main()
