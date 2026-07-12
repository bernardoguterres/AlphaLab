"""Walk-Forward Validation for GreenblattWeekly Strategy.

Phase 1 - Screener: ranks a universe of stocks by Greenblatt Magic Formula
          (earnings yield + ROE) and picks the top 6 candidates.

Phase 2 - Validation: runs two rolling walk-forward windows on each candidate
          using the GreenblattWeekly strategy on weekly bars.

          Window 1: Train 2010–2017 (8y)  |  Test 2018–2020 (3y)
          Window 2: Train 2013–2020 (7y)  |  Test 2021–2024 (4y)

Verdict: CONSISTENT if out-of-sample Sharpe ≥ 0.8 AND CAGR ≥ 13% in BOTH windows.

Usage:
    cd /Users/bernardoguterrres/Desktop/Alpha/AlphaLab/backend
    source venv/bin/activate
    cd ..
    python scripts/greenblatt_walk_forward.py
"""

from __future__ import annotations

import math
import warnings

warnings.filterwarnings("ignore")

from wf_common import setup_backend_path, fmt, print_table_header, print_table_row

setup_backend_path()

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import yfinance as yf
import pandas as pd

from src.data.processor import FeatureEngineer
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.screener.fundamental_screener import FundamentalScreener
from src.strategies.implementations.greenblatt_weekly import GreenblattWeekly

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

TOP_N_CANDIDATES = 6

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

WINDOWS = [
    {
        "label": "Window 1",
        "train_start": "2010-01-01",
        "train_end": "2017-12-31",
        "test_start": "2018-01-01",
        "test_end": "2020-12-31",
    },
    {
        "label": "Window 2",
        "train_start": "2013-01-01",
        "train_end": "2020-12-31",
        "test_start": "2021-01-01",
        "test_end": "2024-12-31",
    },
]

# Thresholds for CONSISTENT verdict
SHARPE_THRESHOLD = 0.8
CAGR_THRESHOLD = 13.0  # % - must beat buy-and-hold SPY

