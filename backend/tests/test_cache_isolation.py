"""Tests must never write into the app's real price cache (B1, Nov 2026
audit: stubbed-price app tests stored synthetic frames under real keys)."""

from alphalab.api.routes import create_app
from alphalab.data.cache_manager import CacheManager


def test_default_cache_manager_is_redirected_during_tests(
    tmp_path, monkeypatch, _isolate_real_price_cache
):
    monkeypatch.chdir(tmp_path)
    assert CacheManager().cache_dir == _isolate_real_price_cache
    assert not (tmp_path / "data" / "cache").exists()


def test_app_fetcher_does_not_use_the_real_cache(
    tmp_path, monkeypatch, _isolate_real_price_cache
):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    fetcher = app.extensions["fetcher"]
    assert fetcher.cache.cache_dir == _isolate_real_price_cache
    assert not (tmp_path / "data" / "cache").exists()


def test_explicit_cache_dir_is_respected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "data" / "cache"
    cm = CacheManager(cache_dir=str(cache_dir))
    assert cm.cache_dir == cache_dir
