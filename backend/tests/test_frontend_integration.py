"""Integration tests simulating frontend workflows.

These tests run against the Flask backend API and simulate the complete
workflows that the frontend performs. They verify end-to-end functionality
without requiring a browser.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import create_app


@pytest.fixture
def client():
    """Create Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_yfinance():
    """Mock yfinance data fetching."""
    with patch("src.data.fetcher.yf.download") as mock_download:
        # Create synthetic price data
        dates = pd.bdate_range("2020-01-01", periods=1000)
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(1000) * 0.5)
        high = close + np.abs(np.random.randn(1000) * 0.5)
        low = close - np.abs(np.random.randn(1000) * 0.5)
        open_ = close + np.random.randn(1000) * 0.3
        volume = np.random.randint(1_000_000, 10_000_000, 1000)

        mock_df = pd.DataFrame({
            ("Open", "AAPL"): open_,
            ("High", "AAPL"): high,
            ("Low", "AAPL"): low,
            ("Close", "AAPL"): close,
            ("Volume", "AAPL"): volume,
        }, index=dates)

        mock_download.return_value = mock_df
        yield mock_download


class TestFullBacktestFlow:
    """Test complete backtest workflow from data fetch to export."""

    def test_full_backtest_flow(self, client, mock_yfinance):
        """Test full backtest flow: fetch → backtest → export."""

        # Step 1: Fetch data for AAPL
        fetch_response = client.post(
            "/api/data/fetch",
            json={
                "tickers": ["AAPL"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "interval": "1d",
            }
        )

        assert fetch_response.status_code == 200
        fetch_data = fetch_response.get_json()
        assert fetch_data["status"] == "ok"
        assert "AAPL" in fetch_data["data"]

        # Step 2: Run backtest with MA Crossover + risk settings
        backtest_response = client.post(
            "/api/strategies/backtest",
            json={
                "ticker": "AAPL",
                "strategy": "ma_crossover",
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
                "params": {
                    "short_window": 50,
                    "long_window": 200,
                    "volume_confirmation": True,
                    "cooldown_days": 5,
                },
                "position_sizing": "equal_weight",
                "monte_carlo_runs": 0,
                "risk_settings": {
                    "stop_loss_pct": 2.0,
                    "take_profit_pct": 5.0,
                    "max_position_size_pct": 10.0,
                    "max_daily_loss_pct": 3.0,
                    "max_open_positions": 5,
                    "trailing_stop_enabled": False,
                    "trailing_stop_pct": 3.0,
                    "commission_per_trade": 0.0,
                }
            }
        )

        assert backtest_response.status_code == 200
        backtest_data = backtest_response.get_json()
        assert backtest_data["status"] == "ok"

        result = backtest_data["data"]

        # Verify result structure
        assert "backtest_id" in result
        assert "equity_curve" in result
        assert "trades" in result
        assert "metrics" in result
        assert "benchmark" in result

        # Verify equity curve
        assert len(result["equity_curve"]) > 0
        assert "date" in result["equity_curve"][0]
        assert "value" in result["equity_curve"][0]

        # Verify metrics structure
        assert "returns" in result["metrics"]
        assert "risk" in result["metrics"]
        assert "drawdown" in result["metrics"]
        assert "trades" in result["metrics"]
        assert "consistency" in result["metrics"]
        assert "vs_benchmark" in result["metrics"]

        backtest_id = result["backtest_id"]

        # Step 3: Export strategy
        export_response = client.post(
            "/api/strategies/export",
            json={"backtest_id": backtest_id}
        )

        assert export_response.status_code == 200
        assert export_response.content_type == "application/json"

        # Parse export JSON
        export_json = json.loads(export_response.data)

        # Verify schema
        assert export_json["schema_version"] == "1.0"
        assert export_json["strategy"]["name"] == "ma_crossover"
        assert export_json["ticker"] == "AAPL"
        assert "risk" in export_json
        assert "execution" in export_json
        assert "metadata" in export_json

        # Verify risk settings are included
        assert export_json["risk"]["stop_loss_pct"] == 2.0
        assert export_json["risk"]["take_profit_pct"] == 5.0
        assert export_json["risk"]["max_position_size_pct"] == 10.0


class TestBatchBacktestFlow:
    """Test batch backtesting across multiple tickers."""

    def test_batch_backtest_flow(self, client, mock_yfinance):
        """Test batch backtest flow: fetch multiple tickers → batch backtest."""

        # Step 1: Fetch data for 3 tickers
        tickers = ["AAPL", "MSFT", "GOOGL"]

        fetch_response = client.post(
            "/api/data/fetch",
            json={
                "tickers": tickers,
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "interval": "1d",
            }
        )

        assert fetch_response.status_code == 200

        # Step 2: Run batch backtest
        batch_response = client.post(
            "/api/strategies/batch-backtest",
            json={
                "tickers": tickers,
                "strategy": "ma_crossover",
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
                "params": {
                    "short_window": 50,
                    "long_window": 200,
                },
                "position_sizing": "equal_weight",
            }
        )

        assert batch_response.status_code == 200
        batch_data = batch_response.get_json()
        assert batch_data["status"] == "ok"

        results = batch_data["data"]

        # Verify results structure
        assert "results" in results
        assert "batch_summary" in results
        assert "errors" in results

        # Verify results array
        assert len(results["results"]) > 0

        # Verify results are sorted by Sharpe ratio (descending)
        sharpe_ratios = [r["sharpe_ratio"] for r in results["results"]]
        assert sharpe_ratios == sorted(sharpe_ratios, reverse=True)

        # Verify batch summary
        summary = results["batch_summary"]
        assert "total_tickers" in summary
        assert "successful" in summary
        assert "failed" in summary
        assert "profitable_count" in summary
        assert "avg_sharpe_ratio" in summary
        assert "runtime_seconds" in summary

        assert summary["total_tickers"] == 3


class TestComparisonFlow:
    """Test strategy comparison workflow."""

    def test_comparison_flow(self, client, mock_yfinance):
        """Test comparison flow: run 3 strategies → compare."""

        # Step 1: Fetch data
        fetch_response = client.post(
            "/api/data/fetch",
            json={
                "tickers": ["AAPL"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "interval": "1d",
            }
        )

        assert fetch_response.status_code == 200

        # Step 2: Run comparison
        compare_response = client.post(
            "/api/compare",
            json={
                "ticker": "AAPL",
                "strategies": ["ma_crossover", "rsi_mean_reversion", "momentum_breakout"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
            }
        )

        assert compare_response.status_code == 200
        compare_data = compare_response.get_json()
        assert compare_data["status"] == "ok"

        results = compare_data["data"]

        # Verify all 3 strategies have results
        assert "ma_crossover" in results
        assert "rsi_mean_reversion" in results
        assert "momentum_breakout" in results

        # Verify each strategy has required data
        for strategy, data in results.items():
            assert "total_return_pct" in data
            assert "metrics" in data
            assert "returns" in data["metrics"]
            assert "risk" in data["metrics"]


class TestPortfolioOptimizeFlow:
    """Test portfolio optimization workflow."""

    def test_portfolio_optimize_flow(self, client, mock_yfinance):
        """Test portfolio optimization: run 3 backtests → optimize."""

        # Step 1: Fetch data
        client.post(
            "/api/data/fetch",
            json={
                "tickers": ["AAPL"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "interval": "1d",
            }
        )

        # Step 2: Run 3 backtests with different strategies
        backtest_ids = []
        strategies = ["ma_crossover", "rsi_mean_reversion", "momentum_breakout"]

        for strategy in strategies:
            response = client.post(
                "/api/strategies/backtest",
                json={
                    "ticker": "AAPL",
                    "strategy": strategy,
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "initial_capital": 100000,
                    "params": {},
                    "position_sizing": "equal_weight",
                    "monte_carlo_runs": 0,
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            backtest_ids.append(data["data"]["backtest_id"])

        # Step 3: Optimize portfolio
        optimize_response = client.post(
            "/api/portfolio/optimize",
            json={
                "strategies": [
                    {"backtest_id": backtest_ids[0], "ticker": "AAPL", "strategy": strategies[0]},
                    {"backtest_id": backtest_ids[1], "ticker": "AAPL", "strategy": strategies[1]},
                    {"backtest_id": backtest_ids[2], "ticker": "AAPL", "strategy": strategies[2]},
                ],
                "method": "max_sharpe",
                "constraints": {
                    "max_weight_per_strategy": 0.5,
                    "min_weight_per_strategy": 0.1,
                    "target_return": None,
                }
            }
        )

        assert optimize_response.status_code == 200
        optimize_data = optimize_response.get_json()
        assert optimize_data["status"] == "ok"

        result = optimize_data["data"]

        # Verify result structure
        assert "optimal_weights" in result
        assert "expected_return" in result
        assert "expected_risk" in result
        assert "sharpe_ratio" in result
        assert "strategy_labels" in result
        assert "efficient_frontier" in result

        # Verify weights
        weights = result["optimal_weights"]
        assert len(weights) == 3

        # Weights should sum to 1.0 (within floating point tolerance)
        assert abs(sum(weights) - 1.0) < 0.01

        # Each weight should be within constraints
        for weight in weights:
            assert 0.1 <= weight <= 0.5

        # Verify efficient frontier
        frontier = result["efficient_frontier"]
        assert len(frontier) > 0

        for point in frontier:
            assert "return" in point
            assert "risk" in point
            assert "sharpe_ratio" in point


class TestSettingsFlow:
    """Test settings management workflow."""

    def test_settings_flow(self, client, monkeypatch):
        """Test settings flow: save → load → verify persistence."""

        # Set environment variables for API key configured flags
        monkeypatch.setenv("ALPACA_API_KEY", "test_key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")

        # Step 1: Save settings
        save_response = client.post(
            "/api/settings/notifications",
            json={
                "telegram": {
                    "enabled": True,
                    "alert_trades": True,
                    "alert_daily_summary": False,
                    "alert_errors": True,
                    "alert_drawdown": True,
                    "alert_signals": False,
                    "drawdown_threshold_pct": 7.5,
                },
                "alpaca": {
                    "paper_trading": False,
                }
            }
        )

        assert save_response.status_code == 200
        save_data = save_response.get_json()
        assert save_data["status"] == "ok"

        # Step 2: Load settings
        get_response = client.get("/api/settings/notifications")

        assert get_response.status_code == 200
        get_data = get_response.get_json()
        assert get_data["status"] == "ok"

        settings = get_data["data"]

        # Verify settings persisted
        assert settings["telegram"]["enabled"] is True
        assert settings["telegram"]["alert_daily_summary"] is False
        assert settings["telegram"]["drawdown_threshold_pct"] == 7.5
        assert settings["alpaca"]["paper_trading"] is False

        # Step 3: Verify API keys are masked
        assert "api_key" not in settings["alpaca"]
        assert "secret_key" not in settings["alpaca"]

        # Only configured flags should be present
        assert settings["alpaca"]["api_key_configured"] is True
        assert settings["alpaca"]["secret_key_configured"] is True

        # Step 4: Verify settings persist across multiple calls
        get_response_2 = client.get("/api/settings/notifications")
        settings_2 = get_response_2.get_json()["data"]

        assert settings_2["telegram"]["enabled"] == settings["telegram"]["enabled"]
        assert settings_2["telegram"]["drawdown_threshold_pct"] == settings["telegram"]["drawdown_threshold_pct"]


class TestAllStrategiesBacktest:
    """Test that all 5 strategies can run backtests without crashing."""

    def test_all_strategies_backtest(self, client, mock_yfinance):
        """Test backtest for each of the 5 strategies."""

        # Fetch data once
        client.post(
            "/api/data/fetch",
            json={
                "tickers": ["AAPL"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "interval": "1d",
            }
        )

        strategies = [
            "ma_crossover",
            "rsi_mean_reversion",
            "momentum_breakout",
            "bollinger_breakout",
            "vwap_reversion",
        ]

        for strategy in strategies:
            response = client.post(
                "/api/strategies/backtest",
                json={
                    "ticker": "AAPL",
                    "strategy": strategy,
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "initial_capital": 100000,
                    "params": {},  # Use default params
                    "position_sizing": "equal_weight",
                    "monte_carlo_runs": 0,
                }
            )

            assert response.status_code == 200, f"Strategy {strategy} failed"
            data = response.get_json()
            assert data["status"] == "ok", f"Strategy {strategy} returned error"

            result = data["data"]

            # Verify basic result structure
            assert "equity_curve" in result
            assert "trades" in result
            assert "metrics" in result
            assert "total_return_pct" in result
            assert "final_value" in result

            # Verify metrics are reasonable (not NaN or infinite)
            metrics = result["metrics"]
            sharpe = metrics["risk"]["sharpe_ratio"]
            assert not np.isnan(sharpe) and not np.isinf(sharpe), f"Strategy {strategy} has invalid Sharpe ratio"

            total_return = result["total_return_pct"]
            assert not np.isnan(total_return) and not np.isinf(total_return), f"Strategy {strategy} has invalid total return"