# BacktestEngine drawdown halt at 40% - correct for weekly value strategies
MAX_DRAWDOWN_PCT = 40

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def fetch_weekly(ticker: str, start: str, end: str) -> pd.DataFrame:
    print(f"    Fetching {ticker} weekly {start} → {end} …", end=" ", flush=True)
    raw = yf.download(
        ticker, start=start, end=end, interval="1wk", auto_adjust=True, progress=False
    )
    if raw.empty:
        raise RuntimeError(f"No weekly data for {ticker}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0] for col in raw.columns]

    raw = raw.rename(columns=str.title)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(raw.columns)
    if missing:
        raise RuntimeError(f"{ticker}: missing columns {missing}")

    raw = raw[list(required)].dropna()
    raw.index = pd.to_datetime(raw.index)
    raw.index.name = "Date"
    print(f"{len(raw)} bars")
    return raw


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    fe = FeatureEngineer()
    featured = fe.process(df)
    # Drop rows where the slow SMA (50) or RSI hasn't warmed up yet
    return featured.dropna(subset=["SMA_50", "RSI"])


# ---------------------------------------------------------------------------
# Backtest helper
# ---------------------------------------------------------------------------


def run_one_backtest(
    featured_data: pd.DataFrame,
    start_date: str,
    end_date: str,
    ticker: str,
) -> dict:
    df_slice = featured_data.loc[start_date:end_date].copy()
    df_slice.attrs["ticker"] = ticker

    if len(df_slice) < 20:
        return _empty_row(f"Too few bars ({len(df_slice)})")

    strategy = GreenblattWeekly(STRATEGY_PARAMS.copy())
    engine = BacktestEngine()
    results = engine.run_backtest(
        strategy,
        df_slice,
        initial_capital=100_000,
        max_drawdown_pct=MAX_DRAWDOWN_PCT,
    )

    calculator = PerformanceMetrics(risk_free_rate=0.04)
    bm_curve = (
        results.benchmark.get("buy_and_hold_equity_curve")
        if results.benchmark
        else None
    )
    metrics = calculator.calculate_all(
        equity_curve=results.equity_curve,
        trades=results.trades,
        benchmark_curve=bm_curve,
    )

    sharpe = metrics.get("risk", {}).get("sharpe_ratio", 0.0) or 0.0
    cagr = metrics.get("returns", {}).get("cagr_pct", 0.0) or 0.0
    max_dd = metrics.get("drawdown", {}).get("max_drawdown_pct", 0.0) or 0.0
    win_rate = metrics.get("trades", {}).get("win_rate", 0.0) or 0.0
    n_trades = metrics.get("trades", {}).get("total_trades", 0) or 0

    return {
        "sharpe": sharpe,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "total_trades": n_trades,
        "error": None,
    }


def _empty_row(reason: str) -> dict:
    return {
        "sharpe": float("nan"),
        "cagr": float("nan"),
        "max_drawdown": float("nan"),
        "win_rate": float("nan"),
        "total_trades": 0,
        "error": reason,
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

COLUMNS = [
    ("ticker", "Ticker", 6, "<"),
    ("window", "Window", 10, "<"),
    ("phase", "Ph", 4, "<"),
    ("period", "Period", 24, "<"),
    ("sharpe", "Sharpe", 8, ">"),
    ("cagr", "CAGR%", 8, ">"),
    ("win_rate", "WinRate", 9, ">"),
    ("max_dd", "MaxDD%", 9, ">"),
    ("trades", "Trades", 7, ">"),
]


def _header() -> str:
    return print_table_header(COLUMNS)


def _row(ticker_lbl, window_lbl, phase, period, m):
    wr = m["win_rate"]
    if m["error"] or wr is None or (isinstance(wr, float) and math.isnan(wr)):
        wr_str = "  N/A  "
    else:
        wr_str = f"{wr * 100:.1f}%"

    print_table_row(
        COLUMNS,
        {
            "ticker": ticker_lbl,
            "window": window_lbl,
            "phase": phase,
            "period": period,
            "sharpe": fmt(m["sharpe"], ".4f"),
            "cagr": fmt(m["cagr"], ".1f"),
            "win_rate": wr_str,
            "max_dd": fmt(m["max_drawdown"], ".1f"),
            "trades": str(m["total_trades"]) if not m["error"] else "N/A",
        },
        note=f"  [{m['error']}]" if m["error"] else "",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print()
    print("=" * 80)
    print("  AlphaLab - GreenblattWeekly Walk-Forward Validation")
    print(f"  Universe   : {len(UNIVERSE)} tickers")
    print(f"  Candidates : top {TOP_N_CANDIDATES} by Greenblatt rank")
    print(
        f"  Strategy   : GreenblattWeekly (weekly bars, 52w min hold, 20% trailing stop)"
    )
    print(f"  Windows    : {len(WINDOWS)}")
    for w in WINDOWS:
        print(
            f"    {w['label']}: Train {w['train_start'][:4]}–{w['train_end'][:4]}  |  "
            f"Test {w['test_start'][:4]}–{w['test_end'][:4]}"
        )
    print(
        f"  Verdict threshold: OOS Sharpe ≥ {SHARPE_THRESHOLD} AND CAGR ≥ {CAGR_THRESHOLD}% in BOTH windows"
    )
    print("=" * 80)

    # ------------------------------------------------------------------
    # 1. Greenblatt screener
    # ------------------------------------------------------------------
    print(f"\n[1/3] Running Greenblatt screener on {len(UNIVERSE)} tickers …\n")

    screener = FundamentalScreener(
        universe=UNIVERSE,
        min_market_cap_b=10.0,
        max_debt_to_equity=2.0,
        request_delay=0.5,
    )
    try:
        top_candidates = screener.screen(top_n=TOP_N_CANDIDATES)
    except Exception as exc:
        print(f"  Screener error: {exc}")
        print("  Using fallback candidate list from CLAUDE.md verified results.")

        class _FakeSR:
            def __init__(self, t):
                self.ticker = t
                self.combined_rank = None
                self.earnings_yield = None
                self.return_on_capital = None

        top_candidates = [
            _FakeSR(t) for t in ["META", "LLY", "NVDA", "JPM", "AAPL", "V"]
        ]

    if not top_candidates:
        print("  No candidates returned - aborting.")
        return

    print(f"\n  Screener results (top {len(top_candidates)}):")
    print(
        f"  {'#':<3} {'Ticker':<7} {'Combined Rank':<14} {'Earnings Yield':>14} {'ROC':>8}"
    )
    print("  " + "-" * 50)
    for i, c in enumerate(top_candidates, 1):
        ey = f"{c.earnings_yield:.4f}" if c.earnings_yield is not None else "  N/A"
        roc = (
            f"{c.return_on_capital:.3f}" if c.return_on_capital is not None else " N/A"
        )
        rank = str(c.combined_rank) if c.combined_rank is not None else " N/A"
        print(f"  {i:<3} {c.ticker:<7} {rank:<14} {ey:>14} {roc:>8}")

    candidate_tickers = [c.ticker for c in top_candidates]

    # ------------------------------------------------------------------
    # 2. Fetch & engineer weekly data for all candidates
    # ------------------------------------------------------------------
    print(f"\n[2/3] Fetching weekly market data …\n")

    all_starts = [w["train_start"] for w in WINDOWS]
    all_ends = [w["test_end"] for w in WINDOWS]
    fetch_start = min(all_starts)
    fetch_end = max(all_ends)

    featured: dict[str, pd.DataFrame] = {}
    failed_tickers = []

    for ticker in candidate_tickers:
        try:
            raw = fetch_weekly(ticker, fetch_start, fetch_end)
            fd = engineer_features(raw)
            featured[ticker] = fd
            print(f"    Features ready: {len(fd)} usable weekly bars after warm-up\n")
        except Exception as exc:
            print(f"    SKIP {ticker}: {exc}\n")
            failed_tickers.append(ticker)

    active_tickers = [t for t in candidate_tickers if t not in failed_tickers]
    if not active_tickers:
        print("  No data available for any candidate - aborting.")
        return

    # ------------------------------------------------------------------
    # 3. Walk-forward backtests
    # ------------------------------------------------------------------
    print(f"[3/3] Running walk-forward backtests …\n")

    all_results: dict[str, dict] = {}

    for ticker in active_tickers:
        all_results[ticker] = {}
        fd = featured[ticker]

        for window in WINDOWS:
            wlabel = window["label"]
            print(f"  {ticker} / {wlabel}")

            print(
                f"    In-sample  {window['train_start']} → {window['train_end']}",
                end=" … ",
            )
            in_m = run_one_backtest(
                fd, window["train_start"], window["train_end"], ticker
            )
            print(
                f"Sharpe={fmt(in_m['sharpe'], '.3f')}  CAGR={fmt(in_m['cagr'], '.1f')}%"
            )

            print(
                f"    Out-sample {window['test_start']} → {window['test_end']}",
                end=" … ",
            )
            out_m = run_one_backtest(
                fd, window["test_start"], window["test_end"], ticker
            )
            print(
                f"Sharpe={fmt(out_m['sharpe'], '.3f')}  CAGR={fmt(out_m['cagr'], '.1f')}%"
            )

            all_results[ticker][wlabel] = {
                "in_sample": in_m,
                "out_of_sample": out_m,
            }

    # ------------------------------------------------------------------
    # 4. Results table
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  RESULTS TABLE")
    print("=" * 80)
    sep = _header()

    for ticker in active_tickers:
        first_row = True

        for window in WINDOWS:
            wlabel = window["label"]
            res = all_results[ticker][wlabel]

            ticker_lbl = ticker if first_row else ""
            first_row = False

            _row(
                ticker_lbl,
                wlabel,
                "IN",
                f"{window['train_start'][:4]}–{window['train_end'][:4]}",
                res["in_sample"],
            )
            _row(
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
    print("=" * 80)
    print(
        f"  VERDICTS  (OOS Sharpe ≥ {SHARPE_THRESHOLD} AND CAGR ≥ {CAGR_THRESHOLD}% in BOTH windows)"
    )
    print("=" * 80)

    consistent_tickers = []

    for ticker in active_tickers:
        oos_rows = []
        for window in WINDOWS:
            oos_rows.append(all_results[ticker][window["label"]]["out_of_sample"])

        valid = all(r["error"] is None for r in oos_rows)
        all_sharpe_pass = valid and all(
            not math.isnan(r["sharpe"]) and r["sharpe"] >= SHARPE_THRESHOLD
            for r in oos_rows
        )
        all_cagr_pass = valid and all(
            not math.isnan(r["cagr"]) and r["cagr"] >= CAGR_THRESHOLD for r in oos_rows
        )
        passes = all_sharpe_pass and all_cagr_pass

        if passes:
            consistent_tickers.append(ticker)

        verdict = "CONSISTENT" if passes else "UNSTABLE"
        marker = ">>>" if passes else "   "

        sharpe_str = "  |  ".join(
            f"{w['label']}: {fmt(all_results[ticker][w['label']]['out_of_sample']['sharpe'], '.3f')}"
            for w in WINDOWS
        )
        cagr_str = "  |  ".join(
            f"{w['label']}: {fmt(all_results[ticker][w['label']]['out_of_sample']['cagr'], '.1f')}%"
            for w in WINDOWS
        )

        print(f"  {marker} {ticker:<6}  {verdict:<12}  Sharpe: {sharpe_str}")
        print(f"              {'':22}  CAGR:   {cagr_str}")

    print()
    print(
        "  CONSISTENT = OOS Sharpe ≥ {:.1f} AND CAGR ≥ {:.0f}% in BOTH windows - safe to export to AlphaLive.".format(
            SHARPE_THRESHOLD, CAGR_THRESHOLD
        )
    )
    print("  UNSTABLE   = Fails one or more thresholds - do NOT deploy.")
    print()

    if consistent_tickers:
        print("Export candidates (all passed):", ", ".join(consistent_tickers))
        print(
            "  Next step: AlphaLab → batch backtest → export JSON → place in AlphaLive/configs/production/"
        )
    else:
        print("No candidates passed both thresholds.")
        print("  Review parameters or expand the screener universe.")
    print()


if __name__ == "__main__":
    main()
