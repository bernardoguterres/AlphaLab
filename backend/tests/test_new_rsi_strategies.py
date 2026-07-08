"""Tests for RSISimple, BollingerRSICombo, and TrendAdaptiveRSI strategies."""

import numpy as np
import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategies.implementations.rsi_simple import RSISimple
from src.strategies.implementations.bollinger_rsi_combo import BollingerRSICombo
from src.strategies.implementations.trend_adaptive_rsi import TrendAdaptiveRSI
from helpers import make_featured_data as _make_featured_data


class TestRSISimple:
    def test_default_params(self):
        s = RSISimple()
        assert s.params["period"] == 14
        assert s.params["oversold"] == 40
        assert s.params["overbought"] == 60

    def test_invalid_bounds(self):
        with pytest.raises(ValueError):
            RSISimple({"oversold": 70, "overbought": 20})

    def test_required_columns(self):
        s = RSISimple()
        cols = s.required_columns()
        assert cols == ["Close", "RSI"]

    def test_generates_signals(self):
        data = _make_featured_data()
        s = RSISimple()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        assert set(signals["signal"].unique()).issubset({-1, 0, 1})

    def test_buy_signal_only_when_rsi_below_oversold(self):
        # Build a tiny synthetic frame so we control RSI exactly.
        idx = pd.date_range("2022-01-01", periods=5)
        data = pd.DataFrame({"Close": [10, 10, 10, 10, 10]}, index=idx)
        data["RSI"] = [50, 35, np.nan, 65, 45]
        s = RSISimple({"oversold": 40, "overbought": 60})
        signals = s.generate_signals(data)

        assert signals["signal"].iloc[0] == 0  # RSI 50 -> hold
        assert signals["signal"].iloc[1] == 1  # RSI 35 < 40 -> buy
        assert signals["signal"].iloc[2] == 0  # NaN -> skipped/hold
        assert signals["signal"].iloc[3] == -1  # RSI 65 > 60 -> sell
        assert signals["signal"].iloc[4] == 0  # RSI 45 -> hold

    def test_confidence_increases_with_distance_from_threshold(self):
        idx = pd.date_range("2022-01-01", periods=2)
        data = pd.DataFrame({"Close": [10, 10]}, index=idx)
        data["RSI"] = [39, 10]  # both oversold, second one more extreme
        s = RSISimple({"oversold": 40, "overbought": 60})
        signals = s.generate_signals(data)
        assert signals["confidence"].iloc[1] > signals["confidence"].iloc[0]

    def test_reason_populated_on_signal(self):
        idx = pd.date_range("2022-01-01", periods=1)
        data = pd.DataFrame({"Close": [10]}, index=idx)
        data["RSI"] = [20]
        s = RSISimple()
        signals = s.generate_signals(data)
        assert "oversold" in signals["reason"].iloc[0]

    def test_empty_dataframe_does_not_crash(self):
        data = pd.DataFrame({"Close": [], "RSI": []})
        s = RSISimple()
        signals = s.generate_signals(data)
        assert len(signals) == 0


class TestBollingerRSICombo:
    def test_default_params(self):
        s = BollingerRSICombo()
        assert s.params["bb_period"] == 20
        assert s.params["rsi_oversold"] == 45
        assert s.params["rsi_overbought"] == 55
        assert s.params["exit_at_middle"] is True

    def test_invalid_bounds(self):
        with pytest.raises(ValueError):
            BollingerRSICombo({"rsi_oversold": 80, "rsi_overbought": 20})

    def test_required_columns(self):
        s = BollingerRSICombo()
        cols = s.required_columns()
        assert set(cols) == {"Close", "BB_Lower", "BB_Middle", "BB_Upper", "RSI"}

    def test_generates_signals_on_featured_data(self):
        data = _make_featured_data()
        s = BollingerRSICombo()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        assert set(signals["signal"].unique()).issubset({-1, 0, 1})

    def test_entry_on_bb_touch_and_rsi_oversold(self):
        idx = pd.date_range("2022-01-01", periods=3)
        data = pd.DataFrame(
            {
                "Close": [10, 8, 8],
                "BB_Lower": [9, 9, 9],
                "BB_Middle": [10, 10, 10],
                "BB_Upper": [11, 11, 11],
                "RSI": [50, 30, 30],
            },
            index=idx,
        )
        s = BollingerRSICombo()
        signals = s.generate_signals(data)
        # Bar 0: close 10 > BB_Lower 9, no entry
        assert signals["signal"].iloc[0] == 0
        # Bar 1: close 8 <= BB_Lower 9 and RSI 30 < 45 -> buy
        assert signals["signal"].iloc[1] == 1

    def test_exit_at_middle_band(self):
        idx = pd.date_range("2022-01-01", periods=3)
        data = pd.DataFrame(
            {
                "Close": [10, 8, 10],
                "BB_Lower": [9, 9, 9],
                "BB_Middle": [10, 10, 10],
                "BB_Upper": [11, 11, 11],
                "RSI": [50, 30, 50],
            },
            index=idx,
        )
        s = BollingerRSICombo({"exit_at_middle": True})
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[1] == 1  # entry
        assert signals["signal"].iloc[2] == -1  # exit at middle band reached

    def test_exit_on_rsi_overbought(self):
        idx = pd.date_range("2022-01-01", periods=3)
        data = pd.DataFrame(
            {
                "Close": [12, 8, 8.5],
                "BB_Lower": [9, 9, 9],
                "BB_Middle": [12, 12, 12],
                "BB_Upper": [13, 13, 13],
                "RSI": [50, 30, 60],
            },
            index=idx,
        )
        s = BollingerRSICombo({"exit_at_middle": True})
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[1] == 1
        # Price still below middle band, but RSI overbought triggers exit
        assert signals["signal"].iloc[2] == -1

    def test_nan_rows_skipped(self):
        idx = pd.date_range("2022-01-01", periods=2)
        data = pd.DataFrame(
            {
                "Close": [np.nan, 8],
                "BB_Lower": [9, 9],
                "BB_Middle": [10, 10],
                "BB_Upper": [11, 11],
                "RSI": [30, 30],
            },
            index=idx,
        )
        s = BollingerRSICombo()
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[0] == 0


