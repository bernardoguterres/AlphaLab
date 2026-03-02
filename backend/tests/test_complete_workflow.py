"""End-to-end workflow test simulating a real user session."""

import sys
import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.fetcher import DataFetcher
from src.data.validator import DataValidator
from src.data.processor import FeatureEngineer
from src.strategies.implementations.moving_average_crossover import MovingAverageCrossover
from src.strategies.implementations.rsi_mean_reversion import RSIMeanReversion
from src.strategies.implementations.momentum_breakout import MomentumBreakout
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics


def _make_ohlcv(n=600, seed=42):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = 100 + rng.randn(n).cumsum() * 0.4
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


class TestCompleteWorkflow:
    """Simulate real user flow: fetch → validate → features → backtest → metrics."""

    def setup_method(self):
        self.raw_data = _make_ohlcv()
        self.validator = DataValidator()
        self.processor = FeatureEngineer()
        self.engine = BacktestEngine()
        self.metrics_calc = PerformanceMetrics()

    def _prepare_data(self):
        cleaned, report = self.validator.validate_and_clean(self.raw_data, "TEST")
        assert report.is_acceptable, f"Data quality too low: {report.confidence}"
        featured = self.processor.process(cleaned)
        featured.attrs["ticker"] = "TEST"
        return featured

    def test_ma_crossover_workflow(self):
        data = self._prepare_data()
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        results = self.engine.run_backtest(strategy, data, initial_capital=100_000)

        assert results.final_value > 0
        assert len(results.equity_curve) > 0

        metrics = self.metrics_calc.calculate_all(results.equity_curve, results.trades)
        assert "returns" in metrics
        assert "risk" in metrics
        assert "drawdown" in metrics
        assert "trades" in metrics
        assert "consistency" in metrics

    def test_rsi_mean_reversion_workflow(self):
        data = self._prepare_data()
        strategy = RSIMeanReversion()
        results = self.engine.run_backtest(strategy, data, initial_capital=100_000)

        assert results.final_value > 0
        assert len(results.equity_curve) > 0

        metrics = self.metrics_calc.calculate_all(results.equity_curve, results.trades)
        assert metrics["returns"] is not None

    def test_momentum_breakout_workflow(self):
        data = self._prepare_data()
        strategy = MomentumBreakout()
        results = self.engine.run_backtest(strategy, data, initial_capital=100_000)

        assert results.final_value > 0
        assert len(results.equity_curve) > 0

    def test_all_strategies_produce_valid_metrics(self):
        data = self._prepare_data()
        strategies = [
            MovingAverageCrossover({"short_window": 20, "long_window": 50}),
            RSIMeanReversion(),
            MomentumBreakout(),
        ]

        for strategy in strategies:
            results = self.engine.run_backtest(strategy, data, initial_capital=100_000)
            metrics = self.metrics_calc.calculate_all(results.equity_curve, results.trades)

            # Verify core metrics exist
            assert "sharpe_ratio" in metrics.get("risk", {}), \
                f"{strategy.name}: missing sharpe_ratio"
            assert "max_drawdown_pct" in metrics.get("drawdown", {}), \
                f"{strategy.name}: missing max_drawdown_pct"
            assert "total_trades" in metrics.get("trades", {}), \
                f"{strategy.name}: missing total_trades"

    def test_results_reproducible(self):
        """Same inputs should produce identical results."""
        data = self._prepare_data()
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})

        r1 = self.engine.run_backtest(strategy, data, initial_capital=100_000)
        r2 = self.engine.run_backtest(strategy, data, initial_capital=100_000)

        assert r1.final_value == r2.final_value
        assert len(r1.trades) == len(r2.trades)

    def test_results_serializable(self):
        """Results should convert to dict/JSON without error."""
        data = self._prepare_data()
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        results = self.engine.run_backtest(strategy, data, initial_capital=100_000)

        result_dict = results.to_dict()
        assert isinstance(result_dict, dict)
        assert "strategy" in result_dict
        assert "final_value" in result_dict
        assert "equity_curve" in result_dict

    def test_monte_carlo_workflow(self):
        data = self._prepare_data()
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        results = self.engine.run_backtest(
            strategy, data, initial_capital=100_000, monte_carlo_runs=20
        )

        assert results.monte_carlo is not None
        assert results.monte_carlo["runs"] == 20
        assert "prob_profit" in results.monte_carlo
        assert 0 <= results.monte_carlo["prob_profit"] <= 1
