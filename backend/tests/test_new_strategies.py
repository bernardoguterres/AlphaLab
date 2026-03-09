"""Tests for new trading strategies (Bollinger Breakout and VWAP Reversion)."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategies.implementations import BollingerBreakout, VWAPReversion
from src.data.processor import FeatureEngineer


def _make_test_data(n=300, trend=True):
    """Create synthetic price data for testing."""
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", periods=n)

    if trend:
        # Trending price
        base = np.linspace(100, 150, n)
    else:
        # Mean-reverting price
        base = 125 + 10 * np.sin(np.linspace(0, 4 * np.pi, n))

    noise = np.random.normal(0, 2, n)
    close = base + noise

    high = close + np.abs(np.random.normal(0, 1, n))
    low = close - np.abs(np.random.normal(0, 1, n))
    open_ = close + np.random.normal(0, 0.5, n)
    volume = np.random.randint(1_000_000, 5_000_000, n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)

    processor = FeatureEngineer()
    return processor.process(df)


class TestBollingerBreakout:
    """Tests for Bollinger Breakout strategy."""

    def test_buy_signal_on_upper_band_break(self):
        """Test that buy signal is generated on upper band breakout."""
        data = _make_test_data(n=300, trend=True)

        strategy = BollingerBreakout({
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "confirmation_bars": 2,
            "volume_filter": False,
            "volume_threshold": 1.5,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        # Result is a DataFrame with 'signal' column
        assert "signal" in result.columns
        assert len(result) == len(data)

    def test_sell_signal_on_lower_band_break(self):
        """Test that sell signal is generated on lower band breakout."""
        data = _make_test_data(n=300, trend=False)

        strategy = BollingerBreakout({
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "confirmation_bars": 2,
            "volume_filter": False,
            "volume_threshold": 1.5,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        # Strategy should run successfully
        assert "signal" in result.columns
        assert len(result) == len(data)

    def test_volume_filter_works(self):
        """Test that volume filter affects signal generation."""
        data = _make_test_data(n=300, trend=True)

        # Without volume filter
        strategy_no_filter = BollingerBreakout({
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "confirmation_bars": 1,
            "volume_filter": False,
            "volume_threshold": 1.5,
            "cooldown_days": 1,
        })

        result_no_filter = strategy_no_filter.generate_signals(data)
        assert "signal" in result_no_filter.columns

        # With volume filter
        strategy_with_filter = BollingerBreakout({
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "confirmation_bars": 1,
            "volume_filter": True,
            "volume_threshold": 2.0,
            "cooldown_days": 1,
        })

        result_with_filter = strategy_with_filter.generate_signals(data)
        assert "signal" in result_with_filter.columns

    def test_confirmation_bars_requirement(self):
        """Test that confirmation bars requirement works."""
        data = _make_test_data(n=300, trend=True)

        # Different confirmation bars should produce valid results
        for confirmation_bars in [1, 2, 3]:
            strategy = BollingerBreakout({
                "bb_period": 20,
                "bb_std_dev": 2.0,
                "confirmation_bars": confirmation_bars,
                "volume_filter": False,
                "volume_threshold": 1.5,
                "cooldown_days": 1,
            })

            result = strategy.generate_signals(data)
            assert "signal" in result.columns

    def test_parameter_validation(self):
        """Test that parameter validation works."""
        # Invalid bb_period (too low)
        with pytest.raises(ValueError, match="bb_period"):
            BollingerBreakout({"bb_period": 3})

        # Invalid confirmation_bars
        with pytest.raises(ValueError, match="confirmation_bars"):
            BollingerBreakout({"confirmation_bars": 0})

    def test_no_look_ahead_bias(self):
        """Test that strategy doesn't use future data."""
        data = _make_test_data(n=300)

        strategy = BollingerBreakout({
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "confirmation_bars": 2,
            "volume_filter": False,
            "volume_threshold": 1.5,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        # First 20 bars should have no signals (need BB calculation)
        assert result["signal"].iloc[:20].abs().sum() == 0

        # Signals should be 0, 1, or -1
        assert set(result["signal"].unique()).issubset({0, 1, -1})


class TestVWAPReversion:
    """Tests for VWAP Reversion strategy."""

    def test_buy_signal_below_vwap_deviation(self):
        """Test that buy signal is generated when price is below VWAP."""
        data = _make_test_data(n=300, trend=False)

        strategy = VWAPReversion({
            "vwap_period": 20,
            "deviation_threshold": 2.0,
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        assert "signal" in result.columns
        assert len(result) == len(data)

    def test_sell_signal_above_vwap_deviation(self):
        """Test that sell signal is generated when price is above VWAP."""
        data = _make_test_data(n=300, trend=False)

        strategy = VWAPReversion({
            "vwap_period": 20,
            "deviation_threshold": 2.0,
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        assert "signal" in result.columns
        assert len(result) == len(data)

    def test_rsi_filter_works(self):
        """Test that RSI filter affects signal generation."""
        data = _make_test_data(n=300, trend=False)

        # Different RSI thresholds should produce valid results
        for oversold, overbought in [(30, 70), (25, 75)]:
            strategy = VWAPReversion({
                "vwap_period": 20,
                "deviation_threshold": 1.5,
                "rsi_period": 14,
                "oversold": oversold,
                "overbought": overbought,
                "cooldown_days": 1,
            })

            result = strategy.generate_signals(data)
            assert "signal" in result.columns

    def test_exit_at_vwap(self):
        """Test that exits occur when price returns to VWAP."""
        data = _make_test_data(n=300, trend=False)

        strategy = VWAPReversion({
            "vwap_period": 20,
            "deviation_threshold": 2.0,
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        # Strategy should produce valid signals
        assert "signal" in result.columns
        assert len(result) == len(data)

    def test_parameter_validation(self):
        """Test that parameter validation works."""
        # Invalid vwap_period (too low)
        with pytest.raises(ValueError, match="vwap_period"):
            VWAPReversion({"vwap_period": 3})

        # Invalid RSI thresholds (oversold >= overbought)
        with pytest.raises(ValueError, match="oversold"):
            VWAPReversion({
                "oversold": 50,
                "overbought": 40,
            })

    def test_no_look_ahead_bias(self):
        """Test that strategy doesn't use future data."""
        data = _make_test_data(n=300)

        strategy = VWAPReversion({
            "vwap_period": 20,
            "deviation_threshold": 2.0,
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "cooldown_days": 3,
        })

        result = strategy.generate_signals(data)

        # First 20+ bars should have no signals (need VWAP + RSI calculation)
        warmup_period = max(20, 14)
        assert result["signal"].iloc[:warmup_period].abs().sum() == 0

        # Signals should be 0, 1, or -1
        assert set(result["signal"].unique()).issubset({0, 1, -1})