class TestTrendAdaptiveRSI:
    def test_default_params(self):
        s = TrendAdaptiveRSI()
        assert s.params["trend_sma"] == 50
        assert s.params["uptrend_buy"] == 45
        assert s.params["downtrend_sell"] == 55

    def test_required_columns_uses_trend_sma_param(self):
        s = TrendAdaptiveRSI({"trend_sma": 50})
        cols = s.required_columns()
        assert "SMA_50" in cols
        assert "Close" in cols
        assert "RSI" in cols

    def test_generates_signals_on_featured_data(self):
        data = _make_featured_data()
        s = TrendAdaptiveRSI()
        signals = s.generate_signals(data)
        assert "signal" in signals.columns
        assert set(signals["signal"].unique()).issubset({-1, 0, 1})

    def test_missing_sma_column_returns_flat_signals(self):
        idx = pd.date_range("2022-01-01", periods=10)
        data = pd.DataFrame({"Close": np.full(10, 10.0)}, index=idx)
        data["RSI"] = 50.0
        s = TrendAdaptiveRSI({"trend_sma": 50})
        signals = s.generate_signals(data)
        assert (signals["signal"] == 0).all()

    def test_uptrend_buys_dip_above_range_threshold(self):
        # Construct a clear uptrend: SMA rising >0.5% over lookback, price above SMA.
        n = 20
        idx = pd.date_range("2022-01-01", periods=n)
        sma = np.linspace(100, 110, n)  # rising sma, >0.5% over 5-bar lookback
        close = sma + 1  # price above sma -> uptrend
        rsi = np.full(n, 50.0)
        rsi[10] = 44  # below uptrend_buy=45 but above range_buy=35
        data = pd.DataFrame({"Close": close, "RSI": rsi, "SMA_50": sma}, index=idx)
        s = TrendAdaptiveRSI({"trend_sma": 50, "trend_lookback": 5})
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[10] == 1
        assert "uptrend" in signals["reason"].iloc[10]

    def test_downtrend_sells_rip_at_lower_threshold(self):
        n = 20
        idx = pd.date_range("2022-01-01", periods=n)
        sma = np.linspace(110, 100, n)  # falling sma -> downtrend
        close = sma - 1  # price below sma
        rsi = np.full(n, 50.0)
        rsi[5] = 30  # entry: below downtrend_buy=35
        rsi[10] = 56  # exit: above downtrend_sell=55
        data = pd.DataFrame({"Close": close, "RSI": rsi, "SMA_50": sma}, index=idx)
        s = TrendAdaptiveRSI({"trend_sma": 50, "trend_lookback": 5})
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[5] == 1
        assert signals["signal"].iloc[10] == -1
        assert "downtrend" in signals["reason"].iloc[5]

    def test_range_regime_uses_standard_thresholds(self):
        n = 20
        idx = pd.date_range("2022-01-01", periods=n)
        sma = np.full(n, 100.0)  # flat sma -> range regime
        close = sma.copy()
        rsi = np.full(n, 50.0)
        rsi[8] = 30  # below range_buy=35
        data = pd.DataFrame({"Close": close, "RSI": rsi, "SMA_50": sma}, index=idx)
        s = TrendAdaptiveRSI({"trend_sma": 50, "trend_lookback": 5})
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[8] == 1
        assert "range" in signals["reason"].iloc[8]

    def test_nan_rows_are_skipped(self):
        n = 10
        idx = pd.date_range("2022-01-01", periods=n)
        sma = np.full(n, 100.0)
        close = np.full(n, 100.0)
        close[6] = np.nan
        rsi = np.full(n, 50.0)
        data = pd.DataFrame({"Close": close, "RSI": rsi, "SMA_50": sma}, index=idx)
        s = TrendAdaptiveRSI({"trend_sma": 50, "trend_lookback": 5})
        signals = s.generate_signals(data)
        assert signals["signal"].iloc[6] == 0
