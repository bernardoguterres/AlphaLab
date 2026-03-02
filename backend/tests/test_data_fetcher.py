"""Tests for DataFetcher."""

import shutil
import sys
import os
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.fetcher import DataFetcher, DataFetchError, InvalidTickerError, InsufficientDataError


def _mock_download(n=200):
    """Create a mock yfinance download result."""
    dates = pd.bdate_range("2023-01-01", periods=n)
    rng = np.random.RandomState(42)
    close = 150 + rng.randn(n).cumsum() * 0.5
    close = np.maximum(close, 50)
    high = close + rng.uniform(0, 3, n)
    low = close - rng.uniform(0, 3, n)
    opn = close + rng.uniform(-1, 1, n)
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.randint(10_000_000, 100_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


# Patch time.sleep globally for all tests in this module to avoid retry delays
@pytest.fixture(autouse=True)
def no_sleep():
    with patch("src.data.fetcher.time.sleep"):
        yield


@pytest.fixture(autouse=True)
def clean_cache(tmp_path):
    """Provide a unique tmp cache dir per test via tmp_path."""
    yield tmp_path


class TestDataFetcher:
    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_fetch_returns_data(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.return_value = _mock_download()

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        result = fetcher.fetch("AAPL", "2023-01-01", "2023-12-31")

        assert result["ticker"] == "AAPL"
        assert len(result["data"]) > 0
        assert "metadata" in result
        assert result["metadata"]["records"] > 0

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_fetch_quality_score(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.return_value = _mock_download()

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        result = fetcher.fetch("AAPL", "2023-01-01", "2023-12-31")

        assert 0 <= result["metadata"]["quality_score"] <= 1

    @patch("src.data.fetcher.yf.Ticker")
    def test_invalid_ticker(self, mock_ticker, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": None}

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        with pytest.raises(InvalidTickerError):
            fetcher.fetch("XYZXYZ", "2023-01-01", "2023-12-31")

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_insufficient_data(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.return_value = _mock_download(n=3)

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        with pytest.raises(InsufficientDataError):
            fetcher.fetch("AAPL", "2023-01-01", "2023-01-05")

    def test_invalid_interval(self, tmp_path):
        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        with pytest.raises(ValueError, match="Invalid interval"):
            fetcher.fetch("AAPL", "2023-01-01", "2023-12-31", interval="5m")

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_cache_hit(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.return_value = _mock_download()

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        result1 = fetcher.fetch("AAPL", "2023-01-01", "2023-12-31")
        assert not result1["metadata"]["from_cache"]

        result2 = fetcher.fetch("AAPL", "2023-01-01", "2023-12-31")
        assert result2["metadata"]["from_cache"]
        assert mock_download.call_count == 1

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_retry_on_failure(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            _mock_download(),
        ]

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"), max_retries=3)
        result = fetcher.fetch("AAPL", "2023-01-01", "2023-12-31")
        assert len(result["data"]) > 0
        assert mock_download.call_count == 3

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_all_retries_fail(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.side_effect = Exception("Persistent failure")

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"), max_retries=2)
        with pytest.raises(DataFetchError, match="Failed to download"):
            fetcher.fetch("AAPL", "2023-01-01", "2023-12-31")

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_fetch_multiple(self, mock_ticker, mock_download, tmp_path):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_download.return_value = _mock_download()

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        results = fetcher.fetch_multiple(["AAPL", "MSFT"], "2023-01-01", "2023-12-31")
        assert "AAPL" in results
        assert "MSFT" in results

    @patch("src.data.fetcher.yf.Ticker")
    def test_fetch_company_info(self, mock_ticker, tmp_path):
        mock_ticker.return_value.info = {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3000000000000,
            "currency": "USD",
            "exchange": "NMS",
            "regularMarketPrice": 150.0,
        }

        fetcher = DataFetcher(cache_dir=str(tmp_path / "cache"))
        info = fetcher.fetch_company_info("AAPL")
        assert info["name"] == "Apple Inc."
        assert info["sector"] == "Technology"
