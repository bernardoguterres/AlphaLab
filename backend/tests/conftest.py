"""Shared pytest fixtures for AlphaLab backend tests."""

import sys
import os
from pathlib import Path

import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_featured_data
from alphalab.data import cache_manager as _cache_manager

# The app's real price cache (config default "data/cache", relative to
# backend/). Tests that build the app or a DataFetcher with stubbed prices
# used to write synthetic frames into it under real keys (e.g. MSFT 1d
# 2020-2024), so a dev server started within the cache expiry backtested
# fake prices labelled as real.
REAL_PRICE_CACHE = (Path(__file__).resolve().parent.parent / "data" / "cache").resolve()


@pytest.fixture(autouse=True, scope="session")
def _isolate_real_price_cache(tmp_path_factory):
    """Redirect any CacheManager that would use the real price cache to a
    per-session temp dir. Tests passing their own cache_dir are untouched."""
    isolated = tmp_path_factory.mktemp("price_cache")
    original_init = _cache_manager.CacheManager.__init__

    def _init(self, cache_dir="data/cache", expiry_hours=24):
        resolved = Path(cache_dir)
        if not resolved.is_absolute():
            resolved = Path.cwd() / resolved
        if resolved.resolve() == REAL_PRICE_CACHE:
            cache_dir = str(isolated)
        original_init(self, cache_dir, expiry_hours)

    _cache_manager.CacheManager.__init__ = _init
    yield isolated
    _cache_manager.CacheManager.__init__ = original_init


@pytest.fixture
def featured_data() -> pd.DataFrame:
    """500-bar synthetic OHLCV DataFrame with all indicators (seed=42)."""
    return make_featured_data()
