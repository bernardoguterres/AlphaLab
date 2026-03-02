"""Cache manager for storing and retrieving downloaded market data."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.cache")


class CacheManager:
    """Manages local file-based caching of market data to avoid redundant API calls."""

    def __init__(self, cache_dir: str = "data/cache", expiry_hours: float = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_seconds = expiry_hours * 3600
        self._meta_path = self.cache_dir / "_meta.json"
        self._meta = self._load_meta()

    def _load_meta(self) -> dict:
        if self._meta_path.exists():
            with open(self._meta_path) as f:
                return json.load(f)
        return {}

    def _save_meta(self):
        with open(self._meta_path, "w") as f:
            json.dump(self._meta, f, indent=2)

    @staticmethod
    def _cache_key(ticker: str, interval: str, start: str, end: str) -> str:
        raw = f"{ticker}_{interval}_{start}_{end}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(
        self, ticker: str, interval: str, start: str, end: str
    ) -> Optional[pd.DataFrame]:
        """Retrieve cached data if it exists and hasn't expired."""
        key = self._cache_key(ticker, interval, start, end)
        entry = self._meta.get(key)
        if entry is None:
            return None

        age = time.time() - entry["timestamp"]
        if age > self.expiry_seconds:
            logger.debug("Cache expired for %s (age=%.0fs)", ticker, age)
            self.invalidate(ticker, interval, start, end)
            return None

        path = self.cache_dir / f"{key}.parquet"
        if not path.exists():
            return None

        logger.debug("Cache hit for %s", ticker)
        return pd.read_parquet(path)

    def put(
        self,
        ticker: str,
        interval: str,
        start: str,
        end: str,
        data: pd.DataFrame,
    ):
        """Store data in cache with current timestamp."""
        key = self._cache_key(ticker, interval, start, end)
        path = self.cache_dir / f"{key}.parquet"
        data.to_parquet(path)
        self._meta[key] = {
            "ticker": ticker,
            "interval": interval,
            "start": start,
            "end": end,
            "timestamp": time.time(),
            "records": len(data),
        }
        self._save_meta()
        logger.debug("Cached %d records for %s", len(data), ticker)

    def invalidate(self, ticker: str, interval: str, start: str, end: str):
        """Remove a specific cache entry."""
        key = self._cache_key(ticker, interval, start, end)
        path = self.cache_dir / f"{key}.parquet"
        if path.exists():
            path.unlink()
        self._meta.pop(key, None)
        self._save_meta()

    def list_cached(self) -> list[dict]:
        """Return metadata for all cached entries."""
        return [
            {**v, "key": k}
            for k, v in self._meta.items()
            if (self.cache_dir / f"{k}.parquet").exists()
        ]

    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.time()
        expired = [
            k
            for k, v in self._meta.items()
            if now - v["timestamp"] > self.expiry_seconds
        ]
        for key in expired:
            path = self.cache_dir / f"{key}.parquet"
            if path.exists():
                path.unlink()
            del self._meta[key]
        if expired:
            self._save_meta()
            logger.info("Cleared %d expired cache entries", len(expired))
        return len(expired)
