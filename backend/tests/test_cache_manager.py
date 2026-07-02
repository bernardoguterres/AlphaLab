"""Tests for the file-based CacheManager."""

import json
import time

import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.cache_manager import CacheManager


def _sample_df():
    dates = pd.bdate_range("2022-01-01", periods=5)
    return pd.DataFrame(
        {
            "Open": [1.0, 2, 3, 4, 5],
            "High": [1.5, 2.5, 3.5, 4.5, 5.5],
            "Low": [0.5, 1.5, 2.5, 3.5, 4.5],
            "Close": [1.2, 2.2, 3.2, 4.2, 5.2],
            "Volume": [100, 200, 300, 400, 500],
        },
        index=dates,
    )


class TestCacheManagerBasics:
    def test_creates_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "cache"
        CacheManager(cache_dir=str(cache_dir))
        assert cache_dir.exists()

    def test_get_returns_none_when_no_entry(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        assert cm.get("AAPL", "1d", "2022-01-01", "2022-06-01") is None

    def test_put_then_get_roundtrip(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)

        loaded = cm.get("AAPL", "1d", "2022-01-01", "2022-06-01")
        assert loaded is not None
        assert len(loaded) == len(df)
        pd.testing.assert_frame_equal(loaded, df, check_freq=False)

    def test_different_keys_do_not_collide(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)
        # Different ticker -> should not be found
        assert cm.get("MSFT", "1d", "2022-01-01", "2022-06-01") is None
        # Different interval -> should not be found
        assert cm.get("AAPL", "1wk", "2022-01-01", "2022-06-01") is None


class TestCacheManagerExpiry:
    def test_expired_entry_returns_none_and_invalidates(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"), expiry_hours=1e-9)
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)
        time.sleep(0.01)  # ensure age exceeds the tiny expiry window

        assert cm.get("AAPL", "1d", "2022-01-01", "2022-06-01") is None
        # Entry should have been removed from metadata by invalidate()
        assert cm.list_cached() == []

    def test_clear_expired_removes_only_expired(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"), expiry_hours=24)
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)

        # Manually age the entry past expiry.
        key = cm._cache_key("AAPL", "1d", "2022-01-01", "2022-06-01")
        cm._meta[key]["timestamp"] = time.time() - 999999
        cm._save_meta()

        # Add a fresh entry that should NOT be cleared.
        cm.put("MSFT", "1d", "2022-01-01", "2022-06-01", df)

        removed = cm.clear_expired()
        assert removed == 1
        cached = cm.list_cached()
        assert len(cached) == 1
        assert cached[0]["ticker"] == "MSFT"


class TestCacheManagerInvalidateAndList(object):
    def test_invalidate_removes_file_and_metadata(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)
        key = cm._cache_key("AAPL", "1d", "2022-01-01", "2022-06-01")
        path = cm.cache_dir / f"{key}.parquet"
        assert path.exists()

        cm.invalidate("AAPL", "1d", "2022-01-01", "2022-06-01")
        assert not path.exists()
        assert cm.get("AAPL", "1d", "2022-01-01", "2022-06-01") is None

    def test_invalidate_nonexistent_entry_is_noop(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        # Should not raise even though nothing was ever cached.
        cm.invalidate("NOPE", "1d", "2022-01-01", "2022-06-01")

    def test_list_cached_excludes_entries_missing_parquet_file(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)
        key = cm._cache_key("AAPL", "1d", "2022-01-01", "2022-06-01")
        # Delete the parquet file directly, leaving stale metadata behind.
        (cm.cache_dir / f"{key}.parquet").unlink()

        assert cm.list_cached() == []

    def test_get_returns_none_when_parquet_missing_but_meta_present(self, tmp_path):
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        df = _sample_df()
        cm.put("AAPL", "1d", "2022-01-01", "2022-06-01", df)
        key = cm._cache_key("AAPL", "1d", "2022-01-01", "2022-06-01")
        (cm.cache_dir / f"{key}.parquet").unlink()

        assert cm.get("AAPL", "1d", "2022-01-01", "2022-06-01") is None


class TestCacheManagerCorruptMeta:
    def test_corrupt_meta_file_is_quarantined_and_ignored(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True)
        meta_path = cache_dir / "_meta.json"
        meta_path.write_text("{not valid json")

        cm = CacheManager(cache_dir=str(cache_dir))

        # Corrupt file should have been renamed, not left in place.
        assert not meta_path.exists()
        assert (cache_dir / "_meta.json.corrupt").exists()
        # And the manager should start with an empty cache instead of crashing.
        assert cm.list_cached() == []
