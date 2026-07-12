"""Tests for the equal-weight benchmark (full universe, no ranking)."""

import numpy as np
import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.equal_weight_benchmark import equal_weight_benchmark


def _make_price_data(tickers, n=60, seed=42):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2021-01-01", periods=n, freq="W-FRI")
    data = {}
    for t in tickers:
        rets = rng.normal(0.001, 0.02, n)
        close = 100 * np.cumprod(1 + rets)
        data[t] = pd.DataFrame({"Close": close}, index=dates)
    return data


class TestEqualWeightBenchmark:
    def test_holds_every_ticker_in_universe(self):
        price_data = _make_price_data(["A", "B", "C", "D"])
        result = equal_weight_benchmark(price_data, rebalance_period_bars=52)
        assert set(result.tickers_used) == {"A", "B", "C", "D"}

    def test_equal_weight_across_whole_universe_not_just_a_subset(self):
        price_data = _make_price_data(["A", "B", "C", "D", "E"])
        result = equal_weight_benchmark(price_data, rebalance_period_bars=52)

        first_date = result.rebalance_history[0].date
        first_batch = [r for r in result.rebalance_history if r.date == first_date]
        assert len(first_batch) == 5
        for r in first_batch:
            assert r.target_weight == pytest.approx(1.0 / 5)

    def test_respects_rebalance_period(self):
        price_data = _make_price_data(["A", "B"], n=120)
        result = equal_weight_benchmark(price_data, rebalance_period_bars=52)
        rebalance_dates = sorted(set(r.date for r in result.rebalance_history))
        assert len(rebalance_dates) == 3  # bars 0, 52, 104

    def test_uses_real_costs(self):
        # commission_rate=1.0 (100% of notional) or slippage_pct near 100
        # makes Portfolio's own affordability check REJECT the order
        # entirely rather than execute it at a worse price - use a large
        # but still-fillable slippage instead to prove costs are applied.
        price_data = _make_price_data(["A", "B"], n=10)
        result = equal_weight_benchmark(
            price_data, rebalance_period_bars=52, slippage_pct=5.0
        )
        # With 5% slippage on entry, first-bar equity should drop below
        # initial capital (costs paid on entry, no time for the position to
        # have moved yet).
        assert result.equity_curve[0]["value"] < 100_000.0

    def test_returns_portfolio_constructor_result_shape(self):
        price_data = _make_price_data(["A", "B"])
        result = equal_weight_benchmark(price_data, rebalance_period_bars=52)
        assert result.final_portfolio is not None
        assert len(result.equity_curve) == 60
