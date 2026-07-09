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
        for col in ["SMA_20", "RSI", "ATR", "ADX", "BB_Upper"]:
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

    def test_no_unused_indicators(self):
        df = _make_ohlcv()
        fe = FeatureEngineer()
        result = fe.process(df)
        removed = [
            "Pivot", "Pivot_R1", "Pivot_S1", "Fib_0.236", "PSAR",
            "EMA_12", "EMA_26", "EMA_50", "EMA_200",
            "MACD", "MACD_Signal", "MACD_Hist",
            "Stoch_K", "Stoch_D", "Williams_R", "ROC_10", "CMO",
            "BB_Width", "HV_30", "HV_60", "HV_90",
            "Keltner_Upper", "Keltner_Lower",
            "OBV", "VWMA_10", "VWMA_20", "MFI", "AD", "Volume_SMA_20",
            "Return", "Log_Return", "Return_Mean_20", "Return_Std_20",
            "Return_Mean_60", "Return_Std_60", "Skew_30", "Kurt_30",
            "Benchmark_Return", "Beta_60", "Corr_60",
            "Resistance", "Support", "Gap", "Gap_Pct",
        ]
        for col in removed:
            assert col not in result.columns, f"{col} should have been removed"
