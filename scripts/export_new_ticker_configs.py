#!/usr/bin/env python3
"""
Export production configs for GLD, IWM, XLK to AlphaLive.

Runs real AlphaLab backtests (2015-2024) and exports properly formatted
JSON configs — the same way the AlphaLab UI export button works.

Usage:
    cd AlphaLab
    python scripts/export_new_ticker_configs.py
"""

import sys
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# AlphaLab path setup (same pattern as other AlphaLab scripts)
SCRIPT_DIR = Path(__file__).parent.parent
BACKEND = SCRIPT_DIR / "backend"
sys.path.insert(0, str(BACKEND))

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd

from src.data.processor import FeatureEngineer
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.strategies.implementations.moving_average_crossover import MovingAverageCrossover
from src.strategies.implementations.rsi_mean_reversion import RSIMeanReversion

ALPHALIVE_CONFIGS = SCRIPT_DIR.parent / "AlphaLive" / "configs" / "production"

BACKTEST_START = "2015-01-01"
BACKTEST_END   = "2024-12-31"
INITIAL_CAPITAL = 100_000.0

JOBS = [
    {"ticker": "GLD", "strategy_class": RSIMeanReversion,  "strategy_name": "rsi_mean_reversion",
     "params": {"period": 14, "oversold": 30, "overbought": 70},
     "risk": {"stop_loss_pct": 1.5, "take_profit_pct": 4.0, "max_position_size_pct": 15.0,
              "max_daily_loss_pct": 5.0, "max_open_positions": 3}},
    {"ticker": "GLD", "strategy_class": MovingAverageCrossover, "strategy_name": "ma_crossover",
     "params": {"fast_period": 20, "slow_period": 50},
     "risk": {"stop_loss_pct": 2.0, "take_profit_pct": 5.0, "max_position_size_pct": 15.0,
              "max_daily_loss_pct": 5.0, "max_open_positions": 3}},
    {"ticker": "IWM", "strategy_class": RSIMeanReversion,  "strategy_name": "rsi_mean_reversion",
     "params": {"period": 14, "oversold": 30, "overbought": 70},
     "risk": {"stop_loss_pct": 2.0, "take_profit_pct": 5.0, "max_position_size_pct": 15.0,
              "max_daily_loss_pct": 5.0, "max_open_positions": 3}},
    {"ticker": "IWM", "strategy_class": MovingAverageCrossover, "strategy_name": "ma_crossover",
     "params": {"fast_period": 20, "slow_period": 50},
     "risk": {"stop_loss_pct": 2.0, "take_profit_pct": 5.0, "max_position_size_pct": 15.0,
              "max_daily_loss_pct": 5.0, "max_open_positions": 3}},
    {"ticker": "XLK", "strategy_class": RSIMeanReversion,  "strategy_name": "rsi_mean_reversion",
     "params": {"period": 14, "oversold": 30, "overbought": 70},
     "risk": {"stop_loss_pct": 2.0, "take_profit_pct": 5.0, "max_position_size_pct": 10.0,
              "max_daily_loss_pct": 5.0, "max_open_positions": 3}},
    {"ticker": "XLK", "strategy_class": MovingAverageCrossover, "strategy_name": "ma_crossover",
     "params": {"fast_period": 20, "slow_period": 50},
     "risk": {"stop_loss_pct": 2.0, "take_profit_pct": 5.0, "max_position_size_pct": 10.0,
              "max_daily_loss_pct": 5.0, "max_open_positions": 3}},
]


def fetch_and_engineer(ticker: str) -> pd.DataFrame:
    print(f"  Fetching {ticker} {BACKTEST_START} → {BACKTEST_END}...", end=" ", flush=True)
    raw = yf.download(ticker, start=BACKTEST_START, end=BACKTEST_END, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.title)
    raw = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
    print(f"{len(raw)} bars")
    return FeatureEngineer().process(raw)


