"""Faber (2007/2013) 10-month SMA tactical overlay - mandatory comparison
benchmark alongside buy-and-hold, per docs/STRATEGY_RESEARCH_PLAN.md section D.

Faber, M. (2007/2013). "A Quantitative Approach to Tactical Asset
Allocation." SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461

Rule: at each month-end, hold the asset if its price is above its trailing
10-month simple moving average; otherwise hold cash (0% return that month).
The most rigorously documented "simple timing" benchmark in the practitioner
literature - any strategy claiming a timing/trend edge should beat this, not
just buy-and-hold.

No look-ahead: the signal computed from month t's close decides exposure for
month t -> t+1 (shift(1) below), matching every other engine in this
codebase's next-period execution convention.
"""

from __future__ import annotations

import pandas as pd


def faber_signal(monthly_close: pd.Series, sma_months: int = 10) -> pd.Series:
    """True (invested) if price > trailing sma_months SMA, else False (cash).
    NaN for the warmup period is treated as False (not enough history yet ->
    stay in cash, the conservative default)."""
    sma = monthly_close.rolling(sma_months).mean()
    return (monthly_close > sma).fillna(False)


def faber_overlay_returns(
    monthly_close: pd.Series, sma_months: int = 10, cash_return_per_period: float = 0.0
) -> pd.Series:
    """Per-period strategy returns applying the Faber overlay to one asset's
    monthly close series. Returns NaN for the first period (no prior return).
    """
    signal = faber_signal(monthly_close, sma_months)
    asset_returns = monthly_close.pct_change()
    # Decision at month t (signal) governs exposure for the return realized
    # AT month t (i.e. the return from t-1 to t) is NOT what t's signal
    # governs - t's signal governs the NEXT period's return, hence shift(1).
    invested_last_period = signal.shift(1, fill_value=False)
    strategy_returns = asset_returns.where(invested_last_period, cash_return_per_period)
    strategy_returns.iloc[0] = float("nan")
    return strategy_returns
