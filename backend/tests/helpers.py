"""Shared test helpers for AlphaLab backend tests."""

import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.processor import FeatureEngineer


def make_featured_data(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data with all indicators pre-computed.

    Args:
        n: Number of bars to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame processed by FeatureEngineer (all indicators present).
    """
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
