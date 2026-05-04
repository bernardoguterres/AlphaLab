#!/usr/bin/env python3
"""Generate weekly AAPL fixture + expected signals for AlphaLive parity test.

Produces two files in AlphaLive/tests/fixtures/:
  aapl_weekly_fixture.csv          — AAPL weekly OHLCV 2015-2024 (lowercase cols)
  expected_signals_greenblatt_weekly.csv — bar_index, signal, confidence, reason

Usage:
    cd AlphaLab
    python scripts/generate_greenblatt_fixtures.py
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

SCRIPT_DIR = Path(__file__).parent.parent
BACKEND = SCRIPT_DIR / "backend"
sys.path.insert(0, str(BACKEND))

import yfinance as yf
import pandas as pd

from src.data.processor import FeatureEngineer
from src.strategies.implementations.greenblatt_weekly import GreenblattWeekly

FIXTURES_DIR = SCRIPT_DIR.parent / "AlphaLive" / "tests" / "fixtures"

TICKER = "AAPL"
START  = "2015-01-01"
END    = "2024-12-31"

STRATEGY_PARAMS = {
    "fast_sma": 10,
    "slow_sma": 50,
    "rsi_period": 14,
    "rsi_oversold": 35,
    "rsi_overbought": 65,
    "min_hold_bars": 52,
    "trailing_stop_pct": 0.20,
    "exit_rsi_overbought": False,
    "exit_sma_cross": False,
}


def main():
    print(f"Generating GreenblattWeekly fixtures for AlphaLive parity test")
    print(f"  Ticker : {TICKER}  {START} → {END}")
    print(f"  Output : {FIXTURES_DIR}")

    # 1. Fetch weekly data
    print(f"\n[1/3] Fetching weekly data …", end=" ", flush=True)
    raw = yf.download(TICKER, start=START, end=END, interval="1wk",
                      auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError("yfinance returned no data")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0] for col in raw.columns]
    raw = raw.rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]].dropna()
    raw.index = pd.to_datetime(raw.index)
    raw.index.name = "Date"
    print(f"{len(raw)} bars")

    # 2. Feature engineering (AlphaLab) + run signals on FULL raw data (no dropna)
    # AlphaLive computes indicators incrementally from raw bars.
    # AlphaLab's generate_signals already skips NaN bars in its loop.
    # Using the full raw dataset ensures both engines warm up from the same bar 0.
    print(f"[2/3] Engineering features + generating AlphaLab signals …", end=" ", flush=True)
    fe = FeatureEngineer()
    featured = fe.process(raw)   # NO dropna — keep all bars including warmup period

    strategy = GreenblattWeekly(STRATEGY_PARAMS.copy())
    strategy.validate_params()
    signals_df = strategy.generate_signals(featured)
    print(f"done ({len(featured)} bars total, AlphaLab skips NaN bars internally)")

    # 3. Write fixture — AlphaLive expects raw OHLCV with lowercase column names.
    # Include all bars (incl. warmup) so AlphaLive's indicator computation matches AlphaLab.
    print(f"[3/3] Writing fixture files …")

    fixture_df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    fixture_df.index.name = "timestamp"
    fixture_df.columns = ["open", "high", "low", "close", "volume"]
    fixture_df = fixture_df.reset_index()

    fixture_path = FIXTURES_DIR / "aapl_weekly_fixture.csv"
    fixture_df.to_csv(fixture_path, index=False)
    print(f"  ✓ {fixture_path.name}  ({len(fixture_df)} rows)")

    # Write expected signals — only BUY/SELL bars (HOLD is implicit for everything else)
    expected_rows = []
    signal_map = {1: "BUY", -1: "SELL", 0: "HOLD"}

    for i, (idx, row) in enumerate(signals_df.iterrows()):
        sig = int(row["signal"])
        expected_rows.append({
            "bar_index": i,
            "signal": signal_map[sig],
            "confidence": round(float(row["confidence"]), 4),
            "reason": str(row["reason"]),
        })

    expected_df = pd.DataFrame(expected_rows)
    signals_path = FIXTURES_DIR / "expected_signals_greenblatt_weekly.csv"
    expected_df.to_csv(signals_path, index=False)

    non_hold = expected_df[expected_df["signal"] != "HOLD"]
    print(f"  ✓ {signals_path.name}  ({len(expected_df)} rows, {len(non_hold)} non-HOLD signals)")
    print()
    print("  Non-HOLD signals:")
    for _, r in non_hold.iterrows():
        print(f"    bar {int(r['bar_index']):3d}  {r['signal']:4s}  conf={r['confidence']:.2f}  {r['reason'][:70]}")

    print(f"\nDone. Run: cd AlphaLive && pytest tests/test_greenblatt_parity.py -v")


if __name__ == "__main__":
    main()
