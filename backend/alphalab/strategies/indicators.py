"""Parameterised indicator helpers for strategies.

The shared FeatureEngineer columns (RSI, BB_*, ATR) are computed once with
FIXED periods (RSI 14, Bollinger 20/2.0, ATR 14). Strategies that expose an
`rsi_period` / `bb_period` / `bb_std` parameter must compute the indicator
from that parameter - reading the fixed column silently ignored any
non-default value while AlphaLive (which receives the parameter in the
export) honoured it (2026-10 parity audit). These helpers use the SAME
formulas as FeatureEngineer, so default parameters reproduce the fixed
columns exactly.
"""

import numpy as np
import pandas as pd


def rsi_ewm(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI with exponential smoothing (alpha = 1/period, adjust=False), no
    seed; avg_loss == 0 -> NaN. Identical to FeatureEngineer's "RSI"."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # avg_loss == 0: RSI is 100 if there were gains, 50 if no movement at
    # all (previously NaN - an undefined RSI that blocked signals forever on
    # a series with no down-moves). Same convention as rsi_wilder().
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    return rsi.clip(0, 100)


def bollinger(close: pd.Series, period: int = 20, std: float = 2.0):
    """(lower, middle, upper) with sample std (ddof=1). Identical to
    FeatureEngineer's BB_* columns for (20, 2.0)."""
    mid = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std()
    return mid - std * sd, mid, mid + std * sd
