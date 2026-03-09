"""Tests for portfolio optimization."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.portfolio_optimizer import (
    PortfolioOptimizer,
    extract_daily_returns,
    build_returns_matrix,
)


def _make_returns_matrix(n=252, n_strategies=3, seed=42):
    """Generate synthetic returns matrix for testing."""
    np.random.seed(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)

    # Generate correlated returns
    returns_dict = {}
    for i in range(n_strategies):
        # Mean return: 8-12% annual
        mean_return = (0.08 + 0.04 * np.random.rand()) / 252
        # Volatility: 15-25% annual
        volatility = (0.15 + 0.10 * np.random.rand()) / np.sqrt(252)

        returns = np.random.normal(mean_return, volatility, n)
        returns_dict[f"Strategy_{i+1}"] = returns

    returns_df = pd.DataFrame(returns_dict, index=dates)
    return returns_df


class TestPortfolioOptimizer:
    """Tests for PortfolioOptimizer class."""

    def test_equal_weight(self):
        """Test equal weight optimization."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(method="equal_weight")

        assert "optimal_weights" in result
        assert len(result["optimal_weights"]) == 3
        assert all(abs(w - 1/3) < 0.01 for w in result["optimal_weights"])
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-6

    def test_max_sharpe(self):
        """Test maximum Sharpe ratio optimization."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(method="max_sharpe")

        assert "optimal_weights" in result
        assert "sharpe_ratio" in result
        assert len(result["optimal_weights"]) == 3
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-4

        # Sharpe should be better than equal weight
        eq_result = optimizer.optimize(method="equal_weight")
        assert result["sharpe_ratio"] >= eq_result["sharpe_ratio"]

    def test_min_variance(self):
        """Test minimum variance optimization."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(method="min_variance")

        assert "optimal_weights" in result
        assert "expected_risk" in result
        assert len(result["optimal_weights"]) == 3
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-4

        # Risk should be lower than equal weight
        eq_result = optimizer.optimize(method="equal_weight")
        assert result["expected_risk"] <= eq_result["expected_risk"] + 0.01  # Small tolerance

    def test_risk_parity(self):
        """Test risk parity optimization."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(method="risk_parity")

        assert "optimal_weights" in result
        assert len(result["optimal_weights"]) == 3
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-4

        # All weights should be > 0 for risk parity
        assert all(w > 0 for w in result["optimal_weights"])

    def test_constraint_enforcement(self):
        """Test that weight constraints are enforced."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(
            method="max_sharpe",
            max_weight=0.5,
            min_weight=0.1
        )

        # All weights should be within bounds
        assert all(0.1 <= w <= 0.5 for w in result["optimal_weights"])
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-4

    def test_two_strategies(self):
        """Test optimization with only 2 strategies."""
        returns = _make_returns_matrix(n=252, n_strategies=2)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(method="max_sharpe")

        assert len(result["optimal_weights"]) == 2
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-4

    def test_single_strategy(self):
        """Test optimization with single strategy (should return 100% weight)."""
        returns = _make_returns_matrix(n=252, n_strategies=1)
        optimizer = PortfolioOptimizer(returns)

        result = optimizer.optimize(method="equal_weight")

        assert len(result["optimal_weights"]) == 1
        assert abs(result["optimal_weights"][0] - 1.0) < 1e-6

    def test_correlated_strategies(self):
        """Test optimization with highly correlated strategies."""
        # Create perfectly correlated returns
        np.random.seed(42)
        n = 252
        dates = pd.bdate_range("2020-01-01", periods=n)
        base_returns = np.random.normal(0.0004, 0.01, n)

        returns_df = pd.DataFrame({
            "Strategy_1": base_returns,
            "Strategy_2": base_returns * 1.0,  # Perfect correlation
            "Strategy_3": base_returns * 0.95,  # Near-perfect correlation
        }, index=dates)

        optimizer = PortfolioOptimizer(returns_df)
        result = optimizer.optimize(method="min_variance")

        # Should still return valid weights
        assert len(result["optimal_weights"]) == 3
        assert abs(sum(result["optimal_weights"]) - 1.0) < 1e-4

    def test_efficient_frontier(self):
        """Test efficient frontier calculation."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        frontier = optimizer.efficient_frontier(n_points=10)

        assert len(frontier) > 0
        assert len(frontier) <= 10

        # Each point should have return, risk, sharpe
        for point in frontier:
            assert "return" in point
            assert "risk" in point
            assert "sharpe_ratio" in point
            assert point["risk"] >= 0

    def test_extract_daily_returns(self):
        """Test extracting returns from equity curve."""
        equity_curve = [
            {"date": "2020-01-01", "value": 100000},
            {"date": "2020-01-02", "value": 101000},
            {"date": "2020-01-03", "value": 100500},
        ]

        returns = extract_daily_returns(equity_curve)

        assert len(returns) == 2  # One less than equity points
        assert returns.iloc[0] == pytest.approx(0.01)
        assert returns.iloc[1] == pytest.approx(-0.00495, abs=1e-4)

    def test_build_returns_matrix(self):
        """Test building returns matrix from multiple backtests."""
        strategies = [
            {"backtest_id": "bt_1", "ticker": "AAPL", "strategy": "ma_crossover"},
            {"backtest_id": "bt_2", "ticker": "MSFT", "strategy": "rsi_mean_reversion"},
        ]

        backtest_results = {
            "bt_1": {
                "equity_curve": [
                    {"date": "2020-01-01", "value": 100000},
                    {"date": "2020-01-02", "value": 101000},
                    {"date": "2020-01-03", "value": 102000},
                ]
            },
            "bt_2": {
                "equity_curve": [
                    {"date": "2020-01-01", "value": 100000},
                    {"date": "2020-01-02", "value": 100500},
                    {"date": "2020-01-03", "value": 101000},
                ]
            }
        }

        returns_df, labels = build_returns_matrix(strategies, backtest_results)

        assert returns_df.shape[1] == 2
        assert len(labels) == 2
        assert "AAPL_ma_crossover" in labels
        assert "MSFT_rsi_mean_reversion" in labels

    def test_invalid_method(self):
        """Test that invalid method raises error."""
        returns = _make_returns_matrix(n=252, n_strategies=3)
        optimizer = PortfolioOptimizer(returns)

        with pytest.raises(ValueError):
            optimizer.optimize(method="invalid_method")

    def test_build_returns_matrix_missing_backtest(self):
        """Test handling of missing backtest IDs."""
        strategies = [
            {"backtest_id": "bt_1", "ticker": "AAPL", "strategy": "ma_crossover"},
            {"backtest_id": "bt_missing", "ticker": "MSFT", "strategy": "rsi_mean_reversion"},
        ]

        backtest_results = {
            "bt_1": {
                "equity_curve": [
                    {"date": "2020-01-01", "value": 100000},
                    {"date": "2020-01-02", "value": 101000},
                ]
            }
        }

        # Should only include valid backtests
        returns_df, labels = build_returns_matrix(strategies, backtest_results)

        assert returns_df.shape[1] == 1
        assert len(labels) == 1
        assert "AAPL_ma_crossover" in labels

    def test_build_returns_matrix_no_valid_backtests(self):
        """Test error when no valid backtests found."""
        strategies = [
            {"backtest_id": "bt_missing", "ticker": "AAPL", "strategy": "ma_crossover"},
        ]

        backtest_results = {}

        with pytest.raises(ValueError, match="No valid backtest results found"):
            build_returns_matrix(strategies, backtest_results)
