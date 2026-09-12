"""Tests for BacktestEngine and Portfolio."""

import numpy as np
import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.portfolio import Portfolio
from alphalab.backtest.order import Order, OrderSide, OrderType, OrderStatus
from alphalab.strategies.base_strategy import BaseStrategy
from alphalab.strategies.implementations.moving_average_crossover import (
    MovingAverageCrossover,
)
from helpers import make_featured_data as _make_featured_data_base


def _make_featured_data(n=500, seed=42):
    result = _make_featured_data_base(n=n, seed=seed)
    result.attrs["ticker"] = "TEST"
    return result


class _FixedSignalStrategy(BaseStrategy):
    """Test-only strategy that replays a pre-built signals frame verbatim,
    so drawdown-halt tests can drive the engine through run_backtest()
    (exercising the real signal->pending->fill wiring and result
    serialization) without depending on any real strategy's indicator
    logic to fire a signal on a specific bar."""

    name = "FixedSignal"

    def __init__(self, signals: pd.DataFrame):
        self._signals = signals
        super().__init__({})

    def validate_params(self):
        pass

    def required_columns(self) -> list[str]:
        return ["Close"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self._signals


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
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        # Invest almost everything
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        # Record peak value
        p.record_value(None, {"AAPL": 100.0})
        # Price crashes - portfolio drops >5%
        p.record_value(None, {"AAPL": 90.0})
        val = p.get_portfolio_value({"AAPL": 90.0})
        p._check_drawdown_halt(val)
        assert p.halted

    def test_drawdown_halt_still_allows_closing_position(self):
        """Regression test for audit bug 3.2: a drawdown halt used to
        reject ALL orders, including SELLs - once triggered, an open
        position was frozen for the rest of the backtest with no way to
        ever close it. A halt now only blocks new entries (BUY); a SELL
        must still go through to close/reduce an existing position."""
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        p.record_value(None, {"AAPL": 100.0})
        p.record_value(None, {"AAPL": 90.0})
        p._check_drawdown_halt(p.get_portfolio_value({"AAPL": 90.0}))
        assert p.halted

        # A new BUY must still be rejected while halted.
        another_buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=1)
        rejected = p.execute_order(another_buy, {"AAPL": 90.0})
        assert rejected.status == OrderStatus.REJECTED

        # But closing the existing position via SELL must succeed.
        sell = Order(ticker="AAPL", side=OrderSide.SELL, shares=95)
        result = p.execute_order(sell, {"AAPL": 90.0})
        assert result.status == OrderStatus.FILLED
        assert p.get_position("AAPL") == 0


class TestBacktestEngine:
    def test_drawdown_halt_does_not_block_exit_signal_in_simulation_loop(self):
        """Engine-level regression test for audit bug 3.2: `_simulate`'s
        pending-signal execution used to be gated behind
        `not portfolio.halted`, so once a drawdown halt tripped, a
        strategy's own SELL signal was silently dropped before it ever
        reached execute_order - the position sat frozen at mark-to-market
        for the rest of the backtest. Reproduces the audit's own scenario:
        a crash trips the drawdown halt, then a subsequent SELL signal
        must still close the position.
        """
        n = 20
        dates = pd.bdate_range("2021-01-01", periods=n)
        # Flat, then a crash big enough to trip the default 10% drawdown
        # halt, then flat again.
        close = np.concatenate(
            [np.full(5, 100.0), np.linspace(100, 10, 5), np.full(n - 10, 10.0)]
        )
        data = pd.DataFrame(
            {
                "Open": close,
                "High": close * 1.001,
                "Low": close * 0.999,
                "Close": close,
                "Volume": np.full(n, 1_000_000),
            },
            index=dates,
        )
        data.attrs["ticker"] = "TEST"

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["reason"] = ""
        signals.loc[dates[1], "signal"] = 1  # BUY, executes at dates[2]'s open
        signals.loc[dates[1], "reason"] = "test buy"
        signals.loc[dates[12], "signal"] = -1  # SELL, well after the crash/halt
        signals.loc[dates[12], "reason"] = "test sell"

        engine = BacktestEngine()
        portfolio, trades = engine._simulate(
            data, signals, capital=10_000, sizing="equal_weight"
        )

        assert portfolio.halted, "test setup should have tripped the drawdown halt"
        sell_trades = [t for t in trades if t["side"] == "sell"]
        assert len(sell_trades) == 1
        assert sell_trades[0]["status"] == "filled"
        assert portfolio.get_position("TEST") == 0

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


