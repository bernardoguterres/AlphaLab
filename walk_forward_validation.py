"""Walk-Forward Validation Script for AlphaLab Strategies.

Tests three new strategies across two rolling windows on SPY (2019-2024):
  - Window 1: Train 2019-2021  |  Test 2022
  - Window 2: Train 2020-2022  |  Test 2023

For each (strategy, window) combination the script runs a full backtest and
records Sharpe ratio, win rate, max drawdown, and total trades.  It then
prints a formatted table comparing in-sample vs out-of-sample results and
issues a final CONSISTENT / UNSTABLE verdict per strategy.

Usage:
    cd /Users/bernardoguterrres/Desktop/Alpha/AlphaLab/backend
    source venv/bin/activate
    cd ..
    python walk_forward_validation.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Path setup — make the AlphaLab backend importable from any working directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(SCRIPT_DIR, "backend")

if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# ---------------------------------------------------------------------------
# Standard library & third-party imports
# ---------------------------------------------------------------------------
import math
import warnings
warnings.filterwarnings("ignore")          # suppress pandas / scipy noise

import yfinance as yf
import pandas as pd

# ---------------------------------------------------------------------------
# AlphaLab internal imports
# ---------------------------------------------------------------------------
from src.data.processor import FeatureEngineer
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.strategies.implementations.rsi_simple import RSISimple
from src.strategies.implementations.bollinger_rsi_combo import BollingerRSICombo
from src.strategies.implementations.trend_adaptive_rsi import TrendAdaptiveRSI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TICKER = "SPY"

# Walk-forward windows: (train_start, train_end, test_start, test_end)
WINDOWS = [
    {
        "label": "Window 1",
        "train_start": "2019-01-01",
        "train_end":   "2021-12-31",
        "test_start":  "2022-01-01",
        "test_end":    "2022-12-31",
    },
    {
        "label": "Window 2",
        "train_start": "2020-01-01",
        "train_end":   "2022-12-31",
        "test_start":  "2023-01-01",
        "test_end":    "2023-12-31",
    },
]

# Strategies and their parameters
STRATEGIES = [
    {
        "name": "rsi_simple",
        "class": RSISimple,
        "params": {
            "period":     14,
            "oversold":   40,
            "overbought": 60,
        },
    },
    {
        "name": "bollinger_rsi_combo",
        "class": BollingerRSICombo,
        "params": {
            "bb_period":      20,
            "bb_std":         2.0,
            "rsi_period":     14,
            "rsi_oversold":   45,
            "rsi_overbought": 55,
            "exit_at_middle": True,
        },
    },
    {
        "name": "trend_adaptive_rsi",
        "class": TrendAdaptiveRSI,
        "params": {
            "rsi_period":      14,
            "trend_sma":       50,
            "trend_lookback":  5,
            "uptrend_buy":     45,
            "uptrend_sell":    65,
            "downtrend_buy":   35,
            "downtrend_sell":  55,
            "range_buy":       35,
            "range_sell":      65,
        },
    },
]

# Verdict threshold
SHARPE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def fetch_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLCV data from yfinance and normalise column names."""
    print(f"  Fetching {ticker} {start} → {end} …", end=" ", flush=True)
    raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)

    if raw.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker} [{start}, {end}]")

    # yfinance may return a MultiIndex if a single ticker is passed with
    # certain library versions — flatten if needed.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0] for col in raw.columns]

    # Ensure standard column names
    raw = raw.rename(columns=str.title)          # open→Open, etc.
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(raw.columns)
    if missing:
        raise RuntimeError(f"Missing columns after download: {missing}")

    raw = raw[list(required)].dropna()
    raw.index = pd.to_datetime(raw.index)
    raw.index.name = "Date"
    print(f"{len(raw)} bars")
    return raw


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Run FeatureEngineer on raw OHLCV data."""
    fe = FeatureEngineer()
    return fe.process(df)


# ---------------------------------------------------------------------------
# Backtest helpers
# ---------------------------------------------------------------------------

def run_one_backtest(
    strategy_class,
    params: dict,
    full_featured_data: pd.DataFrame,
    start_date: str,
    end_date: str,
    ticker: str = TICKER,
) -> dict:
    """Run a single backtest slice and return the key metrics.

    The engine's _simulate loop uses `data.attrs.get("ticker")` to look up
    prices, so we attach the ticker name to the DataFrame attributes.
    """
    # Slice the pre-computed feature DataFrame to the requested window
    df_slice = full_featured_data.loc[start_date:end_date].copy()
    df_slice.attrs["ticker"] = ticker

    if len(df_slice) < 10:
        return _empty_metrics_row(f"Too few bars ({len(df_slice)})")

    # Instantiate strategy with the given params
    strategy = strategy_class(params.copy())

    # Run backtest
    engine = BacktestEngine()
    results = engine.run_backtest(strategy, df_slice, initial_capital=100_000)

    # Calculate performance metrics
    calculator = PerformanceMetrics(risk_free_rate=0.04)
    bm_curve = results.benchmark.get("buy_and_hold_equity_curve") if results.benchmark else None
    metrics = calculator.calculate_all(
        equity_curve=results.equity_curve,
        trades=results.trades,
        benchmark_curve=bm_curve,
    )

    sharpe      = metrics.get("risk", {}).get("sharpe_ratio", 0.0) or 0.0
    max_dd      = metrics.get("drawdown", {}).get("max_drawdown_pct", 0.0) or 0.0
    win_rate    = metrics.get("trades", {}).get("win_rate", 0.0) or 0.0
    total_trades = metrics.get("trades", {}).get("total_trades", 0) or 0

    return {
        "sharpe":        sharpe,
        "win_rate":      win_rate,
        "max_drawdown":  max_dd,
        "total_trades":  total_trades,
        "error":         None,
    }


def _empty_metrics_row(reason: str) -> dict:
    return {
        "sharpe":       float("nan"),
        "win_rate":     float("nan"),
        "max_drawdown": float("nan"),
        "total_trades": 0,
        "error":        reason,
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

COL_W = {
    "strategy":    22,
    "window":      10,
    "phase":        7,
    "period":      24,
    "sharpe":       8,
    "win_rate":     9,
    "max_dd":       9,
    "trades":       7,
}


def _fmt(value, fmt_str, na="  N/A  "):
    """Format a numeric value, returning na string if NaN."""
    if value is None:
        return na
    try:
        if math.isnan(value):
            return na
        return format(value, fmt_str)
    except (TypeError, ValueError):
        return na


def print_header():
    h = (
        f"{'Strategy':<{COL_W['strategy']}} "
        f"{'Window':<{COL_W['window']}} "
        f"{'Phase':<{COL_W['phase']}} "
        f"{'Period':<{COL_W['period']}} "
        f"{'Sharpe':>{COL_W['sharpe']}} "
        f"{'Win Rate':>{COL_W['win_rate']}} "
        f"{'Max DD%':>{COL_W['max_dd']}} "
        f"{'Trades':>{COL_W['trades']}}"
    )
    sep = "-" * len(h)
    print(sep)
    print(h)
    print(sep)
    return sep


def print_row(strategy_label, window_label, phase, period, m):
    """Print one result row."""
    sharpe_str  = _fmt(m["sharpe"], ".4f")
    max_dd_str  = _fmt(m["max_drawdown"], ".2f")
    trades_str  = str(m["total_trades"]) if m["error"] is None else "N/A"

    wr = m["win_rate"]
    if m["error"] is not None or wr is None or (isinstance(wr, float) and math.isnan(wr)):
        win_rate_str = "  N/A  "
    else:
        win_rate_str = f"{wr * 100:.1f}%"

    note = f"  [{m['error']}]" if m["error"] else ""

    print(
        f"{strategy_label:<{COL_W['strategy']}} "
        f"{window_label:<{COL_W['window']}} "
        f"{phase:<{COL_W['phase']}} "
        f"{period:<{COL_W['period']}} "
        f"{sharpe_str:>{COL_W['sharpe']}} "
        f"{win_rate_str:>{COL_W['win_rate']}} "
        f"{max_dd_str:>{COL_W['max_dd']}} "
        f"{trades_str:>{COL_W['trades']}}"
        f"{note}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print("  AlphaLab Walk-Forward Validation")
    print(f"  Ticker : {TICKER}")
    print(f"  Windows: {len(WINDOWS)}  (3-year train / 1-year test, step 1 year)")
    print(f"  Verdict threshold: out-of-sample Sharpe > {SHARPE_THRESHOLD} in all windows")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Determine the full date range needed and fetch once
    # ------------------------------------------------------------------
    all_starts = [w["train_start"] for w in WINDOWS]
    all_ends   = [w["test_end"]    for w in WINDOWS]
    fetch_start = min(all_starts)
    fetch_end   = max(all_ends)

    print(f"\n[1/3] Downloading market data …")
    raw_data = fetch_data(TICKER, fetch_start, fetch_end)

    # ------------------------------------------------------------------
    # 2. Feature engineering (single pass over the full range)
    # ------------------------------------------------------------------
    print(f"\n[2/3] Engineering features …", end=" ", flush=True)
    featured_data = engineer_features(raw_data)
    # Drop early NaN rows that can't be used by any strategy
    featured_data = featured_data.dropna(subset=["RSI", "BB_Lower", "SMA_50"])
    print(f"done ({len(featured_data)} usable bars after indicator warm-up)")

    # ------------------------------------------------------------------
    # 3. Run walk-forward backtests
    # ------------------------------------------------------------------
    print(f"\n[3/3] Running backtests …\n")

    # results[strategy_name][window_label] = {"in_sample": {...}, "out_of_sample": {...}}
    all_results: dict[str, dict] = {}

    for strat_cfg in STRATEGIES:
        sname  = strat_cfg["name"]
        sclass = strat_cfg["class"]
        sparams = strat_cfg["params"]
        all_results[sname] = {}

        for window in WINDOWS:
            wlabel = window["label"]
            print(f"  {sname} / {wlabel}")

            # In-sample (training window)
            print(f"    In-sample  {window['train_start']} → {window['train_end']}", end=" … ")
            in_m = run_one_backtest(sclass, sparams, featured_data,
                                    window["train_start"], window["train_end"])
            print(f"Sharpe={_fmt(in_m['sharpe'], '.4f')}")

            # Out-of-sample (test window)
            print(f"    Out-sample {window['test_start']} → {window['test_end']}", end=" … ")
            out_m = run_one_backtest(sclass, sparams, featured_data,
                                     window["test_start"], window["test_end"])
            print(f"Sharpe={_fmt(out_m['sharpe'], '.4f')}")

            all_results[sname][wlabel] = {
                "in_sample":      in_m,
                "out_of_sample":  out_m,
            }

    # ------------------------------------------------------------------
    # 4. Print results table
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  RESULTS TABLE")
    print("=" * 70)
    sep = print_header()

    for strat_cfg in STRATEGIES:
        sname = strat_cfg["name"]
        first_strat_row = True

        for window in WINDOWS:
            wlabel = window["label"]
            res = all_results[sname][wlabel]

            strat_display = sname if first_strat_row else ""
            first_strat_row = False

            # In-sample row
            print_row(
                strat_display,
                wlabel,
                "IN",
                f"{window['train_start'][:4]}–{window['train_end'][:4]}",
                res["in_sample"],
            )

            # Out-of-sample row
            print_row(
                "",
                "",
                "OUT",
                f"{window['test_start'][:4]}–{window['test_end'][:4]}",
                res["out_of_sample"],
            )

        print(sep)

    # ------------------------------------------------------------------
    # 5. Verdicts
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  VERDICTS  (threshold: out-of-sample Sharpe > {:.1f} in BOTH windows)".format(
        SHARPE_THRESHOLD))
    print("=" * 70)

    for strat_cfg in STRATEGIES:
        sname = strat_cfg["name"]
        oos_sharpes = []

        for window in WINDOWS:
            wlabel = window["label"]
            oos = all_results[sname][wlabel]["out_of_sample"]
            sharpe = oos["sharpe"]
            oos_sharpes.append(sharpe)

        valid_sharpes = [s for s in oos_sharpes if not math.isnan(s)]
        all_pass = (
            len(valid_sharpes) == len(WINDOWS)
            and all(s > SHARPE_THRESHOLD for s in valid_sharpes)
        )

        verdict = "CONSISTENT" if all_pass else "UNSTABLE"
        sharpe_summary = "  |  ".join(
            f"W{i+1}: {_fmt(s, '.4f')}" for i, s in enumerate(oos_sharpes)
        )

        marker = ">>>" if all_pass else "   "
        print(f"  {marker} {sname:<22}  {verdict:<12}  (OOS Sharpes: {sharpe_summary})")

    print()
    print("  CONSISTENT = strategy generalises; OOS Sharpe held above {:.1f} in every window.".format(
        SHARPE_THRESHOLD))
    print("  UNSTABLE   = possible overfitting or regime sensitivity; review parameters.")
    print()


if __name__ == "__main__":
    main()
