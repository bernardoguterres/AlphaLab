"""Tests for FeatureEngineer (processor.py)."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.processor import FeatureEngineer


def _make_ohlcv(n=300, seed=42):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2022-01-01", periods=n)
    close = 100 + rng.randn(n).cumsum() * 0.5
    close = np.maximum(close, 10)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    opn = close + rng.uniform(-1, 1, n)
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.randint(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


class TestFeatureEngineer:
    def test_process_returns_all_columns(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        # Check some expected columns
        for col in ["SMA_20", "EMA_12", "MACD", "RSI", "ATR", "OBV", "Return"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_rsi_bounded(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        rsi = result["RSI"].dropna()
        assert rsi.min() >= 0
        assert rsi.max() <= 100

    def test_sma_accuracy(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        # Manual SMA20 check on last row
        expected = df["Close"].iloc[-20:].mean()
        actual = result["SMA_20"].iloc[-1]
        assert abs(actual - expected) < 0.01

    def test_bollinger_bands_relationship(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        valid = result.dropna(subset=["BB_Upper", "BB_Lower", "BB_Middle"])
        assert (valid["BB_Upper"] >= valid["BB_Middle"]).all()
        assert (valid["BB_Middle"] >= valid["BB_Lower"]).all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"Close": [1, 2, 3]})
        fe = FeatureEngineer()
        with pytest.raises(ValueError, match="Missing required columns"):
            fe.process(df)

    def test_short_data_warns(self):
        df = _make_ohlcv(n=20)
        fe = FeatureEngineer()
        result = fe.process(df)
        # Should still produce a DataFrame, just with many NaNs
        assert len(result) == 20

    def test_gap_analysis(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        assert "Gap" in result.columns
        assert "Gap_Pct" in result.columns

    def test_pivot_points(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        valid = result.dropna(subset=["Pivot"])
        # Pivot = (H+L+C)/3 of previous day
        row = valid.iloc[-1]
        prev = df.iloc[-2]
        expected = (prev["High"] + prev["Low"] + prev["Close"]) / 3
        assert abs(row["Pivot"] - expected) < 0.01
