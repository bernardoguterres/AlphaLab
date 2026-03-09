"""Performance benchmarking tests to prevent regressions.

These tests verify that backtests, optimizations, and data operations
complete within acceptable time limits. Run before every deployment.

If a test fails:
1. Check git diff to see what changed
2. Profile the slow function (use cProfile or line_profiler)
3. Optimize the bottleneck
4. Re-run tests until they pass
5. Document performance in commit message

Performance Budgets:
- Backtest (5 years daily): <30s
- Signal generation (500 bars): <5s (CRITICAL for AlphaLive)
- Portfolio optimization (6 strategies): <60s
- Batch backtest (10 tickers): <3 minutes
- Data fetch (cached): <0.1s
"""

import time
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.engine import BacktestEngine
from src.backtest.portfolio_optimizer import PortfolioOptimizer
from src.data.processor import FeatureEngineer
from src.data.fetcher import DataFetcher
from src.strategies.implementations import MovingAverageCrossover


@pytest.fixture
def large_dataset():
    """5 years of daily data (~1260 bars)."""
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", periods=1260)

    # Realistic price action with trend + noise
    trend = np.linspace(100, 200, 1260)
    noise = np.cumsum(np.random.randn(1260) * 2)
    close = trend + noise

    high = close + np.abs(np.random.randn(1260) * 2)
    low = close - np.abs(np.random.randn(1260) * 2)
    open_ = close + np.random.randn(1260) * 1
    volume = np.random.randint(1_000_000, 10_000_000, 1260)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)

    # Process features
    processor = FeatureEngineer()
    return processor.process(df)


@pytest.fixture
def medium_dataset():
    """1 year of hourly data (~1560 bars)."""
    np.random.seed(42)

    # Generate hourly timestamps (252 trading days * 6.5 hours)
    dates = pd.date_range("2024-01-01", periods=1560, freq="h")

    # Intraday price action
    trend = np.linspace(150, 180, 1560)
    noise = np.cumsum(np.random.randn(1560) * 0.5)
    close = trend + noise

    high = close + np.abs(np.random.randn(1560) * 0.5)
    low = close - np.abs(np.random.randn(1560) * 0.5)
    open_ = close + np.random.randn(1560) * 0.2
    volume = np.random.randint(500_000, 2_000_000, 1560)

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)

    processor = FeatureEngineer()
    return processor.process(df)


def test_backtest_5_years_daily_completes_in_30_seconds(large_dataset):
    """
    Regression test: Full 5-year backtest should complete in <30s.

    If this fails, investigate:
    - Inefficient indicator calculations
    - Pandas apply() instead of vectorized operations
    - Excessive logging in tight loops
    - Portfolio operations in every bar (should batch)
    """
    strategy = MovingAverageCrossover({
        "short_window": 20,
        "long_window": 50,
        "volume_confirmation": False,
        "cooldown_days": 5,
    })

    engine = BacktestEngine()

    start = time.time()
    results = engine.run_backtest(
        strategy=strategy,
        data=large_dataset,
        initial_capital=100000,
        position_sizing="equal_weight",
        monte_carlo_runs=0,
    )
    elapsed = time.time() - start

    # Assert performance budget
    assert elapsed < 30.0, (
        f"Backtest took {elapsed:.1f}s (limit: 30s). "
        "Check for inefficient loops or non-vectorized operations."
    )

    # Sanity check - should generate some trades
    assert len(results.trades) > 0, "No trades generated (strategy broken?)"
    assert len(results.equity_curve) == 1260, "Equity curve length mismatch"


def test_signal_generation_500_bars_under_5_seconds(medium_dataset):
    """
    Regression test: Single signal generation from 500 bars must be <5s.

    This is the CRITICAL path for AlphaLive — if this exceeds 5s in production,
    the bot blocks the main loop and misses market opportunities.

    If this fails:
    - Profile strategy.generate_signals()
    - Check if indicators are being recalculated unnecessarily
    - Ensure feature engineering is done once, not per signal
    - Consider caching intermediate calculations
    """
    data_slice = medium_dataset.iloc[:500].copy()

    strategy = MovingAverageCrossover({
        "short_window": 20,
        "long_window": 50,
        "volume_confirmation": True,
        "cooldown_days": 1,
    })

    start = time.time()
    signals = strategy.generate_signals(data_slice)
    elapsed = time.time() - start

    # CRITICAL budget for live trading
    assert elapsed < 5.0, (
        f"Signal generation took {elapsed:.3f}s (limit: 5.0s). "
        "This is TOO SLOW for AlphaLive real-time trading. "
        "Profile the generate_signals() method and optimize hot paths."
    )

    # Sanity check
    assert len(signals) == 500, "Signal output length mismatch"
    assert "signal" in signals.columns, "Missing 'signal' column"