def build_export_json(job: dict, results: dict, metrics: dict) -> dict:
    """Mirror AlphaLab's _build_export_json from routes.py."""
    perf = {
        "sharpe_ratio":    round(metrics.get("risk", {}).get("sharpe_ratio", 0.0), 2),
        "sortino_ratio":   round(metrics.get("risk", {}).get("sortino_ratio", 0.0), 2),
        "total_return_pct": round(results.get("total_return_pct", 0.0), 2),
        "max_drawdown_pct": round(metrics.get("drawdown", {}).get("max_drawdown_pct", 0.0), 2),
        "win_rate_pct":    round(metrics.get("trades", {}).get("win_rate", 0.0) * 100, 2),
        "profit_factor":   round(metrics.get("trades", {}).get("profit_factor", 0.0), 2),
        "total_trades":    results.get("total_trades", 0),
        "calmar_ratio":    round(metrics.get("risk", {}).get("calmar_ratio", 0.0), 2),
    }
    risk = {
        "stop_loss_pct":          job["risk"]["stop_loss_pct"],
        "take_profit_pct":        job["risk"]["take_profit_pct"],
        "max_position_size_pct":  job["risk"]["max_position_size_pct"],
        "max_daily_loss_pct":     job["risk"]["max_daily_loss_pct"],
        "max_open_positions":     job["risk"]["max_open_positions"],
        "portfolio_max_positions": 10,
        "trailing_stop_enabled":  False,
        "trailing_stop_pct":      3.0,
        "commission_per_trade":   0.0,
    }
    return {
        "schema_version": "1.0",
        "strategy": {
            "name": job["strategy_name"],
            "parameters": job["params"],
            "description": f"{job['strategy_name'].replace('_',' ').title()} strategy for {job['ticker']}",
        },
        "ticker": job["ticker"],
        "timeframe": "1Day",
        "risk": risk,
        "execution": {"order_type": "market", "limit_offset_pct": 0.1, "cooldown_bars": 1},
        "safety_limits": {
            "max_trades_per_day": 20, "max_api_calls_per_hour": 500,
            "signal_generation_timeout_seconds": 5.0,
            "broker_degraded_mode_threshold_failures": 3,
        },
        "metadata": {
            "exported_from": "AlphaLab",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "alphalab_version": "1.0.0",
            "backtest_id": f"{job['strategy_name']}_{job['ticker']}_{datetime.now().strftime('%Y%m%d')}",
            "backtest_period": {"start": BACKTEST_START, "end": BACKTEST_END},
            "performance": perf,
        },
    }


def main():
    print("=" * 60)
    print("AlphaLab → AlphaLive Config Export: GLD / IWM / XLK")
    print("=" * 60)

    engine = BacktestEngine()
    metrics_calc = PerformanceMetrics(risk_free_rate=0.04)

    # Download data once per ticker
    ticker_data: dict[str, pd.DataFrame] = {}
    print("\n[1/3] Fetching market data")
    for ticker in ["GLD", "IWM", "XLK"]:
        ticker_data[ticker] = fetch_and_engineer(ticker)

    print("\n[2/3] Running backtests")
    exports = []

    for job in JOBS:
        ticker = job["ticker"]
        name   = job["strategy_name"]
        print(f"\n  {name} / {ticker}")

        strategy = job["strategy_class"](job["params"].copy())
        bt = engine.run_backtest(strategy, ticker_data[ticker], initial_capital=INITIAL_CAPITAL)

        bm_curve = bt.benchmark.get("buy_and_hold_equity_curve") if bt.benchmark else None
        m = metrics_calc.calculate_all(bt.equity_curve, bt.trades, benchmark_curve=bm_curve)

        total_return_pct = (
            (bt.final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
            if bt.final_value else 0.0
        )
        bt_summary = {"total_return_pct": total_return_pct, "total_trades": len(bt.trades)}

        sharpe = m.get("risk", {}).get("sharpe_ratio", 0.0)
        wr     = m.get("trades", {}).get("win_rate", 0.0)
        dd     = m.get("drawdown", {}).get("max_drawdown_pct", 0.0)
        print(f"    Sharpe={sharpe:.2f}  WinRate={wr*100:.1f}%  MaxDD={dd:.1f}%  "
              f"Return={total_return_pct:.1f}%  Trades={len(bt.trades)}")

        export_json = build_export_json(job, bt_summary, m)
        exports.append((job, export_json))

    print("\n[3/3] Writing configs to AlphaLive")
    ALPHALIVE_CONFIGS.mkdir(parents=True, exist_ok=True)

    for job, export_json in exports:
        filename = f"{job['strategy_name']}_{job['ticker']}.json"
        out_path = ALPHALIVE_CONFIGS / filename
        with open(out_path, "w") as f:
            json.dump(export_json, f, indent=2)
        perf = export_json["metadata"]["performance"]
        print(f"  ✓ {filename}  (Sharpe={perf['sharpe_ratio']}, "
              f"Return={perf['total_return_pct']}%, Trades={perf['total_trades']})")

    print(f"\n✅ {len(exports)} configs exported to {ALPHALIVE_CONFIGS}")


if __name__ == "__main__":
    main()
