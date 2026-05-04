"""Tests for GreenblattWeekly strategy."""

import unittest

import numpy as np
import pandas as pd

from src.strategies.implementations.greenblatt_weekly import GreenblattWeekly


def _make_weekly_data(n=200, base_price=100.0, trend="flat", seed=42) -> pd.DataFrame:
    """Generate synthetic weekly OHLCV data with pre-computed indicators."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2016-01-04", periods=n, freq="W-MON")

    if trend == "up":
        prices = base_price + np.linspace(0, 80, n) + rng.normal(0, 2, n)
    elif trend == "down":
        prices = base_price + np.linspace(0, -60, n) + rng.normal(0, 2, n)
    else:
        prices = base_price + rng.normal(0, 5, n).cumsum() * 0.3

    prices = np.maximum(prices, 1.0)
    closes = pd.Series(prices, index=dates)

    df = pd.DataFrame(index=dates)
    df["Open"] = closes * 0.99
    df["High"] = closes * 1.02
    df["Low"] = closes * 0.98
    df["Close"] = closes
    df["Volume"] = rng.integers(1_000_000, 5_000_000, n)

    df["SMA_10"] = closes.rolling(10).mean()
    df["SMA_50"] = closes.rolling(50).mean()

    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    return df


class TestGreenblattWeekly(unittest.TestCase):

    def _run(self, data, params=None):
        strat = GreenblattWeekly(params=params or {})
        return strat.generate_signals(data)

    def test_signals_dataframe_has_required_columns(self):
        signals = self._run(_make_weekly_data())
        self.assertIn("signal", signals.columns)
        self.assertIn("confidence", signals.columns)
        self.assertIn("reason", signals.columns)

    def test_signal_values_valid(self):
        signals = self._run(_make_weekly_data())
        self.assertTrue(signals["signal"].isin([-1, 0, 1]).all())

    def test_confidence_between_zero_and_one(self):
        signals = self._run(_make_weekly_data())
        self.assertTrue((signals["confidence"] >= 0.0).all())
        self.assertTrue((signals["confidence"] <= 1.0).all())

    def test_no_consecutive_buy_signals(self):
        signals = self._run(_make_weekly_data(n=200))
        buys = signals[signals["signal"] == 1]
        if len(buys) >= 2:
            indices = buys.index.tolist()
            for i in range(len(indices) - 1):
                between = signals.loc[indices[i]:indices[i + 1], "signal"]
                self.assertIn(-1, between.values, "BUY followed by BUY with no SELL between")

    def test_no_sell_without_position(self):
        signals = self._run(_make_weekly_data())
        in_pos = False
        for sig in signals["signal"]:
            if sig == 1:
                in_pos = True
            elif sig == -1:
                self.assertTrue(in_pos, "SELL generated with no open position")
                in_pos = False

    def test_trailing_stop_fires_on_large_drop(self):
        """A 30% drop from peak should always trigger the trailing stop (default 20%)."""
        data = _make_weekly_data(n=200, trend="up", seed=10)
        # Force entry at bar 80 via oversold RSI
        data.loc[data.index[80], "RSI"] = 25.0
        # Crash 30% at bar 100
        peak = data["Close"].iloc[80]
        data.loc[data.index[100], "Close"] = peak * 0.65

        signals = self._run(data, params={"min_hold_bars": 1, "trailing_stop_pct": 0.20})
        sells = signals[signals["signal"] == -1]
        stop_sells = sells[sells["reason"].str.contains("Trailing stop", na=False)]
        self.assertGreater(len(stop_sells), 0, "Trailing stop should have fired")

    def test_no_rsi_exit_by_default(self):
        """RSI overbought should NOT trigger exit with default params."""
        data = _make_weekly_data(n=200, trend="up", seed=7)
        # Force entry then push RSI above 65
        data.loc[data.index[80], "RSI"] = 25.0
        for i in range(90, 110):
            data.loc[data.index[i], "RSI"] = 80.0

        signals = self._run(data, params={"min_hold_bars": 1})
        rsi_exits = signals[signals["reason"].str.contains("overbought", na=False)]
        self.assertEqual(len(rsi_exits), 0, "RSI exit should be disabled by default")

    def test_no_sma_death_cross_exit_by_default(self):
        """SMA death-cross should NOT trigger exit with default params."""
        data = _make_weekly_data(n=200, trend="up", seed=8)
        data.loc[data.index[80], "RSI"] = 25.0
        # Force death-cross at bar 100
        slow = data["SMA_50"].iloc[100]
        data.loc[data.index[99], "SMA_10"] = slow + 1
        data.loc[data.index[100], "SMA_10"] = slow - 1

        signals = self._run(data, params={"min_hold_bars": 1})
        cross_exits = signals[signals["reason"].str.contains("death-cross", na=False)]
        self.assertEqual(len(cross_exits), 0, "SMA death-cross exit should be disabled by default")

    def test_rsi_exit_fires_when_enabled(self):
        """RSI exit SHOULD fire when exit_rsi_overbought=True and min_hold met."""
        data = _make_weekly_data(n=200, trend="up", seed=9)
        data.loc[data.index[60], "RSI"] = 25.0
        for i in range(75, 90):
            data.loc[data.index[i], "RSI"] = 80.0

        signals = self._run(data, params={
            "min_hold_bars": 10,
            "exit_rsi_overbought": True,
            "trailing_stop_pct": 0.50,  # loose stop so RSI fires first
        })
        rsi_exits = signals[signals["reason"].str.contains("overbought", na=False)]
        self.assertGreater(len(rsi_exits), 0, "RSI exit should fire when enabled")

    def test_default_min_hold_is_52(self):
        strat = GreenblattWeekly(params={})
        self.assertEqual(strat.params["min_hold_bars"], 52)

    def test_default_trailing_stop_is_20_pct(self):
        strat = GreenblattWeekly(params={})
        self.assertAlmostEqual(strat.params["trailing_stop_pct"], 0.20)

    def test_validate_params_fast_ge_slow_raises(self):
        with self.assertRaises(ValueError):
            GreenblattWeekly(params={"fast_sma": 50, "slow_sma": 10})

    def test_validate_params_rsi_threshold_raises(self):
        with self.assertRaises(ValueError):
            GreenblattWeekly(params={"rsi_oversold": 60, "rsi_overbought": 40})

    def test_validate_params_trailing_stop_out_of_range(self):
        with self.assertRaises(ValueError):
            GreenblattWeekly(params={"trailing_stop_pct": 0.99})

    def test_handles_insufficient_data_gracefully(self):
        data = _make_weekly_data(n=10)
        signals = self._run(data)
        self.assertTrue((signals["signal"] == 0).all())

    def test_required_columns_no_atr(self):
        strat = GreenblattWeekly(params={"fast_sma": 10, "slow_sma": 50})
        cols = strat.required_columns()
        self.assertIn("SMA_10", cols)
        self.assertIn("SMA_50", cols)
        self.assertIn("RSI", cols)
        self.assertNotIn("ATR", cols)  # ATR no longer needed


if __name__ == "__main__":
    unittest.main()
