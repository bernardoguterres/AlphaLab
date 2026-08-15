"""Canonical Wilder RSI tests (Prompt 2.5 remediation, 2026-08-15).

See FINAL_ENGINEERING_AUDIT.md / END_TO_END_VALIDATION.md for the two
defects this fixes: (A) rsi_period was accepted by RSIMeanReversion but
never actually used - the strategy always read a fixed, hardcoded
RSI(14) column; (B) AlphaLab's old RSI formula (raw EWM, no warm-up
guard) and AlphaLive's (the `ta` library) disagreed numerically.

The golden values below are pinned literals, independently duplicated in
AlphaLive's tests/test_rsi_wilder.py - both repos assert against the SAME
numbers rather than importing a shared dependency, matching this
project's "two independent implementations + parity test" pattern.
"""

import numpy as np
import pandas as pd
import pytest

from alphalab.strategies.implementations.rsi_mean_reversion import (
    RSIMeanReversion,
    rsi_wilder,
)

# 30-bar deterministic mixed sequence (small up/down zigzag riding a
# gentle uptrend) - exercises both gains and losses every period.
GOLDEN_CLOSES = [
    100.00,
    100.50,
    100.25,
    101.00,
    100.75,
    101.50,
    102.00,
    101.25,
    102.50,
    103.00,
    102.75,
    103.50,
    104.00,
    103.25,
    104.50,
    105.00,
    104.25,
    105.50,
    106.00,
    105.25,
    106.50,
    107.00,
    106.25,
    107.50,
    108.00,
    107.25,
    108.50,
    109.00,
    108.25,
    109.50,
]


def _close():
    return pd.Series(GOLDEN_CLOSES)


@pytest.mark.parametrize("period", [9, 14, 21])
def test_rsi_wilder_warmup_rows_are_nan(period):
    r = rsi_wilder(_close(), period)
    assert r.iloc[:period].isna().all()


@pytest.mark.parametrize(
    "period,expected_first",
    [(9, 77.272727), (14, 75.0), (21, 74.137931)],
)
def test_rsi_wilder_first_valid_row(period, expected_first):
    r = rsi_wilder(_close(), period)
    assert r.first_valid_index() == period
    assert r.iloc[period] == pytest.approx(expected_first, abs=1e-5)


def test_rsi_wilder_steady_state_values_period_9():
    r = rsi_wilder(_close(), 9)
    assert r.iloc[10] == pytest.approx(73.513514, abs=1e-5)
    assert r.iloc[29] == pytest.approx(71.681515, abs=1e-5)


def test_rsi_wilder_steady_state_values_period_14():
    r = rsi_wilder(_close(), 14)
    assert r.iloc[19] == pytest.approx(69.36129, abs=1e-5)
    assert r.iloc[29] == pytest.approx(71.86734, abs=1e-5)


def test_rsi_wilder_steady_state_values_period_21():
    r = rsi_wilder(_close(), 21)
    assert r.iloc[29] == pytest.approx(72.112145, abs=1e-5)


def test_rsi_wilder_flat_price_is_50():
    """No movement at all: avg_gain == avg_loss == 0 -> RSI = 50, not NaN
    or a division-by-zero artifact."""
    r = rsi_wilder(pd.Series([100.0] * 40), 14)
    assert r.iloc[14:].eq(50.0).all()


def test_rsi_wilder_monotonic_rise_is_100():
    r = rsi_wilder(pd.Series(np.arange(100, 160, 1.0)), 14)
    assert r.iloc[14:].eq(100.0).all()


def test_rsi_wilder_monotonic_fall_is_0():
    r = rsi_wilder(pd.Series(np.arange(160, 100, -1.0)), 14)
    assert r.iloc[14:].eq(0.0).all()


def test_rsi_wilder_too_short_series_is_all_nan():
    r = rsi_wilder(pd.Series([100.0, 101.0, 99.0]), 14)
    assert r.isna().all()


# ---------------------------------------------------------------------------
# Parameter functionality: rsi_period must genuinely change values, and can
# change which bars trigger a signal.
# ---------------------------------------------------------------------------


def test_rsi_period_9_differs_from_14_where_mathematically_expected():
    close = _close()
    r9 = rsi_wilder(close, 9)
    r14 = rsi_wilder(close, 14)
    common_idx = r9.dropna().index.intersection(r14.dropna().index)
    assert len(common_idx) > 0
    # A shorter lookback must be more reactive - values must differ on this
    # zigzag dataset (not identical by construction).
    assert not np.allclose(r9.loc[common_idx], r14.loc[common_idx])


def test_rsi_mean_reversion_generate_signals_uses_the_configured_period():
    """The actual strategy, not just the bare rsi_wilder() function, must
    produce different signals for rsi_period=9 vs rsi_period=14 on a
    dataset engineered to cross the oversold threshold at period 9 but not
    at period 14 - proving generate_signals() genuinely consumes the
    parameter end to end."""
    # A zigzag baseline (so both periods carry real gain/loss memory) then
    # a moderate decline: by construction (verified during test authoring)
    # RSI(9) drops to ~26 (oversold, <30) at bar 28 while RSI(14) is still
    # ~35 (not oversold) at the same bar - a genuine asymmetric threshold
    # crossing, not an extreme move that trivially breaches both.
    prices = [100.0]
    for i in range(24):
        prices.append(prices[-1] + (1.0 if i % 2 == 0 else -0.8))
    for i in range(5):
        prices.append(prices[-1] - 1.5)
    prices += [prices[-1]] * 5

    data = pd.DataFrame(
        {
            "Close": prices,
            "ATR": [1.0] * len(prices),
            "BB_Lower": [90.0] * len(prices),
            "BB_Upper": [110.0] * len(prices),
        }
    )

    strat9 = RSIMeanReversion(
        {
            "rsi_period": 9,
            "oversold": 30,
            "overbought": 70,
            "use_bb_confirmation": False,
        }
    )
    strat14 = RSIMeanReversion(
        {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "use_bb_confirmation": False,
        }
    )
    sig9 = strat9.generate_signals(data)
    sig14 = strat14.generate_signals(data)

    assert not sig9["signal"].equals(sig14["signal"]), (
        "rsi_period=9 and rsi_period=14 must be able to produce different "
        "signals on a dataset engineered to cross the oversold threshold "
        "asymmetrically between the two periods - if they're identical, "
        "rsi_period isn't actually affecting the strategy's decisions."
    )
