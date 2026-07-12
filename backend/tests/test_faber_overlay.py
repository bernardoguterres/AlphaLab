"""Tests for the Faber 10-month SMA tactical overlay benchmark."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.faber_overlay import faber_signal, faber_overlay_returns


def _monthly_series(prices: list[float]) -> pd.Series:
    dates = pd.date_range("2018-01-31", periods=len(prices), freq="ME")
    return pd.Series(prices, index=dates)


class TestFaberSignal:
    def test_warmup_period_is_false(self):
        prices = list(range(100, 100 + 15))  # steadily rising
        sig = faber_signal(_monthly_series(prices), sma_months=10)
        assert not sig.iloc[:9].any()

    def test_uptrend_is_invested_after_warmup(self):
        prices = [100 + i for i in range(20)]  # strictly rising
        sig = faber_signal(_monthly_series(prices), sma_months=10)
        assert sig.iloc[-1] == True

    def test_downtrend_is_cash_after_warmup(self):
        prices = [200 - i * 5 for i in range(20)]  # strictly falling
        sig = faber_signal(_monthly_series(prices), sma_months=10)
        assert sig.iloc[-1] == False


class TestFaberOverlayReturns:
    def test_no_lookahead_first_period_signal_does_not_affect_first_return(self):
        prices = [100 + i for i in range(15)]
        returns = faber_overlay_returns(_monthly_series(prices), sma_months=10)
        assert np.isnan(returns.iloc[0])

    def test_uptrend_overlay_matches_buy_and_hold_once_invested(self):
        prices = [100 + i * 2 for i in range(20)]  # steady uptrend
        s = _monthly_series(prices)
        overlay_returns = faber_overlay_returns(s, sma_months=10)
        buy_hold_returns = s.pct_change()

        # Once warmed up and above SMA, overlay should track buy-and-hold.
        tail_overlay = overlay_returns.iloc[-5:]
        tail_bh = buy_hold_returns.iloc[-5:]
        pd.testing.assert_series_equal(tail_overlay, tail_bh, check_names=False)

    def test_downtrend_overlay_earns_cash_return_not_asset_loss(self):
        prices = [100 - i * 3 for i in range(20)]  # steady downtrend
        s = _monthly_series(prices)
        overlay_returns = faber_overlay_returns(
            s, sma_months=10, cash_return_per_period=0.0
        )

        # Once the overlay has flipped to cash, later periods should be
        # exactly 0.0 (cash), not the asset's negative return.
        assert overlay_returns.iloc[-1] == 0.0

    def test_cash_return_parameter_is_used_while_out_of_market(self):
        prices = [100 - i * 3 for i in range(20)]
        s = _monthly_series(prices)
        overlay_returns = faber_overlay_returns(
            s, sma_months=10, cash_return_per_period=0.002
        )
        assert overlay_returns.iloc[-1] == pytest.approx(0.002)

    def test_custom_sma_window(self):
        prices = [100 + i for i in range(10)]
        sig_short = faber_signal(_monthly_series(prices), sma_months=3)
        sig_long = faber_signal(_monthly_series(prices), sma_months=8)
        # Shorter SMA warms up (has a real signal) earlier than the longer one.
        assert sig_short.iloc[3:].any()
        assert not sig_long.iloc[3:7].any()
