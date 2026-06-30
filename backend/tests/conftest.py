"""Shared pytest fixtures for AlphaLab backend tests."""

import sys
import os

import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_featured_data


@pytest.fixture
def featured_data() -> pd.DataFrame:
    """500-bar synthetic OHLCV DataFrame with all indicators (seed=42)."""
    return make_featured_data()
