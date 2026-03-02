"""Integration tests for the Flask API."""

import json
import sys
import os
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import create_app


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("src.data.fetcher.time.sleep"):
        yield


def _mock_download(n=300):
    dates = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.RandomState(42)
    close = 100 + rng.randn(n).cumsum() * 0.3
    close = np.maximum(close, 10)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    opn = close + rng.uniform(-0.5, 0.5, n)
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.randint(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "version" in data


class TestDataEndpoints:
    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_fetch_data(self, mock_ticker, mock_dl, client):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_dl.return_value = _mock_download()

        resp = client.post("/api/data/fetch", json={
            "tickers": ["AAPL"],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "AAPL" in data["data"]

    def test_fetch_invalid_ticker_format(self, client):
        resp = client.post("/api/data/fetch", json={
            "tickers": ["invalid_ticker_123"],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 422

    def test_fetch_invalid_date(self, client):
        resp = client.post("/api/data/fetch", json={
            "tickers": ["AAPL"],
            "start_date": "not-a-date",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 422

    def test_fetch_no_tickers(self, client):
        resp = client.post("/api/data/fetch", json={
            "tickers": [],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 422

    def test_fetch_too_many_tickers(self, client):
        resp = client.post("/api/data/fetch", json={
            "tickers": [f"T{i}" for i in range(21)],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 422

    def test_available_data(self, client):
        resp = client.get("/api/data/available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestBacktestEndpoints:
    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_run_backtest(self, mock_ticker, mock_dl, client):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_dl.return_value = _mock_download(500)

        resp = client.post("/api/strategies/backtest", json={
            "ticker": "AAPL",
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "params": {"short_window": 20, "long_window": 50},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "backtest_id" in data["data"]
        assert "metrics" in data["data"]
        assert data["data"]["final_value"] > 0

    def test_backtest_invalid_strategy(self, client):
        resp = client.post("/api/strategies/backtest", json={
            "ticker": "AAPL",
            "strategy": "nonexistent",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 422

    def test_backtest_low_capital(self, client):
        resp = client.post("/api/strategies/backtest", json={
            "ticker": "AAPL",
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 10,
        })
        assert resp.status_code == 422

    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_get_metrics_after_backtest(self, mock_ticker, mock_dl, client):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_dl.return_value = _mock_download(500)

        # Run backtest first
        resp = client.post("/api/strategies/backtest", json={
            "ticker": "AAPL",
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
            "params": {"short_window": 20, "long_window": 50},
        })
        bt_id = resp.get_json()["data"]["backtest_id"]

        # Retrieve metrics
        resp2 = client.get(f"/api/metrics/{bt_id}")
        assert resp2.status_code == 200

    def test_get_metrics_not_found(self, client):
        resp = client.get("/api/metrics/nonexistent")
        assert resp.status_code == 404


class TestCompareEndpoint:
    @patch("src.data.fetcher.yf.download")
    @patch("src.data.fetcher.yf.Ticker")
    def test_compare_strategies(self, mock_ticker, mock_dl, client):
        mock_ticker.return_value.info = {"regularMarketPrice": 150.0}
        mock_dl.return_value = _mock_download(500)

        resp = client.post("/api/compare", json={
            "ticker": "AAPL",
            "strategies": ["ma_crossover", "rsi_mean_reversion"],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ma_crossover" in data["data"]
        assert "rsi_mean_reversion" in data["data"]

    def test_compare_too_few_strategies(self, client):
        resp = client.post("/api/compare", json={
            "ticker": "AAPL",
            "strategies": ["ma_crossover"],
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert resp.status_code == 422


class TestNotFound:
    def test_404(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["status"] == "error"
