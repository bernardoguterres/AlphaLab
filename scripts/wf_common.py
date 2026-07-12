"""Shared helpers for the standalone research scripts in this directory
(walk-forward validation, Greenblatt/sector-rotation research, evidence-
checklist computation). Not part of the pytest suite - these are one-off
analysis tools, kept here only to avoid the scripts drifting on formatting
and data-fetching/metrics logic. Consolidated 2026-07-12 after 7 near-
duplicate one-shot scripts accumulated in one research session - see
docs/experiments/registry.jsonl for the permanent record of what each of
those scripts found; this module is how to reproduce or extend that
research going forward, not a replacement for the registry.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd


def setup_backend_path() -> None:
    """Make AlphaLab's ``backend/`` importable regardless of cwd."""
    backend = str(Path(__file__).resolve().parent.parent / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)


def fmt(value, fmt_str: str, na: str = "  N/A  ") -> str:
    """Format a numeric value, returning `na` if it's None/NaN/unformattable."""
    if value is None:
        return na
    try:
        if math.isnan(float(value)):
            return na
        return format(value, fmt_str)
    except (TypeError, ValueError):
        return na


def print_table_header(col_specs: list[tuple[str, str, int, str]]) -> str:
    """Print a header + separator line for the given column spec.

    col_specs: list of (key, label, width, align) where align is "<" or ">".
    Returns the separator string so callers can reprint it between groups.
    """
    header = " ".join(f"{label:{align}{width}}" for _, label, width, align in col_specs)
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    return sep


def print_table_row(
    col_specs: list[tuple[str, str, int, str]], values: dict, note: str = ""
) -> None:
    """Print one row using the same column spec passed to `print_table_header`."""
    parts = [
        f"{values.get(key, ''):{align}{width}}" for key, _, width, align in col_specs
    ]
    print(" ".join(parts) + note)


def fetch_weekly_close(ticker: str, start: str, end: str, min_bars: int = 10):
    """Fetch weekly Close prices via yfinance. Returns None if unavailable
    or too short. `src.backtest.*` imports are deferred inside callers that
    need them, not here - this function only needs yfinance/pandas, which
    don't require setup_backend_path() to have run first."""
    import yfinance as yf

    raw = yf.download(
        ticker, start=start, end=end, interval="1wk", auto_adjust=True, progress=False
    )
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw[["Close"]].dropna()
    return close if len(close) >= min_bars else None


def fetch_monthly_close(ticker: str, start: str, end: str, warmup_months: int = 12):
    """Fetch monthly Close prices with warmup lookback (for the Faber
    10-month SMA). Returns None if unavailable."""
    import yfinance as yf

    warmup_start = (pd.Timestamp(start) - pd.DateOffset(months=warmup_months)).strftime(
        "%Y-%m-%d"
    )
    raw = yf.download(
        ticker,
        start=warmup_start,
        end=end,
        interval="1mo",
        auto_adjust=True,
        progress=False,
    )
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    return raw["Close"].dropna()


def compute_metrics_and_dsr(equity_curve, ledger, window_start_ts, n_trials: int = 6):
    """Restrict an equity curve to a window, compute PerformanceMetrics, and
    layer the Deflated Sharpe Ratio on top. Requires setup_backend_path() to
    have already run in the caller."""
    from src.backtest.metrics import PerformanceMetrics
    from src.backtest.deflated_sharpe import deflated_sharpe_ratio

    in_window = [p for p in equity_curve if p["date"] >= window_start_ts]
    calc = PerformanceMetrics(risk_free_rate=0.04)
    metrics = calc.calculate_all(equity_curve=in_window, trades=ledger)
    ret, risk = metrics["returns"], metrics["risk"]
    n_obs = len(in_window)
    sharpe = risk.get("sharpe_ratio", 0.0) or 0.0
    skew = ret.get("skewness", 0.0) or 0.0
    kurtosis_pearson = (
        ret.get("kurtosis", 0.0) or 0.0
    ) + 3.0  # pandas .kurt() is EXCESS kurtosis
    dsr = None
    if n_obs >= 2:
        dsr = deflated_sharpe_ratio(
            sharpe_annualized=sharpe,
            skewness=skew,
            kurtosis_pearson=kurtosis_pearson,
            n_observations=n_obs,
            n_trials=n_trials,
            periods_per_year=52,
        )
    return {
        "cagr_pct": ret.get("cagr_pct"),
        "sharpe": sharpe,
        "n_obs": n_obs,
        "dsr": dsr,
    }


def faber_benchmark_for_window(window_start: str, window_end: str, ticker: str = "SPY"):
    """Faber 10-month-SMA overlay CAGR/Sharpe for one window. Requires
    setup_backend_path() to have already run in the caller."""
    from src.backtest.faber_overlay import faber_overlay_returns

    monthly = fetch_monthly_close(ticker, window_start, window_end)
    if monthly is None:
        return None
    overlay_rets = faber_overlay_returns(monthly, sma_months=10).dropna()
    in_window = overlay_rets[overlay_rets.index >= pd.Timestamp(window_start)]
    if len(in_window) <= 1:
        return None
    equity = (1 + in_window).cumprod()
    years = len(in_window) / 12.0
    cagr = (equity.iloc[-1] ** (1 / years) - 1) * 100 if years > 0 else None
    ann_vol = in_window.std() * (12**0.5)
    ann_ret = in_window.mean() * 12
    sharpe = (ann_ret - 0.04) / ann_vol if ann_vol and ann_vol > 0 else None
    return {
        "cagr_pct": round(cagr, 2) if cagr is not None else None,
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
    }


def spy_buyhold_for_window(window_start: str, window_end: str, ticker: str = "SPY"):
    """Plain single-asset buy-and-hold CAGR/Sharpe for one window, computed
    directly from weekly returns (not routed through PortfolioConstructor,
    which requires >= 2 tickers)."""
    df = fetch_weekly_close(ticker, window_start, window_end)
    if df is None:
        return None
    rets = df["Close"].pct_change().dropna()
    n = len(rets)
    if n < 2:
        return None
    equity = (1 + rets).cumprod()
    years = n / 52.0
    cagr = (equity.iloc[-1] ** (1 / years) - 1) * 100 if years > 0 else None
    ann_ret = rets.mean() * 52
    ann_vol = rets.std() * (52**0.5)
    sharpe = (ann_ret - 0.04) / ann_vol if ann_vol and ann_vol > 0 else None
    return {
        "cagr_pct": round(cagr, 2) if cagr is not None else None,
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
    }


# Standard 6-regime window set used across the 2026-07-12 research campaign
# (docs/STRATEGY_RESEARCH_PLAN.md section D: multiple market regimes).
STANDARD_REGIME_WINDOWS = [
    {"label": "Window 1 (2018-2020)", "start": "2018-01-01", "end": "2020-12-31"},
    {"label": "Window 2 (2021-2024)", "start": "2021-01-01", "end": "2024-12-31"},
    {"label": "2008 Crisis", "start": "2007-06-01", "end": "2009-12-31"},
    {"label": "2015-2019 Grind", "start": "2015-01-01", "end": "2019-12-31"},
    {"label": "2020 COVID", "start": "2020-01-01", "end": "2020-12-31"},
    {"label": "2022 Bear", "start": "2022-01-01", "end": "2022-12-31"},
]
