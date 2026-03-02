"""Tests for DataValidator."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.validator import DataValidator, QualityReport


def _make_ohlcv(n=100, seed=42):
    """Create synthetic OHLCV data."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2023-01-01", periods=n)
    close = 100 + rng.randn(n).cumsum()
    close = np.maximum(close, 1)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    opn = close + rng.uniform(-1, 1, n)
    # Ensure OHLC consistency for base data
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.randint(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


class TestDataValidator:
    def test_clean_data_passes(self):
        df = _make_ohlcv()
        v = DataValidator()
        cleaned, report = v.validate_and_clean(df, "TEST")
        assert report.is_acceptable
        assert report.confidence > 0.9
        assert len(cleaned) > 0

    def test_empty_dataframe(self):
        v = DataValidator()
        cleaned, report = v.validate_and_clean(pd.DataFrame(), "EMPTY")
        assert not report.is_acceptable
        assert report.confidence == 0.0

    def test_duplicate_removal(self):
        df = _make_ohlcv(50)
        df = pd.concat([df, df.iloc[:5]])  # duplicate 5 rows
        v = DataValidator()
        cleaned, report = v.validate_and_clean(df, "DUP")
        assert report.duplicates_removed == 5
        # After dedup we have 50 rows, but outlier removal may reduce further
        assert len(cleaned) <= 50
        assert len(cleaned) >= 45

    def test_ohlc_consistency_fix(self):
        df = _make_ohlcv(50)
        # Break consistency: High < Close
        df.iloc[10, df.columns.get_loc("High")] = df.iloc[10]["Close"] - 5
        v = DataValidator()
        cleaned, report = v.validate_and_clean(df, "BAD_OHLC")
        # Should be corrected
        assert cleaned.iloc[10]["High"] >= max(
            cleaned.iloc[10]["Open"], cleaned.iloc[10]["Close"]
        )

    def test_negative_volume_set_to_zero(self):
        df = _make_ohlcv(50)
        df.iloc[5, df.columns.get_loc("Volume")] = -100
        v = DataValidator()
        cleaned, report = v.validate_and_clean(df, "NEG_VOL")
        assert (cleaned["Volume"] >= 0).all()

    def test_outlier_detection(self):
        df = _make_ohlcv(200)
        # Inject extreme return
        df.iloc[100, df.columns.get_loc("Close")] = df.iloc[99]["Close"] * 5
        v = DataValidator(iqr_factor=2.0)
        cleaned, report = v.validate_and_clean(df, "OUTLIER")
        assert report.outliers_removed >= 1

    def test_missing_data_imputation(self):
        df = _make_ohlcv(100)
        df.iloc[20:22, df.columns.get_loc("Close")] = np.nan  # 2-day gap
        v = DataValidator(max_ffill_gap=3)
        cleaned, report = v.validate_and_clean(df, "MISS")
        assert report.values_imputed >= 2
        assert cleaned["Close"].isna().sum() == 0

    def test_quality_report_dict(self):
        report = QualityReport(
            completeness=0.95,
            outliers_removed=2,
            confidence=0.88,
            warnings=["test warning"],
        )
        d = report.to_dict()
        assert d["completeness"] == 0.95
        assert d["is_acceptable"] is False  # 0.88 < 0.9