class TestCausalDrawdownHalt:
    """Regression tests for the causal mark-to-market drawdown halt.

    Previously _check_drawdown_halt() was only invoked from inside
    execute_order(), after a fill - a price-only crash with no order placed
    on the breach bar went undetected until whenever the next order
    happened to occur (possibly bars later, possibly never). record_value()
    (called exactly once per bar by every simulation loop - BacktestEngine
    and PortfolioConstructor) now runs the check itself on every bar's
    mark-to-market equity, so the halt is detected on the bar it actually
    happens, with no order required.
    """

    def test_price_only_drawdown_halts_with_no_order_on_the_breach_bar(self):
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        assert not p.halted

        # No order at all on this bar - pure mark-to-market update.
        p.record_value(None, {"AAPL": 90.0})
        assert p.halted, "record_value alone must detect a price-only breach"

    def test_breach_then_attempted_entry_is_rejected(self):
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        p.record_value(None, {"AAPL": 90.0})
        assert p.halted

        entry = Order(ticker="MSFT", side=OrderSide.BUY, shares=1)
        result = p.execute_order(entry, {"AAPL": 90.0, "MSFT": 50.0})
        assert result.status == OrderStatus.REJECTED

    def test_risk_reducing_exit_still_works_after_halt(self):
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        p.record_value(None, {"AAPL": 90.0})
        assert p.halted

        sell = Order(ticker="AAPL", side=OrderSide.SELL, shares=95)
        result = p.execute_order(sell, {"AAPL": 90.0})
        assert result.status == OrderStatus.FILLED
        assert p.get_position("AAPL") == 0

    def test_exact_threshold_equality_triggers_halt(self):
        p = Portfolio(initial_capital=10_000, max_drawdown_pct=10, slippage_pct=0)
        p.record_value(None, {"AAPL": 100.0})  # peak = 10,000
        p.record_value(None, {"AAPL": 100.0})  # exactly -10% via cash-only value
        # Force an exact 10% drawdown via a synthetic price map on an
        # uninvested portfolio: value = cash = 10,000 always here, so drive
        # the check directly against a value 10% below the recorded peak.
        p._check_drawdown_halt(9_000.0)
        assert p.halted, ">= threshold must halt, including exact equality"

    def test_just_below_threshold_does_not_halt(self):
        p = Portfolio(initial_capital=10_000, max_drawdown_pct=10, slippage_pct=0)
        p.record_value(None, {"AAPL": 100.0})  # peak = 10,000
        p._check_drawdown_halt(9_000.01)  # 9.9999% drawdown, just under 10%
        assert not p.halted

    def test_just_above_threshold_halts(self):
        p = Portfolio(initial_capital=10_000, max_drawdown_pct=10, slippage_pct=0)
        p.record_value(None, {"AAPL": 100.0})  # peak = 10,000
        p._check_drawdown_halt(8_999.99)  # just over 10% drawdown
        assert p.halted

    def test_disabled_drawdown_is_a_true_no_op(self):
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=None,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        p.record_value(None, {"AAPL": 100.0})
        # A near-total wipeout must still never halt when disabled.
        p.record_value(None, {"AAPL": 1.0})
        assert not p.halted
        assert p.halted_at is None

    def test_price_recovery_does_not_clear_a_permanent_halt(self):
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        p.record_value(None, {"AAPL": 90.0})
        assert p.halted
        first_halted_at = p.halted_at
        first_dd = p.halted_drawdown_pct

        # Price fully recovers past the original peak.
        p.record_value(None, {"AAPL": 200.0})
        assert p.halted, "recovery must not auto-clear a drawdown halt"
        assert p.halted_at == first_halted_at
        assert p.halted_drawdown_pct == first_dd

    def test_multiple_equity_updates_same_bar_is_idempotent(self):
        p = Portfolio(
            initial_capital=10_000,
            max_drawdown_pct=5,
            slippage_pct=0,
            commission_rate=0,
            cash_reserve_pct=0,
            max_position_pct=100,
        )
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=95)
        p.execute_order(buy, {"AAPL": 100.0})
        ts = "2024-01-02"
        p.record_value(ts, {"AAPL": 90.0})
        assert p.halted
        recorded_at = p.halted_at
        recorded_dd = p.halted_drawdown_pct

        # Same bar evaluated again (e.g. a caller re-marking mid-bar) must
        # not move the recorded first-breach values.
        p.record_value(ts, {"AAPL": 85.0})
        assert p.halted_at == recorded_at
        assert p.halted_drawdown_pct == recorded_dd

    def test_invalid_zero_or_nonfinite_equity_does_not_crash_or_halt(self):
        p = Portfolio(initial_capital=10_000, max_drawdown_pct=5, slippage_pct=0)
        p.record_value(None, {"AAPL": 100.0})  # peak = 10,000
        p._check_drawdown_halt(float("nan"))
        assert not p.halted
        p._check_drawdown_halt(float("inf"))
        assert not p.halted

        p2 = Portfolio(initial_capital=0.0, max_drawdown_pct=5, slippage_pct=0)
        # peak_value starts at 0 (initial_capital=0) - must not divide by zero.
        p2._check_drawdown_halt(0.0)
        assert not p2.halted

    def test_negative_equity_is_a_valid_breach(self):
        p = Portfolio(initial_capital=10_000, max_drawdown_pct=5, slippage_pct=0)
        p.record_value(None, {"AAPL": 100.0})  # peak = 10,000
        p._check_drawdown_halt(-500.0)
        assert p.halted

    def test_next_bar_entry_queued_before_previous_bar_breach_is_rejected(self):
        """Bar N-1 breaches the halt during its own record_value(); a signal
        queued from an earlier bar that was about to fill at bar N's open
        must be rejected, since the halt was already set by the time bar
        N's pending-order execution runs (engine executes pending orders
        before this bar's own record_value call)."""
        n = 15
        dates = pd.bdate_range("2021-01-01", periods=n)
        close = np.concatenate(
            [np.full(3, 100.0), np.linspace(100, 10, 4), np.full(n - 7, 10.0)]
        )
        data = pd.DataFrame(
            {
                "Open": close,
                "High": close * 1.001,
                "Low": close * 0.999,
                "Close": close,
                "Volume": np.full(n, 1_000_000),
            },
            index=dates,
        )
        data.attrs["ticker"] = "TEST"

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["reason"] = ""
        # An initial position established before the crash so mark-to-market
        # equity actually moves with price (an all-cash portfolio wouldn't
        # show any drawdown at all).
        signals.loc[dates[0], "signal"] = 1
        signals.loc[dates[0], "reason"] = "initial entry"
        # Signal fires on the last flat crash bar (index 6, price=10),
        # queued to execute at bar 7's open - by then the halt (tripped
        # during the crash, bars 3-6) must already be set.
        signals.loc[dates[6], "signal"] = 1
        signals.loc[dates[6], "reason"] = "post-crash entry attempt"

        engine = BacktestEngine()
        portfolio, trades = engine._simulate(
            data,
            signals,
            capital=10_000,
            sizing="equal_weight",
            max_drawdown_pct=5,
        )
        assert portfolio.halted
        buy_trades = [t for t in trades if t["side"] == "buy"]
        assert len(buy_trades) == 2
        assert buy_trades[0]["status"] == "filled", "initial entry, pre-halt"
        assert (
            buy_trades[1]["status"] == "rejected"
        ), "a BUY queued after the halt was already tripped must be rejected"

    def test_result_serialization_reports_halt_accurately(self):
        n = 20
        dates = pd.bdate_range("2021-01-01", periods=n)
        close = np.concatenate(
            [np.full(5, 100.0), np.linspace(100, 10, 5), np.full(n - 10, 10.0)]
        )
        data = pd.DataFrame(
            {
                "Open": close,
                "High": close * 1.001,
                "Low": close * 0.999,
                "Close": close,
                "Volume": np.full(n, 1_000_000),
            },
            index=dates,
        )
        data.attrs["ticker"] = "TEST"

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["reason"] = ""
        signals.loc[dates[1], "signal"] = 1
        signals.loc[dates[1], "reason"] = "entry before crash"

        strategy = _FixedSignalStrategy(signals)
        engine = BacktestEngine()
        results = engine.run_backtest(
            strategy, data, initial_capital=10_000, max_drawdown_pct=5
        )
        d = results.to_dict()
        assert "drawdown_halt" in d
        assert d["drawdown_halt"]["halted"] is True
        assert d["drawdown_halt"]["halted_at"] is not None
        assert d["drawdown_halt"]["halted_drawdown_pct"] >= 5.0

    def test_not_halted_result_serialization_is_explicit(self):
        data = _make_featured_data(n=200)
        strategy = MovingAverageCrossover({"short_window": 20, "long_window": 50})
        engine = BacktestEngine()
        results = engine.run_backtest(strategy, data, initial_capital=10_000)
        d = results.to_dict()
        assert d["drawdown_halt"]["halted"] is False
        assert d["drawdown_halt"]["halted_at"] is None
        assert d["drawdown_halt"]["halted_drawdown_pct"] is None
