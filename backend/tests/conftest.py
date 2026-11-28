"""Shared pytest fixtures for AlphaLab backend tests."""

import sys
import os
from pathlib import Path

import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from helpers import make_featured_data
from alphalab.data import cache_manager as _cache_manager

# Stubbed prices must stay out of the app cache at either checkout entry
# point, even if a test passes one of those directories as an absolute path.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_PRICE_CACHE = Path("data/cache")
_CHECKOUT_PRICE_CACHES = {
    (directory / _DEFAULT_PRICE_CACHE).resolve()
    for directory in (_BACKEND_DIR, _BACKEND_DIR.parent)
}


@pytest.fixture(autouse=True, scope="session")
def _isolate_real_price_cache(tmp_path_factory):
    """Redirect app cache paths to a per-session temp dir."""
    isolated = tmp_path_factory.mktemp("price_cache")
    original_init = _cache_manager.CacheManager.__init__

    def _init(self, cache_dir="data/cache", expiry_hours=24):
        path = Path(cache_dir)
        if path == _DEFAULT_PRICE_CACHE or path.resolve() in _CHECKOUT_PRICE_CACHES:
            cache_dir = str(isolated)
        original_init(self, cache_dir, expiry_hours)

    _cache_manager.CacheManager.__init__ = _init
    yield isolated
    _cache_manager.CacheManager.__init__ = original_init


@pytest.fixture
def featured_data() -> pd.DataFrame:
    """500-bar synthetic OHLCV DataFrame with all indicators (seed=42)."""
    return make_featured_data()
