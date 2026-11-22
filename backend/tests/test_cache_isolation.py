"""Tests must never write into the app's real price cache (B1, Nov 2026
audit: stubbed-price app tests stored synthetic frames under real keys)."""

from pathlib import Path

from alphalab.api.routes import create_app
from alphalab.data.cache_manager import CacheManager
from conftest import REAL_PRICE_CACHE


def test_default_cache_manager_is_redirected_during_tests():
    cm = CacheManager()  # default "data/cache"
    assert Path(cm.cache_dir).resolve() != REAL_PRICE_CACHE


def test_app_fetcher_does_not_use_the_real_cache():
    app = create_app()
    fetcher = app.extensions["fetcher"]
    assert Path(fetcher.cache.cache_dir).resolve() != REAL_PRICE_CACHE


def test_explicit_cache_dir_is_respected(tmp_path):
    cm = CacheManager(cache_dir=str(tmp_path / "mine"))
    assert Path(cm.cache_dir) == tmp_path / "mine"