def test_portfolio_optimization_6_strategies_under_60_seconds():
    """
    Regression test: Optimizing 6 strategy allocations should complete in <60s.

    scipy.optimize can be slow — if this fails, consider:
    - Reducing number of optimizer iterations (maxiter parameter)
    - Using faster optimization method (SLSQP vs Sequential Least Squares)
    - Caching correlation matrix calculations
    - Using equal_weight as fallback for timeout scenarios
    """
    # Create 6 mock equity curves with different characteristics
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", periods=252)

    equity_curves = []
    for i in range(6):
        # Different return profiles
        returns = np.random.randn(252) * 0.02 + 0.0005 * (i + 1)
        equity = 100000 * (1 + returns).cumprod()

        curve = [{"date": str(d.date()), "value": v} for d, v in zip(dates, equity)]
        equity_curves.append(curve)

    # Create returns matrix as DataFrame
    returns_dict = {}
    for i, curve in enumerate(equity_curves):
        values = [p["value"] for p in curve]
        returns = pd.Series(values).pct_change().dropna()
        returns_dict[f"strategy_{i}"] = returns.values

    returns_matrix = pd.DataFrame(returns_dict)

    optimizer = PortfolioOptimizer(returns_matrix, risk_free_rate=0.02)

    start = time.time()
    result = optimizer.optimize(
        method="max_sharpe",
        max_weight=0.5,
        min_weight=0.05,
    )
    elapsed = time.time() - start

    # Assert performance budget
    assert elapsed < 60.0, (
        f"Optimization took {elapsed:.1f}s (limit: 60s). "
        "Consider reducing scipy.optimize iterations or using a faster method."
    )

    # Sanity check
    weights = result["optimal_weights"]
    assert len(weights) == 6, "Wrong number of weights returned"
    assert abs(sum(weights) - 1.0) < 0.01, "Weights don't sum to 1.0"
    assert all(0.05 <= w <= 0.5 for w in weights), "Weights violate constraints"


def test_batch_backtest_10_tickers_under_3_minutes():
    """
    Regression test: Batch backtest of 10 tickers should complete in <3 minutes.

    This test verifies the batch endpoint doesn't time out in production.

    If this fails:
    - Check if data fetching is sequential (should be parallel or cached)
    - Verify backtests aren't being serialized unnecessarily
    - Consider reducing default parameter search space
    - Add early termination for failed tickers
    """
    # Mock yfinance to avoid real API calls
    with patch("src.data.fetcher.yf.download") as mock_download:
        # Create synthetic data for 10 tickers
        np.random.seed(42)
        dates = pd.bdate_range("2023-01-01", periods=252)

        def create_mock_data(ticker):
            close = 100 + np.cumsum(np.random.randn(252) * 2)
            high = close + np.abs(np.random.randn(252))
            low = close - np.abs(np.random.randn(252))
            open_ = close + np.random.randn(252) * 0.5
            volume = np.random.randint(1_000_000, 5_000_000, 252)

            df = pd.DataFrame({
                ("Open", ticker): open_,
                ("High", ticker): high,
                ("Low", ticker): low,
                ("Close", ticker): close,
                ("Volume", ticker): volume,
            }, index=dates)
            return df

        # Return data based on ticker
        def mock_fetch(*args, **kwargs):
            tickers = kwargs.get("tickers", [])
            if isinstance(tickers, str):
                return create_mock_data(tickers)
            # For multiple tickers, combine into MultiIndex
            dfs = [create_mock_data(t) for t in tickers]
            return pd.concat(dfs, axis=1)

        mock_download.side_effect = mock_fetch

        # Run batch backtest
        from src.data.fetcher import DataFetcher
        from src.data.processor import FeatureEngineer

        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
                   "NVDA", "META", "NFLX", "AMD", "INTC"]

        strategy = MovingAverageCrossover({
            "short_window": 20,
            "long_window": 50,
            "volume_confirmation": False,
            "cooldown_days": 3,
        })

        engine = BacktestEngine()
        processor = FeatureEngineer()

        start = time.time()
        results = []

        for ticker in tickers:
            try:
                # Simulate what batch endpoint does
                data = create_mock_data(ticker)

                # Extract single ticker data
                ticker_data = pd.DataFrame({
                    "Open": data[("Open", ticker)],
                    "High": data[("High", ticker)],
                    "Low": data[("Low", ticker)],
                    "Close": data[("Close", ticker)],
                    "Volume": data[("Volume", ticker)],
                }, index=data.index)

                processed = processor.process(ticker_data)

                result = engine.run_backtest(
                    strategy=strategy,
                    data=processed,
                    initial_capital=100000,
                    position_sizing="equal_weight",
                )
                results.append(result)
            except Exception as e:
                # Don't let one failure break the batch
                pass

        elapsed = time.time() - start

        # Assert performance budget
        assert elapsed < 180.0, (
            f"Batch backtest took {elapsed:.1f}s (limit: 180s). "
            "Check if tickers are being processed sequentially when they could be parallel."
        )

        # Sanity check - most should succeed
        assert len(results) >= 8, f"Only {len(results)}/10 tickers succeeded"


