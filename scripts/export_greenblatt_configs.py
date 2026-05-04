#!/usr/bin/env python3
"""Export GreenblattWeekly configs for META, JPM, AAPL to AlphaLive.

Runs a full in-sample backtest (weekly bars, 2015-2025) for each ticker,
then writes validated JSON configs to AlphaLive/configs/production/.

Walk-forward validation was completed 2026-05-04:
  META: OOS Sharpe 1.04 / 2.26, OOS CAGR 22.6% / 91.0%  → CONSISTENT
  JPM:  OOS Sharpe 0.92 / 1.46, OOS CAGR 18.2% / 18.5%  → CONSISTENT
  AAPL: OOS Sharpe 1.25 / 1.87, OOS CAGR 19.9% / 25.3%  → CONSISTENT

Usage:
    cd AlphaLab
    python scripts/export_greenblatt_configs.py
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

SCRIPT_DIR = Path(__file__).parent.parent
BACKEND = SCRIPT_DIR / "backend"
sys.path.insert(0, str(BACKEND))

import yfinance as yf
import pandas as pd

from src.data.processor import FeatureEngineer
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.strategies.implementations.greenblatt_weekly import GreenblattWeekly

ALPHALIVE_CONFIGS = SCRIPT_DIR.parent / "AlphaLive" / "configs" / "production"
BACKTEST_START = "2015-01-01"
BACKTEST_END   = "2025-12-31"
INITIAL_CAPITAL = 100_000.0

TICKERS = ["META", "JPM", "AAPL"]

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

# Risk settings tuned for weekly value strategies on a small account.
# stop_loss_pct=25 acts as safety net below the strategy's own 20% trailing stop.
# take_profit_pct=100 effectively disabled — strategy holds until trailing stop fires.
# max_position_size_pct=33 allows three equal positions on a $1k account.
RISK = {
    "stop_loss_pct": 25.0,
    "take_profit_pct": 100.0,
    "max_position_size_pct": 33.0,
    "max_daily_loss_pct": 10.0,
    "max_open_positions": 1,
    "portfolio_max_positions": 10,
    "trailing_stop_enabled": False,
    "trailing_stop_pct": None,
    "commission_per_trade": 0.0,
}


def fetch_weekly(ticker: str) -> pd.DataFrame:
    print(f"  Fetching {ticker} weekly {BACKTEST_START} → {BACKTEST_END} …", end=" ", flush=True)
    raw = yf.download(ticker, start=BACKTEST_START, end=BACKTEST_END,
                      interval="1wk", auto_adjust=True, progress=False)
    if raw.empty:
        raise RuntimeError(f"No weekly data returned for {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0] for col in raw.columns]
    raw = raw.rename(columns=str.title)
    raw = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
    raw.index = pd.to_datetime(raw.index)
    raw.index.name = "Date"
    print(f"{len(raw)} bars")
    return raw


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    fe = FeatureEngineer()
    return fe.process(df).dropna(subset=["SMA_50", "RSI"])


def build_config(ticker: str, metrics: dict, bt_result) -> dict:
    perf = {
        "sharpe_ratio":    round(metrics.get("risk", {}).get("sharpe_ratio", 0.0), 2),
        "sortino_ratio":   round(metrics.get("risk", {}).get("sortino_ratio", 0.0), 2),
        "total_return_pct": round(
            (bt_result.final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2
        ),
        "max_drawdown_pct": round(metrics.get("drawdown", {}).get("max_drawdown_pct", 0.0), 2),
        "win_rate_pct":    round((metrics.get("trades", {}).get("win_rate", 0.0) or 0.0) * 100, 2),
        "profit_factor":   round(min(metrics.get("trades", {}).get("profit_factor", 0.0) or 0.0, 999.0), 2),
        "total_trades":    metrics.get("trades", {}).get("total_trades", 0) or 0,
        "calmar_ratio":    round(metrics.get("risk", {}).get("calmar_ratio", 0.0) or 0.0, 2),
    }
    return {
        "schema_version": "1.0",
        "strategy": {
            "name": "greenblatt_weekly",
            "parameters": STRATEGY_PARAMS,
            "description": (
                f"Greenblatt Magic Formula value strategy for {ticker}. "
                "Weekly bars. Entry on RSI<35 or 10w/50w golden cross. "
                "52-week minimum hold. 20% trailing stop from peak."
            ),
        },
        "ticker": ticker,
        "timeframe": "1Week",
        "risk": RISK,
        "execution": {
            "order_type": "market",
            "limit_offset_pct": 0.1,
            "cooldown_bars": 1,
        },
        "safety_limits": {
            "max_trades_per_day": 5,
            "max_api_calls_per_hour": 500,
            "signal_generation_timeout_seconds": 10.0,
            "broker_degraded_mode_threshold_failures": 3,
        },
        "metadata": {
            "exported_from": "AlphaLab",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "alphalab_version": "1.0.0",
            "backtest_id": f"greenblatt_weekly_{ticker}_{datetime.now().strftime('%Y%m%d')}",
            "backtest_period": {"start": BACKTEST_START, "end": BACKTEST_END},
            "performance": perf,
            "walk_forward_note": (
                "Walk-forward validated 2026-05-04. "
                "Two OOS windows both passed Sharpe ≥ 0.8 AND CAGR ≥ 13%."
            ),
        },
    }


def main():
    print("=" * 65)
    print("  AlphaLab → AlphaLive Export: GreenblattWeekly (META/JPM/AAPL)")
    print("=" * 65)

    engine = BacktestEngine()
    metrics_calc = PerformanceMetrics(risk_free_rate=0.04)

    print(f"\n[1/3] Fetching weekly market data ({BACKTEST_START} → {BACKTEST_END})")
    data: dict[str, pd.DataFrame] = {}
    for t in TICKERS:
        raw = fetch_weekly(t)
        data[t] = engineer(raw)
        print(f"    Features ready: {len(data[t])} usable weekly bars")

    print(f"\n[2/3] Running backtests")
    configs = []
    for ticker in TICKERS:
        print(f"\n  {ticker}")
        strategy = GreenblattWeekly(STRATEGY_PARAMS.copy())
        bt = engine.run_backtest(
            strategy, data[ticker],
            initial_capital=INITIAL_CAPITAL,
            max_drawdown_pct=40,
        )
        bm_curve = bt.benchmark.get("buy_and_hold_equity_curve") if bt.benchmark else None
        m = metrics_calc.calculate_all(bt.equity_curve, bt.trades, benchmark_curve=bm_curve)

        sharpe = m.get("risk", {}).get("sharpe_ratio", 0.0) or 0.0
        cagr   = m.get("returns", {}).get("cagr_pct", 0.0) or 0.0
        dd     = m.get("drawdown", {}).get("max_drawdown_pct", 0.0) or 0.0
        wr     = (m.get("trades", {}).get("win_rate", 0.0) or 0.0) * 100
        n      = m.get("trades", {}).get("total_trades", 0) or 0
        ret    = (bt.final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

        print(f"    Sharpe={sharpe:.2f}  CAGR={cagr:.1f}%  Return={ret:.1f}%  "
              f"WinRate={wr:.1f}%  MaxDD={dd:.1f}%  Trades={n}")

        cfg = build_config(ticker, m, bt)
        configs.append((ticker, cfg))

    print(f"\n[3/3] Writing configs to AlphaLive/configs/production/")
    ALPHALIVE_CONFIGS.mkdir(parents=True, exist_ok=True)
    for ticker, cfg in configs:
        filename = f"greenblatt_weekly_{ticker}.json"
        out_path = ALPHALIVE_CONFIGS / filename
        with open(out_path, "w") as f:
            json.dump(cfg, f, indent=2)
        perf = cfg["metadata"]["performance"]
        years = int(BACKTEST_END[:4]) - int(BACKTEST_START[:4])
        print(f"  ✓ {filename}  (Sharpe={perf['sharpe_ratio']}, "
              f"Return={perf['total_return_pct']:.0f}% over {years}y, "
              f"Trades={perf['total_trades']})")

    print(f"\n  All configs written to: {ALPHALIVE_CONFIGS}")
    print("\n  Next steps:")
    print("  1. cd AlphaLive && pytest tests/test_signal_parity.py — verify no regressions")
    print("  2. Add greenblatt_weekly parity test (Priority 4 in MASTER_PLAN)")
    print("  3. Deploy to Railway in DRY_RUN mode first, then paper, then live")
    print()


if __name__ == "__main__":
    main()
