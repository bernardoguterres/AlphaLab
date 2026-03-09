"""Tests for parameter optimization."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.parameter_optimizer import ParameterOptimizer
from src.strategies.implementations import MovingAverageCrossover
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.data.processor import FeatureEngineer


def _make_synthetic_data(n=500, seed=42):
    """Generate synthetic price data with features."""
    np.random.seed(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)

    # Generate price data with trend and noise
    trend = np.linspace(100, 150, n)
    noise = np.random.normal(0, 5, n)
    close = trend + noise

    # OHLCV data
    high = close + np.abs(np.random.normal(0, 2, n))
    low = close - np.abs(np.random.normal(0, 2, n))
    open_ = close + np.random.normal(0, 1, n)
    volume = np.random.randint(1_000_000, 10_000_000, n)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)

    # Add features using FeatureEngineer
    processor = FeatureEngineer()
    featured = processor.process(df)
    return featured


class TestParameterOptimizer:
    """Tests for ParameterOptimizer class."""

    def test_simple_grid_search(self):
        """Test basic grid search without walk-forward."""
        data = _make_synthetic_data(n=500)
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        # Simple param grid
        param_grid = {
            "short_window": [20, 50],
            "long_window": [100, 200],
        }

        result = optimizer.grid_search(
            strategy_class=MovingAverageCrossover,
            data=data,
            param_grid=param_grid,
            initial_capital=100_000,
            engine=engine,
            metrics_calc=metrics_calc,
            optimization_target="sharpe_ratio",
            walk_forward=False,
        )

        # Should test 2x2 = 4 combinations
        assert "best_params" in result
        assert "best_score" in result
        assert "all_results" in result
        assert "optimization_target" in result
        assert result["optimization_target"] == "sharpe_ratio"
        assert result["walk_forward"] is False
        assert len(result["all_results"]) == 4

        # Best params should be valid
        assert "short_window" in result["best_params"]
        assert "long_window" in result["best_params"]
        assert result["best_params"]["short_window"] in [20, 50]
        assert result["best_params"]["long_window"] in [100, 200]

    def test_walk_forward_optimization(self):
        """Test walk-forward validation prevents overfitting."""
        data = _make_synthetic_data(n=500)
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        param_grid = {
            "short_window": [20, 50],
            "long_window": [100, 200],
        }

        result = optimizer.grid_search(
            strategy_class=MovingAverageCrossover,
            data=data,
            param_grid=param_grid,
            initial_capital=100_000,
            engine=engine,
            metrics_calc=metrics_calc,
            optimization_target="sharpe_ratio",
            walk_forward=True,
            n_folds=3,
        )

        # Walk-forward specific fields
        assert result["walk_forward"] is True
        assert result["n_folds"] == 3
        assert "final_backtest" in result
        assert "total_return_pct" in result["final_backtest"]
        assert "sharpe_ratio" in result["final_backtest"]
        assert "max_drawdown_pct" in result["final_backtest"]

        # All results should have fold scores
        for combo_result in result["all_results"]:
            assert "params" in combo_result
            assert "avg_out_of_sample_score" in combo_result
            assert "fold_scores" in combo_result
            assert len(combo_result["fold_scores"]) == 3

    def test_fold_splitting(self):
        """Test that folds are created correctly with progressive training."""
        data = _make_synthetic_data(n=300)
        optimizer = ParameterOptimizer()

        folds = optimizer._create_folds(data, n_folds=3)

        assert len(folds) == 3

        # Each fold should have train and test data
        for train_data, test_data in folds:
            assert len(train_data) > 0
            assert len(test_data) > 0
            # Train data should come before test data
            assert train_data.index[-1] < test_data.index[0]

        # Training sets should grow progressively
        train_sizes = [len(train) for train, test in folds]
        assert train_sizes[0] < train_sizes[1] < train_sizes[2]

    def test_heatmap_generation(self):
        """Test 2D parameter heatmap generation."""
        data = _make_synthetic_data(n=400)
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        result = optimizer.generate_heatmap(
            strategy_class=MovingAverageCrossover,
            data=data,
            param1_name="short_window",
            param1_values=[20, 30, 40],
            param2_name="long_window",
            param2_values=[100, 150, 200],
            fixed_params={},
            initial_capital=100_000,
            engine=engine,
            metrics_calc=metrics_calc,
        )

        assert "param1_name" in result
        assert "param2_name" in result
        assert "param1_values" in result
        assert "param2_values" in result
        assert "heatmap_data" in result

        assert result["param1_name"] == "short_window"
        assert result["param2_name"] == "long_window"
        assert result["param1_values"] == [20, 30, 40]
        assert result["param2_values"] == [100, 150, 200]

        # Heatmap should be 3x3 grid (param2 rows x param1 cols)
        assert len(result["heatmap_data"]) == 3  # 3 rows
        for row in result["heatmap_data"]:
            assert len(row) == 3  # 3 columns

    def test_optimization_targets(self):
        """Test different optimization targets."""
        data = _make_synthetic_data(n=400)
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        param_grid = {
            "short_window": [20, 50],
            "long_window": [100],
        }

        # Test each target
        for target in ["sharpe_ratio", "total_return_pct", "max_drawdown_pct", "win_rate"]:
            result = optimizer.grid_search(
                strategy_class=MovingAverageCrossover,
                data=data,
                param_grid=param_grid,
                initial_capital=100_000,
                engine=engine,
                metrics_calc=metrics_calc,
                optimization_target=target,
                walk_forward=False,
            )

            assert result["optimization_target"] == target
            assert "best_score" in result
            # Best score should be finite (not NaN or inf)
            assert np.isfinite(result["best_score"])

    def test_single_parameter_combination(self):
        """Test optimization with single parameter set."""
        data = _make_synthetic_data(n=400)
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        param_grid = {
            "short_window": [50],
            "long_window": [200],
        }

        result = optimizer.grid_search(
            strategy_class=MovingAverageCrossover,
            data=data,
            param_grid=param_grid,
            initial_capital=100_000,
            engine=engine,
            metrics_calc=metrics_calc,
            optimization_target="sharpe_ratio",
            walk_forward=False,
        )

        # Should work with single combination
        assert len(result["all_results"]) == 1
        assert result["best_params"]["short_window"] == 50
        assert result["best_params"]["long_window"] == 200