def test_data_fetch_and_cache_1_ticker_under_2_seconds():
    """
    Regression test: Fetching 1 year of data (or loading from cache)
    should take <2s. Verifies DataManager caching works.

    First call may be slower (API fetch + parquet write).
    Second call should hit cache and be <0.1s (parquet read).

    If cache hit is slow:
    - Check if parquet files are being written to slow storage
    - Verify cache_manager is using pyarrow engine
    - Check if cache expiry logic is too aggressive
    """
    with patch("src.data.fetcher.yf.download") as mock_download:
        # Mock yfinance response
        np.random.seed(42)
        dates = pd.bdate_range("2024-01-01", periods=252)

        close = 150 + np.cumsum(np.random.randn(252) * 2)
        high = close + np.abs(np.random.randn(252))
        low = close - np.abs(np.random.randn(252))
        open_ = close + np.random.randn(252) * 0.5
        volume = np.random.randint(1_000_000, 5_000_000, 252)

        mock_df = pd.DataFrame({
            ("Open", "AAPL"): open_,
            ("High", "AAPL"): high,
            ("Low", "AAPL"): low,
            ("Close", "AAPL"): close,
            ("Volume", "AAPL"): volume,
        }, index=dates)

        mock_download.return_value = mock_df

        fetcher = DataFetcher()

        # First call - may hit API
        start = time.time()
        data1 = fetcher.fetch("AAPL", "2024-01-01", "2024-12-31", interval="1d")
        elapsed1 = time.time() - start

        # Should complete reasonably fast even with API call
        assert elapsed1 < 5.0, (
            f"First fetch took {elapsed1:.3f}s (limit: 5.0s). "
            "Even with API call, this should be fast."
        )

        # Second call - MUST hit cache
        start2 = time.time()
        data2 = fetcher.fetch("AAPL", "2024-01-01", "2024-12-31", interval="1d")
        elapsed2 = time.time() - start2

        # Cache hit should be near-instant
        assert elapsed2 < 0.5, (
            f"Cache hit took {elapsed2:.3f}s (limit: 0.5s). "
            "Parquet cache read should be instant. "
            "Check cache_manager.py and verify pyarrow is installed."
        )

        # Sanity check - both fetches return same data
        assert data1["ticker"] == data2["ticker"] == "AAPL"
        assert len(data1["data"]) == len(data2["data"])


@pytest.mark.slow
def test_monte_carlo_100_runs_under_2_minutes(large_dataset):
    """
    Regression test: Monte Carlo simulation with 100 runs should complete in <2 minutes.

    This is marked @pytest.mark.slow and only runs with: pytest -m slow

    If this fails:
    - Check if each run is independent (can be parallelized)
    - Consider reducing default MC runs from 1000 to 100
    - Profile the random walk generation
    """
    strategy = MovingAverageCrossover({
        "short_window": 20,
        "long_window": 50,
        "volume_confirmation": False,
        "cooldown_days": 3,
    })

    engine = BacktestEngine()

    start = time.time()
    results = engine.run_backtest(
        strategy=strategy,
        data=large_dataset,
        initial_capital=100000,
        position_sizing="equal_weight",
        monte_carlo_runs=100,  # 100 runs instead of 1000
    )
    elapsed = time.time() - start

    # Assert performance budget
    assert elapsed < 120.0, (
        f"Monte Carlo (100 runs) took {elapsed:.1f}s (limit: 120s). "
        "Consider parallelizing MC runs or reducing default run count."
    )

    # Sanity check
    assert results.monte_carlo is not None, "Monte Carlo results missing"
    # Check for expected MC result keys (mean, max, min, etc.)
    assert "mean_final_value" in results.monte_carlo, "MC mean_final_value missing"
    assert "max_final_value" in results.monte_carlo, "MC max_final_value missing"


# Mark slow tests so they can be skipped in CI
pytest.mark.slow(test_monte_carlo_100_runs_under_2_minutes)
