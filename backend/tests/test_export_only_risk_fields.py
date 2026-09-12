"""Regression tests establishing exactly which RiskSettings fields
AlphaLab's backtest engine simulates vs. which are export-only (accepted,
validated, exported to AlphaLive unchanged, but never touching AlphaLab's
own returns/trades/metrics).

See RiskSettings' docstring (alphalab/api/validators.py) and RiskConfig's
Field descriptions (strategy_schema.py) for the same classification stated
as documentation - these tests make it a checked fact, not just a comment.
"""

import pandas as pd
import pytest

from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.order import Order, OrderSide
from alphalab.backtest.portfolio import Portfolio
from helpers import make_featured_data
from alphalab.strategies.implementations.moving_average_crossover import (
    MovingAverageCrossover,
)


def _data(n=300):
    d = make_featured_data(n=n)
    d.attrs["ticker"] = "TEST"
    return d


class TestExportOnlyFieldsDoNotAffectAlphaLabResults:
    """max_daily_loss_pct, max_open_positions, and commission_per_trade are
    accepted in risk_settings but BacktestEngine._simulate() deliberately
    never reads them into Portfolio - varying them must produce byte-for-byte
    identical simulation output."""

    def _run(self, risk_settings):
        data = _data()
        strategy = MovingAverageCrossover({"short_window": 10, "long_window": 30})
        engine = BacktestEngine()
        return engine.run_backtest(
            strategy,
            data,
            initial_capital=10_000,
            risk_settings=risk_settings,
        )

    def test_commission_per_trade_is_a_no_op(self):
        base = self._run({"stop_loss_pct": 2.0, "commission_per_trade": 0.0})
        varied = self._run({"stop_loss_pct": 2.0, "commission_per_trade": 25.0})
        assert base.final_value == varied.final_value
        assert base.trades == varied.trades

    def test_max_daily_loss_pct_is_a_no_op(self):
        base = self._run({"stop_loss_pct": 2.0, "max_daily_loss_pct": 3.0})
        varied = self._run({"stop_loss_pct": 2.0, "max_daily_loss_pct": 0.5})
        assert base.final_value == varied.final_value
        assert base.trades == varied.trades

    def test_max_open_positions_is_a_no_op(self):
        base = self._run({"stop_loss_pct": 2.0, "max_open_positions": 5})
        varied = self._run({"stop_loss_pct": 2.0, "max_open_positions": 1})
        assert base.final_value == varied.final_value
        assert base.trades == varied.trades


class TestPercentageCommissionStillAffectsResults:
    """The engine's own percentage-of-notional commission
    (config.yaml's backtest.commission, threaded into Portfolio's
    commission_rate) is a real, simulated cost - distinct from the
    export-only flat commission_per_trade above."""

    def test_nonzero_commission_rate_reduces_fill_proceeds(self):
        p_free = Portfolio(initial_capital=10_000, slippage_pct=0, commission_rate=0)
        p_paid = Portfolio(
            initial_capital=10_000, slippage_pct=0, commission_rate=0.01
        )  # 1% per fill
        for p in (p_free, p_paid):
            order = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
            p.execute_order(order, {"AAPL": 100.0})

        assert p_paid.cash < p_free.cash, (
            "a nonzero percentage commission_rate must cost more cash on the "
            "same fill than a zero rate"
        )

    def test_commission_charged_once_per_fill_not_twice(self):
        p = Portfolio(initial_capital=10_000, slippage_pct=0, commission_rate=0.01)
        buy = Order(ticker="AAPL", side=OrderSide.BUY, shares=10)
        p.execute_order(buy, {"AAPL": 100.0})
        # 10 shares * $100 = $1000 notional; 1% commission = $10, once.
        expected_commission = 10.0
        assert buy.commission == pytest.approx(expected_commission)
        # cash spent = notional + commission, not notional + 2x commission
        expected_cash = 10_000 - (1000.0 + expected_commission)
        assert p.cash == pytest.approx(expected_cash)

        sell = Order(ticker="AAPL", side=OrderSide.SELL, shares=10)
        p.execute_order(sell, {"AAPL": 100.0})
        # Round trip: commission charged on the buy AND the sell (2x total,
        # matching CLAUDE.md's documented "commission applied 2x per round
        # trip"), never more than once per individual fill.
        assert sell.commission == pytest.approx(expected_commission)


class TestUnsupportedSettingsFailClearly:
    def test_portfolio_has_no_flat_fee_commission_parameter(self):
        """Portfolio's only commission knob is commission_rate, a
        percentage-of-notional fraction - there is deliberately no separate
        flat-fee kwarg a caller could pass commission_per_trade into. Passing
        one must fail loudly (TypeError), not be silently accepted and
        ignored."""
        with pytest.raises(TypeError):
            Portfolio(initial_capital=10_000, commission_per_trade=5.0)

    def test_a_commission_rate_large_enough_to_exceed_cash_is_rejected(self):
        """commission_rate is unambiguously a percentage-of-notional
        fraction, not a flat USD amount - a rate large enough that its cost
        exceeds available cash is correctly rejected as unaffordable, the
        same as any other fee that blows the cash reserve."""
        p = Portfolio(
            initial_capital=1_000,
            slippage_pct=0,
            commission_rate=50.0,  # 5000% - deliberately absurd as a rate
            cash_reserve_pct=0,
        )
        order = Order(ticker="AAPL", side=OrderSide.BUY, shares=1)
        result = p.execute_order(order, {"AAPL": 100.0})
        assert result.status.value == "rejected"
