"""Tests for batch backtesting endpoint."""

import json
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import create_app


def _mock_fetch_response(ticker):
    """Generate mock fetch response for a ticker."""
    dates = pd.bdate_range("2020-01-01", periods=100)
    data = pd.DataFrame({
        "Open": 100 + np.random.randn(100).cumsum(),
        "High": 105 + np.random.randn(100).cumsum(),
        "Low": 95 + np.random.randn(100).cumsum(),
        "Close": 100 + np.random.randn(100).cumsum(),
        "Volume": np.random.randint(1_000_000, 10_000_000, 100).astype(float),
    }, index=dates)

    return {
        "data": data,
        "from_cache": True,
        "metadata": {
            "ticker": ticker,
            "records": 100,
            "quality_score": 0.95,
            "start_date": "2020-01-01",
            "end_date": "2020-05-15",
        }
    }


class TestBatchBacktest:
    """Tests for POST /api/strategies/batch-backtest endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.app = create_app()
        self.client = self.app.test_client()

    @patch("src.api.routes.DataFetcher")
    def test_valid_batch_request(self, mock_fetcher_cls):
        """Test batch backtest with valid request."""
        # Mock fetcher
        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = lambda ticker, *args, **kwargs: _mock_fetch_response(ticker)

        payload = {
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
            "initial_capital": 100000,
            "params": {"short_window": 10, "long_window": 30}
        }

        response = self.client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"
        assert "results" in data["data"]
        assert "batch_summary" in data["data"]

        # Check results
        results = data["data"]["results"]
        assert len(results) == 3
        assert all("ticker" in r for r in results)
        assert all("sharpe_ratio" in r for r in results)

        # Check results are sorted by Sharpe descending
        sharpe_ratios = [r["sharpe_ratio"] for r in results]
        assert sharpe_ratios == sorted(sharpe_ratios, reverse=True)

        # Check batch summary
        summary = data["data"]["batch_summary"]
        assert summary["total_tickers"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0
        assert "avg_sharpe_ratio" in summary
        assert "best_ticker" in summary
        assert "worst_ticker" in summary
        assert "runtime_seconds" in summary

    def test_empty_tickers(self):
        """Test batch request with no tickers."""
        payload = {
            "tickers": [],
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
        }

        response = self.client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 422
        data = json.loads(response.data)
        assert data["status"] == "error"

    def test_too_many_tickers(self):
        """Test batch request exceeding ticker limit."""
        payload = {
            "tickers": [f"TICK{i}" for i in range(25)],  # 25 tickers (max is 20)
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
        }

        response = self.client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 422
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "20 tickers" in data["message"].lower()

    def test_invalid_strategy(self):
        """Test batch request with invalid strategy name."""
        payload = {
            "tickers": ["AAPL", "MSFT"],
            "strategy": "invalid_strategy",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
        }

        response = self.client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 422
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("src.api.routes.DataFetcher")
    def test_partial_failures(self, mock_fetcher_cls):
        """Test batch where some tickers fail."""
        # Mock fetcher - AAPL succeeds, MSFT fails, GOOGL succeeds
        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher

        def fetch_side_effect(ticker, *args, **kwargs):
            if ticker == "MSFT":
                from src.data.fetcher import DataFetchError
                raise DataFetchError(f"Failed to fetch {ticker}")
            return _mock_fetch_response(ticker)

        mock_fetcher.fetch.side_effect = fetch_side_effect

        payload = {
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
            "initial_capital": 100000,
        }

        response = self.client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"

        # Should have 2 successful results
        results = data["data"]["results"]
        assert len(results) == 2
        assert all(r["ticker"] in ["AAPL", "GOOGL"] for r in results)

        # Should have 1 error
        errors = data["data"]["errors"]
        assert len(errors) == 1
        assert errors[0]["ticker"] == "MSFT"

        # Summary should reflect partial success
        summary = data["data"]["batch_summary"]
        assert summary["total_tickers"] == 3
        assert summary["successful"] == 2
        assert summary["failed"] == 1
