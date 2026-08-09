"""Tests for batch backtesting endpoint."""

import json
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alphalab.api.routes import create_app


def _mock_fetch_response(ticker):
    """Generate mock fetch response for a ticker."""
    dates = pd.bdate_range("2020-01-01", periods=100)
    data = pd.DataFrame(
        {
            "Open": 100 + np.random.randn(100).cumsum(),
            "High": 105 + np.random.randn(100).cumsum(),
            "Low": 95 + np.random.randn(100).cumsum(),
            "Close": 100 + np.random.randn(100).cumsum(),
            "Volume": np.random.randint(1_000_000, 10_000_000, 100).astype(float),
        },
        index=dates,
    )

    return {
        "data": data,
        "from_cache": True,
        "metadata": {
            "ticker": ticker,
            "records": 100,
            "quality_score": 0.95,
            "start_date": "2020-01-01",
            "end_date": "2020-05-15",
        },
    }


def _mock_crash_fetch_response(ticker):
    """Deterministic rise-then-decline fixture with small daily noise
    throughout - used to prove a stop-loss actually changes batch-backtest
    exit behavior. Long flat (zero-return) segments make DataValidator's
    IQR outlier check's interquartile range collapse toward zero, flagging
    any real movement elsewhere as an outlier - small noise throughout
    avoids that while keeping the trend fully deterministic."""
    n = 300
    dates = pd.bdate_range("2020-01-01", periods=n)
    flat = np.full(60, 100.0)
    rise = np.linspace(100, 130, 20)
    decline = np.linspace(130, 90, 25)
    tail = np.full(n - 60 - 20 - 25, 90.0)
    trend = np.concatenate([flat, rise, decline, tail])
    rng = np.random.RandomState(42)
    noise = rng.normal(0, 0.15, n)  # small, non-cumulative per-bar noise
    close = trend + noise
    data = pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.001,
            "Low": close * 0.999,
            "Close": close,
            "Volume": np.full(n, 2_000_000.0),
        },
        index=dates,
    )

    return {
        "data": data,
        "from_cache": True,
        "metadata": {
            "ticker": ticker,
            "records": n,
            "quality_score": 0.95,
            "start_date": "2020-01-01",
            "end_date": "2021-03-01",
        },
    }


class TestBatchBacktest:
    """Tests for POST /api/strategies/batch-backtest endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.app = create_app()
        self.client = self.app.test_client()

    @patch("alphalab.api.routes.DataFetcher")
    def test_valid_batch_request(self, mock_fetcher_cls):
        """Test batch backtest with valid request."""
        # Create app inside patch so the shared fetcher instance is the mock
        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = (
            lambda ticker, *args, **kwargs: _mock_fetch_response(ticker)
        )
        client = create_app().test_client()

        payload = {
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
            "initial_capital": 100000,
            "params": {"short_window": 10, "long_window": 30},
        }

        response = client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json",
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
            content_type="application/json",
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
            content_type="application/json",
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
            content_type="application/json",
        )

        assert response.status_code == 422
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("alphalab.api.routes.DataFetcher")
    def test_partial_failures(self, mock_fetcher_cls):
        """Test batch where some tickers fail."""
        # Create app inside patch so the shared fetcher instance is the mock
        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher

        def fetch_side_effect(ticker, *args, **kwargs):
            if ticker == "MSFT":
                from alphalab.data.fetcher import DataFetchError

                raise DataFetchError(f"Failed to fetch {ticker}")
            return _mock_fetch_response(ticker)

        mock_fetcher.fetch.side_effect = fetch_side_effect
        client = create_app().test_client()

        payload = {
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2020-05-01",
            "initial_capital": 100000,
        }

        response = client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(payload),
            content_type="application/json",
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

    @patch("alphalab.api.routes.DataFetcher")
    def test_risk_settings_applied_to_batch_trades(self, mock_fetcher_cls):
        """batch_backtest() previously validated body.risk_settings but never
        passed it to engine.run_backtest() - stop-loss/take-profit/trailing-
        stop/max-position-size were silently ignored for every batch run,
        even though the frontend's BatchBacktest.tsx sends risk_settings on
        every request. A tight stop-loss during the fixture's post-peak
        crash must now visibly cap the max drawdown reported in the
        batch results, compared to the same run without it."""
        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = (
            lambda ticker, *args, **kwargs: _mock_crash_fetch_response(ticker)
        )
        client = create_app().test_client()

        base_payload = {
            "tickers": ["AAPL"],
            "strategy": "ma_crossover",
            "start_date": "2020-01-01",
            "end_date": "2021-03-01",
            "initial_capital": 100000,
            "params": {
                "short_window": 5,
                "long_window": 50,
                "volume_confirmation": False,
            },
        }

        response_without = client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps(base_payload),
            content_type="application/json",
        )
        drawdown_without = json.loads(response_without.data)["data"]["results"][0][
            "max_drawdown_pct"
        ]

        response_with = client.post(
            "/api/strategies/batch-backtest",
            data=json.dumps({**base_payload, "risk_settings": {"stop_loss_pct": 2.0}}),
            content_type="application/json",
        )
        drawdown_with = json.loads(response_with.data)["data"]["results"][0][
            "max_drawdown_pct"
        ]

        # Both are negative numbers - a tight stop-loss must produce a
        # shallower (less negative / closer to zero) max drawdown.
        assert drawdown_with > drawdown_without
