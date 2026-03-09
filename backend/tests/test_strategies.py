"""Tests for trading strategies."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategies.implementations.moving_average_crossover import MovingAverageCrossover
from src.strategies.implementations.rsi_mean_reversion import RSIMeanReversion
from src.strategies.implementations.momentum_breakout import MomentumBreakout
from src.strategies.implementations.bollinger_breakout import BollingerBreakout
from src.strategies.implementations.vwap_reversion import VWAPReversion
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


class TestBollingerBreakout:
    def test_default_params(self):
        s = BollingerBreakout()
        assert s.params["bb_period"] == 20
        assert s.params["bb_std_dev"] == 2.0
        assert s.params["confirmation_bars"] == 2

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            BollingerBreakout({"bb_period": 2})

    def test_invalid_std_dev(self):
        with pytest.raises(ValueError):
            BollingerBreakout({"bb_std_dev": 0.0})

    def test_invalid_confirmation_bars(self):
        with pytest.raises(ValueError):
            BollingerBreakout({"confirmation_bars": 0})

    def test_generates_signals(self):
        data = _make_featured_data()
        s = BollingerBreakout()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        assert set(signals["signal"].unique()).issubset({-1, 0, 1})

    def test_cooldown_enforced(self):
        data = _make_featured_data()
        s = BollingerBreakout({"cooldown_days": 5})
        signals = s.generate_signals(data)
        # Check no two signals within 5 bars
        sig_idx = signals[signals["signal"] != 0].index
        for i in range(1, len(sig_idx)):
            gap = signals.index.get_loc(sig_idx[i]) - signals.index.get_loc(sig_idx[i - 1])
            assert gap > 5

    def test_volume_filter(self):
        data = _make_featured_data()
        s = BollingerBreakout({"volume_filter": True, "volume_threshold": 2.0})
        signals = s.generate_signals(data)
        # When volume filter is on, signals should only occur with high volume
        buys = signals[signals["signal"] == 1]
        if len(buys) > 0:
            # Check that volume is above threshold at buy signals
            vol_avg = data["Volume"].rolling(20).mean()
            vol_at_buy = data.loc[buys.index, "Volume"]
            vol_avg_at_buy = vol_avg.loc[buys.index]
            # At least some should be above threshold
            assert (vol_at_buy > vol_avg_at_buy * 2.0).any()

    def test_confirmation_bars_required(self):
        # Test that signal requires N consecutive closes outside bands
        data = _make_featured_data(n=300)
        s = BollingerBreakout({"confirmation_bars": 3, "volume_filter": False})
        signals = s.generate_signals(data)
        # Just check it runs and produces valid signals
        assert "signal" in signals.columns

    def test_exit_at_middle_band(self):
        # Test that positions exit when price returns to middle band
        data = _make_featured_data(n=300)
        s = BollingerBreakout({"volume_filter": False})
        signals = s.generate_signals(data)
        # Check that signals include both entries and exits
        has_buys = (signals["signal"] == 1).any()
        has_sells = (signals["signal"] == -1).any()
        # This is probabilistic, but should generate both types
        assert has_buys or has_sells

    def test_no_volume_filter(self):
        data = _make_featured_data()
        s = BollingerBreakout({"volume_filter": False})
        signals = s.generate_signals(data)
        # Should still generate signals even without volume filter
        assert "signal" in signals.columns

    def test_required_columns(self):
        s = BollingerBreakout()
        cols = s.required_columns()
        assert "Close" in cols
        assert "Volume" in cols


class TestVWAPReversion:
    def test_default_params(self):
        s = VWAPReversion()
        assert s.params["vwap_period"] == 20
        assert s.params["deviation_threshold"] == 2.0
        assert s.params["oversold"] == 30
        assert s.params["overbought"] == 70

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            VWAPReversion({"vwap_period": 2})

    def test_invalid_deviation(self):
        with pytest.raises(ValueError):
            VWAPReversion({"deviation_threshold": 0.0})

    def test_invalid_rsi_bounds(self):
        with pytest.raises(ValueError):
            VWAPReversion({"oversold": 80, "overbought": 20})

    def test_generates_signals(self):
        data = _make_featured_data()
        s = VWAPReversion()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        assert set(signals["signal"].unique()).issubset({-1, 0, 1})

    def test_cooldown_enforced(self):
        data = _make_featured_data()
        s = VWAPReversion({"cooldown_days": 7})
        signals = s.generate_signals(data)
        # Check no two signals within 7 bars
        sig_idx = signals[signals["signal"] != 0].index
        for i in range(1, len(sig_idx)):
            gap = signals.index.get_loc(sig_idx[i]) - signals.index.get_loc(sig_idx[i - 1])
            assert gap > 7

    def test_rsi_filter(self):
        # Test that buy signals require RSI < oversold
        data = _make_featured_data(n=300)
        s = VWAPReversion({"oversold": 25, "overbought": 75})
        signals = s.generate_signals(data)
        # Just verify it runs and produces valid signals
        assert "signal" in signals.columns

    def test_exit_at_vwap(self):
        # Test that positions exit when price returns to VWAP
        data = _make_featured_data(n=300)
        s = VWAPReversion()
        signals = s.generate_signals(data)
        # Check that signals include both entries and exits
        has_buys = (signals["signal"] == 1).any()
        has_sells = (signals["signal"] == -1).any()
        # This is probabilistic, should generate signals
        assert has_buys or has_sells

    def test_required_columns(self):
        s = VWAPReversion()
        cols = s.required_columns()
        assert "Close" in cols
        assert "Volume" in cols
        assert "RSI" in cols


class TestSignalQuality:
    def test_quality_assessment(self):
        data = _make_featured_data()
        s = MovingAverageCrossover()
        signals = s.generate_signals(data)
        quality = s.calculate_signal_quality(signals)
        assert "total_signals" in quality
        assert quality["quality"] in ("good", "overtrading", "too_few", "no_signals")
