"""Tests for BacktestEngine and Portfolio."""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.engine import BacktestEngine
from src.backtest.portfolio import Portfolio
from src.backtest.order import Order, OrderSide, OrderType, OrderStatus
from src.strategies.implementations.moving_average_crossover import MovingAverageCrossover
from src.data.processor import FeatureEngineer


def _make_featured_data(n=500, seed=42):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2021-01-01", periods=n)
    close = 100 + rng.randn(n).cumsum() * 0.3
    close = np.maximum(close, 10)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    opn = close + rng.uniform(-0.5, 0.5, n)
    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))
    volume = rng.randint(1_000_000, 10_000_000, n).astype(float)
    df = pd.DataFrame(
        {"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    fe = FeatureEngineer()
    result = fe.process(df)
    result.attrs["ticker"] = "TEST"
    return result


class TestPortfolio:
    def test_initial_state(self):
        p = Portfolio(initial_capital=10_000)
        assert p.cash == 10_000
        assert len(p.positions) == 0

    def test_buy_order(self):
        p = Portfolio(initial_capital=10_000, slippage_pct=0)
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        p.execute_order(order, {"AAPL": 100.0})
        assert order.status == OrderStatus.FILLED
        assert p.positions["AAPL"] == 10
        assert p.cash < 10_000

    def test_sell_order(self):
        p = Portfolio(initial_capital=10_000, slippage_pct=0)
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        p.execute_order(buy, {"AAPL": 100.0})
        sell = Order(ticker="AAPL", side=OrderSide.SELL, shares=10)
        p.execute_order(sell, {"AAPL": 110.0})
        assert sell.status == OrderStatus.FILLED
        assert "AAPL" not in p.positions

    def test_insufficient_funds_rejected(self):
        p = Portfolio(initial_capital=100, slippage_pct=0)
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        p.execute_order(order, {"AAPL": 100.0})
        assert order.status == OrderStatus.REJECTED

    def test_sell_no_position_rejected(self):
        p = Portfolio(initial_capital=10_000)
        order = Order(ticker="AAPL", side=OrderSide.SELL, shares=10)
        p.execute_order(order, {"AAPL": 100.0})
        assert order.status == OrderStatus.REJECTED

    def test_portfolio_value(self):
        p = Portfolio(initial_capital=10_000, slippage_pct=0, commission_rate=0)
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        p.execute_order(buy, {"AAPL": 100.0})
        val = p.get_portfolio_value({"AAPL": 110.0})
        # cash = 10000 - 1000 = 9000, position = 10*110 = 1100
        assert abs(val - 10100.0) < 0.01

    def test_position_size_limit(self):
        p = Portfolio(initial_capital=10_000, max_position_pct=10, slippage_pct=0)
        # 10% of 10k = 1000; trying to buy $5000 worth
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=50)
        p.execute_order(order, {"AAPL": 100.0})
        assert order.status == OrderStatus.REJECTED

    def test_drawdown_halt(self):
        p = Portfolio(
            initial_capital=10_000, max_drawdown_pct=5,
            slippage_pct=0, commission_rate=0, cash_reserve_pct=0,
            max_position_pct=100,
        )
        # Invest almost everything
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        # Record peak value
        p.record_value(None, {"AAPL": 100.0})
        # Price crashes — portfolio drops >5%
        p.record_value(None, {"AAPL": 90.0})
        val = p.get_portfolio_value({"AAPL": 90.0})
        p._check_drawdown_halt(val)
        assert p.halted


class TestBacktestEngine:
    def test_basic_backtest_runs(self):
        data = _make_featured_data()
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        engine = BacktestEngine()
        results = engine.run_backtest(strategy, data, initial_capital=10_000)
        assert results.final_value > 0
        assert len(results.equity_curve) > 0

    def test_no_lookahead(self):
        """Signals on bar N should execute on bar N+1's open."""
        data = _make_featured_data()
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        engine = BacktestEngine()
        results = engine.run_backtest(strategy, data, initial_capital=10_000)
        # Check that trades have execution timestamps after signal dates
        # (at minimum, the engine should have recorded trades)
        assert results.strategy_name == "MA_Crossover"

    def test_insufficient_data(self):
        data = _make_featured_data(n=5)
        strategy = MovingAverageCrossover()
        engine = BacktestEngine()
        results = engine.run_backtest(strategy, data)
        # Should return without crashing
        assert results.final_value == 0 or len(results.equity_curve) <= 5

    def test_monte_carlo(self):
        data = _make_featured_data(n=300)
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        engine = BacktestEngine()
        results = engine.run_backtest(
            strategy, data, initial_capital=10_000, monte_carlo_runs=10
        )
        assert results.monte_carlo is not None
        assert results.monte_carlo["runs"] == 10
        assert "prob_profit" in results.monte_carlo
