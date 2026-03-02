"""Tests for trading strategies."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategies.implementations.moving_average_crossover import MovingAverageCrossover
from src.strategies.implementations.rsi_mean_reversion import RSIMeanReversion
from src.strategies.implementations.momentum_breakout import MomentumBreakout
from src.data.processor import FeatureEngineer


def _make_featured_data(n=500, seed=42):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2021-01-01", periods=n)
    close = 100 + rng.randn(n).cumsum() * 0.5
    close = np.maximum(close, 10)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    opn = close + rng.uniform(-1, 1, n)
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.randint(1_000_000, 10_000_000, n).astype(float)
    df = pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    fe = FeatureEngineer()
    return fe.process(df)


class TestMovingAverageCrossover:
    def test_default_params(self):
        s = MovingAverageCrossover()
        assert s.params["short_window"] == 50
        assert s.params["long_window"] == 200

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            MovingAverageCrossover({"short_window": 200, "long_window": 50})

    def test_generates_signals(self):
        data = _make_featured_data()
        s = MovingAverageCrossover()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        assert set(signals["signal"].unique()).issubset({-1, 0, 1})

    def test_cooldown_enforced(self):
        data = _make_featured_data()
        s = MovingAverageCrossover({"short_window": 10, "long_window": 30, "cooldown_days": 10})
        signals = s.generate_signals(data)
        # Check no two signals within 10 bars
        sig_idx = signals[signals["signal"] != 0].index
        for i in range(1, len(sig_idx)):
            gap = signals.index.get_loc(sig_idx[i]) - signals.index.get_loc(sig_idx[i - 1])
            assert gap > 10


class TestRSIMeanReversion:
    def test_default_params(self):
        s = RSIMeanReversion()
        assert s.params["oversold"] == 30
        assert s.params["overbought"] == 70

    def test_invalid_bounds(self):
        with pytest.raises(ValueError):
            RSIMeanReversion({"oversold": 80, "overbought": 20})

    def test_generates_signals(self):
        data = _make_featured_data()
        s = RSIMeanReversion()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        # Buy signals should correspond to low RSI periods
        buys = signals[signals["signal"] == 1]
        if len(buys) > 0:
            rsi_at_buy = data.loc[buys.index, "RSI"]
            assert rsi_at_buy.max() <= 30  # all buys when RSI < 30


class TestMomentumBreakout:
    def test_default_params(self):
        s = MomentumBreakout()
        assert s.params["lookback"] == 20

    def test_invalid_lookback(self):
        with pytest.raises(ValueError):
            MomentumBreakout({"lookback": 2})

    def test_generates_signals(self):
        data = _make_featured_data()
        s = MomentumBreakout()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns

    def test_stop_loss_set_on_buy(self):
        data = _make_featured_data()
        s = MomentumBreakout()
        signals = s.generate_signals(data)
        buys = signals[signals["signal"] == 1]
        if len(buys) > 0:
            assert buys["stop_loss"].notna().all()


class TestSignalQuality:
    def test_quality_assessment(self):
        data = _make_featured_data()
        s = MovingAverageCrossover()
        signals = s.generate_signals(data)
        quality = s.calculate_signal_quality(signals)
        assert "total_signals" in quality
        assert quality["quality"] in ("good", "overtrading", "too_few", "no_signals")
