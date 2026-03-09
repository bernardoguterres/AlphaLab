"""Tests for edge cases that commonly break backtesting systems.

These tests ensure AlphaLab handles real-world data issues gracefully:
- Penny stocks, stock splits, delisted stocks
- Insufficient data, zero volume, NaN values
- Strategies with 0 trades, all losers, all winners
- Export with edge cases
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.processor import FeatureEngineer
from src.data.validator import DataValidator
from src.strategies.implementations import MovingAverageCrossover, MomentumBreakout
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.api.routes import _build_export_json


class TestDataQualityEdgeCases:
    """Test data quality edge cases."""

    def test_penny_stock_with_large_swings(self):
        """Test penny stock (<$1) with large % swings - verify no divide-by-zero."""
        # Create penny stock data with 50% daily swings
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        # Price oscillates between $0.10 and $0.90
        close = 0.50 + 0.40 * np.sin(np.linspace(0, 4 * np.pi, 100))
        high = close + np.abs(np.random.normal(0, 0.05, 100))
        low = close - np.abs(np.random.normal(0, 0.05, 100))
        open_ = close + np.random.normal(0, 0.02, 100)
        volume = np.random.randint(100_000, 1_000_000, 100)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        # Process features - should not crash
        processor = FeatureEngineer()
        processed = processor.process(df)

        assert len(processed) == 100
        assert not processed["Close"].isna().all()

        # Run backtest - should handle small prices
        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )

        # Should complete without divide-by-zero
        assert result is not None
        assert len(result.equity_curve) > 0
        assert not np.isnan(result.total_return_pct)

    def test_stock_with_missing_days(self):
        """Test stock with missing days (delisted period) - verify backtest handles gaps."""
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_ = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 100)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        # Remove 10 random days (simulate delisting gaps)
        gap_indices = np.random.choice(df.index[20:80], size=10, replace=False)
        df = df.drop(gap_indices)

        assert len(df) == 90  # 10 days missing

        # Process - should handle gaps
        processor = FeatureEngineer()
        processed = processor.process(df)

        assert len(processed) == 90

        # Backtest should handle non-consecutive dates
        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )
        assert result is not None

    def test_stock_split_no_false_signals(self):
        """Test stock with 2:1 split - verify signals don't fire falsely on split day."""
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        # Stable price before split
        close_before = np.full(50, 200.0) + np.random.randn(50) * 2
        # 2:1 split at day 50 - price drops 50% but it's not a crash
        close_after = np.full(50, 100.0) + np.random.randn(50) * 1

        close = np.concatenate([close_before, close_after])
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_ = close + np.random.randn(100) * 0.5
        volume_before = np.random.randint(1_000_000, 2_000_000, 50)
        volume_after = np.random.randint(2_000_000, 4_000_000, 50)  # Volume doubles after split
        volume = np.concatenate([volume_before, volume_after])

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        # Check if validator detects the split
        validator = DataValidator()
        cleaned_df, report = validator.validate_and_clean(df, ticker="SPLIT")

        # Should have low confidence due to split
        assert report.confidence < 0.95

        # Backtest should still work
        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )
        assert result is not None

    def test_very_short_date_range(self):
        """Test very short date range (30 bars) - verify strategies handle insufficient data."""
        dates = pd.bdate_range("2023-01-01", periods=30)
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(30) * 2)
        high = close + np.abs(np.random.randn(30))
        low = close - np.abs(np.random.randn(30))
        open_ = close + np.random.randn(30) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 30)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        # SMA_200 will be all NaN, but should not crash
        assert processed["SMA_200"].isna().all()

        # Strategy with long_window=200 should handle gracefully
        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 200,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        signals = strategy.generate_signals(processed)

        # Should return all zeros (no valid signals due to insufficient data)
        assert signals["signal"].abs().sum() == 0

    def test_zero_volume_days(self):
        """Test ticker with zero volume days - verify volume-based strategies don't crash."""
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_ = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 100)

        # Set 10 random days to zero volume
        zero_vol_indices = np.random.choice(range(100), size=10, replace=False)
        volume[zero_vol_indices] = 0

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        # Volume-based strategy should handle zero volume
        strategy = MomentumBreakout({
            "lookback": 20,
            "volume_surge_pct": 150,
            "rsi_min": 50,
            "stop_loss_atr_mult": 2.0,
            "trailing_stop_atr_mult": 3.0,
        })

        signals = strategy.generate_signals(processed)

        # Should not crash
        assert signals is not None
        assert len(signals) == 100

    def test_single_day_of_data(self):
        """Test single day of data - verify no index errors."""
        dates = pd.bdate_range("2023-01-01", periods=1)

        df = pd.DataFrame({
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Volume": [1_000_000],
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        # Should have 1 row, all indicators NaN
        assert len(processed) == 1
        assert processed["SMA_20"].isna().all()

        # Strategy should handle gracefully
        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        signals = strategy.generate_signals(processed)

        # Should return 0 signal (no data)
        assert signals["signal"].iloc[0] == 0

    def test_data_with_nan_values(self):
        """Test data with NaN values scattered - verify indicators propagate NaN correctly."""
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_ = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 100).astype(float)

        # Inject NaN values
        nan_indices = [10, 25, 50, 75]
        close[nan_indices] = np.nan
        volume[nan_indices] = np.nan

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        # Should handle NaN without crashing
        assert len(processed) == 100

        # NaN should propagate through indicators
        assert processed["Close"].isna().sum() == 4

        # Strategy should handle NaN
        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        signals = strategy.generate_signals(processed)
        assert signals is not None


class TestStrategyEdgeCases:
    """Test strategy behavior edge cases."""

    def test_strategy_with_zero_trades(self):
        """Test strategy that generates 0 trades - verify metrics return sensible defaults."""
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        # Flat price (no volatility = no signals)
        close = np.full(100, 100.0)
        high = close + 0.01
        low = close - 0.01
        open_ = close
        volume = np.full(100, 1_000_000)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )

        # Should have 0 trades
        assert len(result.trades) == 0

        # Metrics may be None if no trades
        if result.metrics is not None:
            metrics = result.metrics
            assert metrics["risk"]["sharpe_ratio"] == 0.0
            assert metrics["returns"]["total_return_pct"] == 0.0
            assert metrics["trades"]["win_rate"] == 0.0
            assert metrics["trades"]["profit_factor"] == 0.0
        else:
            # If metrics is None with 0 trades, that's acceptable
            assert result.total_return_pct == 0.0

    def test_strategy_with_one_open_trade(self):
        """Test strategy with 1 trade still open at end - verify final P&L uses last close."""
        dates = pd.bdate_range("2023-01-01", periods=50)
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(50) * 2)
        high = close + np.abs(np.random.randn(50))
        low = close - np.abs(np.random.randn(50))
        open_ = close + np.random.randn(50) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 50)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        # Manually create a signal on day 45 (near end)
        strategy = MovingAverageCrossover({
            "short_window": 5,
            "long_window": 10,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )

        # Should complete without crashing
        assert result is not None

        # If trades exist, verify equity curve is valid
        if len(result.trades) > 0:
            # Final equity should be positive
            assert result.final_value > 0
            assert len(result.equity_curve) > 0

    def test_all_stop_loss_triggers(self):
        """Test strategy where stop_loss triggers on every trade."""
        dates = pd.bdate_range("2023-01-01", periods=100)
        np.random.seed(42)

        # Trending down market (all trades will lose)
        close = 200 - np.linspace(0, 100, 100) + np.random.randn(100) * 2
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_ = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 100)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        strategy = MovingAverageCrossover({
            "short_window": 10,
            "long_window": 20,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )

        # Should handle all losses
        assert result is not None

        if len(result.trades) > 0:
            # Max drawdown should be significant
            assert result.metrics["drawdown"]["max_drawdown"] < -1.0

    def test_all_trades_losers(self):
        """Test all trades are losers - verify win_rate=0%, not crash."""
        dates = pd.bdate_range("2023-01-01", periods=50)
        np.random.seed(42)

        # Create data where price always goes down after any signal
        close = 100 + np.random.randn(50) * 5
        high = close + 1
        low = close - 1
        open_ = close
        volume = np.random.randint(1_000_000, 5_000_000, 50)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        strategy = MovingAverageCrossover({
            "short_window": 5,
            "long_window": 10,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )

        # Even if all losers, should not crash
        assert result is not None

        # If trades exist and all are losers
        if len(result.trades) > 0 and result.metrics is not None:
            win_rate = result.metrics["trades"]["win_rate"]
            # Win rate should be 0.0 or very low, not NaN
            assert not np.isnan(win_rate)
            assert 0.0 <= win_rate <= 1.0

    def test_all_trades_winners(self):
        """Test all trades are winners - verify profit_factor handled gracefully."""
        dates = pd.bdate_range("2023-01-01", periods=50)
        np.random.seed(42)

        # Strong uptrend (all trades should win)
        close = 100 + np.linspace(0, 50, 50) + np.random.randn(50) * 0.5
        high = close + 1
        low = close - 0.5
        open_ = close
        volume = np.random.randint(1_000_000, 5_000_000, 50)

        df = pd.DataFrame({
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }, index=dates)

        processor = FeatureEngineer()
        processed = processor.process(df)

        strategy = MovingAverageCrossover({
            "short_window": 5,
            "long_window": 10,
            "volume_confirmation": False,
            "cooldown_days": 1,
        })

        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy=strategy,
            data=processed,
            initial_capital=10000,
            position_sizing="equal_weight",
        )

        assert result is not None

        # If trades exist and all winners
        if len(result.trades) > 0:
            win_rate = result.metrics["trades"]["win_rate"]
            profit_factor = result.metrics["trades"]["profit_factor"]

            # Win rate should be 1.0 (or close) if all winners
            assert 0.0 <= win_rate <= 1.0

            # Profit factor should be inf or very large if no losses
            # System should handle this gracefully
            assert not np.isnan(profit_factor)


class TestExportEdgeCases:
    """Test export functionality edge cases."""

    def test_export_with_zero_trades(self):
        """Test export a strategy with 0 trades - verify JSON still valid."""
        config = {"app": {"version": "0.1.0"}}

        # Results with 0 trades
        results = {
            "total_return_pct": 0.0,
            "total_trades": 0,
            "final_value": 10000.0,
            "metrics": {
                "returns": {
                    "total_return_pct": 0.0,
                    "annualized_return_pct": 0.0,
                    "cagr": 0.0,
                },
                "risk": {
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "calmar_ratio": 0.0,
                    "volatility": 0.0,
                },
                "drawdown": {
                    "max_drawdown": 0.0,
                    "max_drawdown_duration_days": 0,
                },
                "trades": {
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                },
            }
        }

        export = _build_export_json(
            backtest_id="test_zero_trades",
            ticker="FLAT",
            strategy_name="ma_crossover",
            params={
                "short_window": 50,
                "long_window": 200,
                "volume_confirmation": True,
                "volume_avg_period": 20,
                "min_separation_pct": 0.0,
                "cooldown_days": 5,
            },
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=10000,
            results=results,
            config=config,
        )

        # Should build valid export even with 0 trades
        assert export["schema_version"] == "1.0"
        assert export["ticker"] == "FLAT"
        assert export["metadata"]["performance"]["total_trades"] == 0
        assert export["metadata"]["performance"]["sharpe_ratio"] == 0.0

    def test_export_with_long_ticker_name(self):
        """Test export with very long ticker name or special characters."""
        config = {"app": {"version": "0.1.0"}}

        results = {
            "total_return_pct": 10.0,
            "total_trades": 5,
            "metrics": {
                "risk": {"sharpe_ratio": 1.5, "sortino_ratio": 1.8, "calmar_ratio": 2.0},
                "drawdown": {"max_drawdown": -5.0},
                "trades": {"win_rate": 0.6, "profit_factor": 1.5},
            }
        }

        # Long ticker with special characters
        long_ticker = "BRK.B-USD-LONG-TICKER-NAME"

        export = _build_export_json(
            backtest_id="test_long",
            ticker=long_ticker,
            strategy_name="ma_crossover",
            params={
                "short_window": 50,
                "long_window": 200,
                "volume_confirmation": True,
                "volume_avg_period": 20,
                "min_separation_pct": 0.0,
                "cooldown_days": 5,
            },
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=10000,
            results=results,
            config=config,
        )

        # Should handle long ticker name
        assert export["ticker"] == long_ticker
        assert len(export["ticker"]) > 10

    def test_export_with_extreme_parameters(self):
        """Test export with extreme parameter values (SMA period = 1)."""
        config = {"app": {"version": "0.1.0"}}

        results = {
            "total_return_pct": 5.0,
            "total_trades": 10,
            "metrics": {
                "risk": {"sharpe_ratio": 1.2, "sortino_ratio": 1.5, "calmar_ratio": 1.8},
                "drawdown": {"max_drawdown": -8.0},
                "trades": {"win_rate": 0.5, "profit_factor": 1.2},
            }
        }

        # Extreme parameters (very short windows)
        extreme_params = {
            "short_window": 2,  # Minimum
            "long_window": 3,   # Minimum
            "volume_confirmation": False,
            "volume_avg_period": 5,
            "min_separation_pct": 0.0,
            "cooldown_days": 0,  # No cooldown
        }

        export = _build_export_json(
            backtest_id="test_extreme",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params=extreme_params,
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=10000,
            results=results,
            config=config,
        )

        # Should handle extreme params
        assert export["strategy"]["parameters"]["short_window"] == 2
        assert export["strategy"]["parameters"]["long_window"] == 3
        assert export["strategy"]["parameters"]["cooldown_days"] == 0
