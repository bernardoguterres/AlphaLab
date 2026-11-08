"""Tests for position sizing with realistic commission rates, flat fees, slippage,
and tight cash boundary conditions.

Verifies that `_calculate_shares()` factors in `portfolio.commission_rate` alongside
`portfolio.slippage_pct` and `portfolio.commission_per_trade`, ensuring buy orders
never get rejected with 'Insufficient funds' while preserving proper position cap
headroom calculations.
"""

import math
import numpy as np
import pandas as pd
import pytest

from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.order import Order, OrderSide, OrderStatus
from alphalab.backtest.portfolio import Portfolio
from alphalab.strategies.base_strategy import BaseStrategy


def _make_ohlcv(prices: list[float], atr_val: float = 2.0) -> pd.DataFrame:
    """Helper to create dummy OHLCV data with ATR for testing."""
    n = len(prices)
    df = pd.DataFrame(
        {
            "Open": prices,
            "High": [p + 1.0 for p in prices],
            "Low": [p - 1.0 for p in prices],
            "Close": prices,
            "Volume": [1000.0] * n,
            "ATR": [atr_val] * n,
        },
        index=pd.date_range("2026-01-01", periods=n, freq="D"),
    )
    df.attrs["ticker"] = "TEST"
    return df


# ===========================================================================
# 1. Equal-Weight Sizing Tests
# ===========================================================================


def test_equal_weight_zero_commission_rate():
    """With zero commission rate and zero slippage, cash divisor is pure price."""
    engine = BacktestEngine()
    p = Portfolio(
        initial_capital=10_000.0,
        commission_rate=0.0,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    data = _make_ohlcv([100.0, 100.0])
    shares = engine._calculate_shares(p, "TEST", 100.0, "equal_weight", data, 1)
    assert shares == 100

    order = Order(ticker="TEST", side=OrderSide.BUY, shares=shares)
    res = p.execute_order(order, {"TEST": 100.0})
    assert res.status == OrderStatus.FILLED
    assert p.cash == 0.0


@pytest.mark.parametrize("comm_rate", [0.001, 0.005, 0.01])
def test_equal_weight_nonzero_commission_rate(comm_rate):
    """Non-zero commission rate scales down shares so total cost <= available cash."""
    engine = BacktestEngine()
    p = Portfolio(
        initial_capital=1_000.0,
        commission_rate=comm_rate,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    price = 100.0
    cost_per_share = price * (1 + comm_rate)
    expected_shares = int(1_000.0 / cost_per_share)

    data = _make_ohlcv([price, price])
    shares = engine._calculate_shares(p, "TEST", price, "equal_weight", data, 1)
    assert shares == expected_shares

    # Execute and verify order is filled without insufficient funds
    order = Order(ticker="TEST", side=OrderSide.BUY, shares=shares)
    res = p.execute_order(order, {"TEST": price})
    assert res.status == OrderStatus.FILLED
    assert res.reason != "Insufficient funds"
    assert p.cash >= 0.0


def test_equal_weight_tight_cash_boundary_rejection_prevention():
    """Under old implementation:
    Cash = $1,000, price = $100, comm_rate = 0.005 (0.5%).
    budget / effective_price = 1000 / 100 = 10 shares.
    Execution cost = 10 * 100 + 10 * 100 * 0.005 = $1005.00 > $1000 -> REJECTED.

    Under fixed implementation:
    budget / cost_per_share = 1000 / 100.5 = 9.95 -> 9 shares.
    Execution cost = 9 * 100 + 9 * 100 * 0.005 = $904.50 <= $1000 -> FILLED.
    """
    engine = BacktestEngine()
    p = Portfolio(
        initial_capital=1_000.0,
        commission_rate=0.005,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    data = _make_ohlcv([100.0, 100.0])
    shares = engine._calculate_shares(p, "TEST", 100.0, "equal_weight", data, 1)
    assert shares == 9

    order = Order(ticker="TEST", side=OrderSide.BUY, shares=shares)
    res = p.execute_order(order, {"TEST": 100.0})
    assert res.status == OrderStatus.FILLED
    assert p.cash == 1_000.0 - 904.50


def test_equal_weight_exact_cost_boundary():
    """Test exact penny boundary where cash exactly equals N * cost_per_share."""
    engine = BacktestEngine()
    price = 100.0
    comm_rate = 0.01  # 1%
    cost_per_share = price * (1 + comm_rate)  # 101.00

    # Exactly enough for 5 shares ($505.00)
    p_exact = Portfolio(
        initial_capital=505.0,
        commission_rate=comm_rate,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    data = _make_ohlcv([price, price])
    shares_exact = engine._calculate_shares(
        p_exact, "TEST", price, "equal_weight", data, 1
    )
    assert shares_exact == 5

    res_exact = p_exact.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=shares_exact), {"TEST": price}
    )
    assert res_exact.status == OrderStatus.FILLED
    assert abs(p_exact.cash) < 1e-9

    # One penny short of 5 shares ($504.99) -> must size down to 4 shares
    p_short = Portfolio(
        initial_capital=504.99,
        commission_rate=comm_rate,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    shares_short = engine._calculate_shares(
        p_short, "TEST", price, "equal_weight", data, 1
    )
    assert shares_short == 4

    res_short = p_short.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=shares_short), {"TEST": price}
    )
    assert res_short.status == OrderStatus.FILLED
    assert res_short.reason != "Insufficient funds"


def test_equal_weight_position_cap_headroom_not_diluted_by_commissions():
    """Position cap headroom divides by effective_price (not cost_per_share),
    because position valuation does not include commissions.
    """
    engine = BacktestEngine()
    # Portfolio equity $50,000, 20% cap = $10,000 max position.
    p = Portfolio(
        initial_capital=50_000.0,
        commission_rate=0.01,  # 1% commission
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=20.0,
    )
    price = 100.0
    data = _make_ohlcv([price, price])
    shares = engine._calculate_shares(p, "TEST", price, "equal_weight", data, 1)

    # Headroom = $10,000. At $100/share, exactly 100 shares.
    # If headroom were divided by cost_per_share ($101), it would erroneously yield 99 shares.
    assert shares == 100

    order = Order(ticker="TEST", side=OrderSide.BUY, shares=shares)
    res = p.execute_order(order, {"TEST": price})
    assert res.status == OrderStatus.FILLED
    assert p.positions["TEST"] == 100
    # Position value = 100 * 100 = $10,000, exactly 20% of initial equity
    assert p.positions["TEST"] * price == 10_000.0


# ===========================================================================
# 2. Volatility-Weighted Sizing Tests
# ===========================================================================


def test_volatility_weighted_zero_vs_nonzero_commission_rate():
    """volatility_weighted sizing respects cost_per_share when cash is the limiting factor."""
    engine = BacktestEngine()

    # Case A: commission_rate = 0.0
    p_zero = Portfolio(
        initial_capital=1_000.0,
        commission_rate=0.0,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
        max_loss_per_trade_pct=100.0,  # ATR won't be the bottleneck
    )
    data = _make_ohlcv([100.0, 100.0], atr_val=1.0)
    shares_zero = engine._calculate_shares(
        p_zero, "TEST", 100.0, "volatility_weighted", data, 1
    )
    assert shares_zero == 10

    # Case B: commission_rate = 0.005 (0.5%)
    p_comm = Portfolio(
        initial_capital=1_000.0,
        commission_rate=0.005,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
        max_loss_per_trade_pct=100.0,
    )
    shares_comm = engine._calculate_shares(
        p_comm, "TEST", 100.0, "volatility_weighted", data, 1
    )
    assert shares_comm == 9

    res = p_comm.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=shares_comm), {"TEST": 100.0}
    )
    assert res.status == OrderStatus.FILLED
    assert res.reason != "Insufficient funds"


def test_volatility_weighted_tight_cash_boundary():
    """Verify tight cash does not reject volatility-weighted orders with 'Insufficient funds'."""
    engine = BacktestEngine()
    p = Portfolio(
        initial_capital=2_000.0,
        commission_rate=0.002,  # 0.2%
        slippage_pct=0.05,  # 0.05%
        cash_reserve_pct=5.0,  # 5% reserve
        max_position_pct=100.0,
        max_loss_per_trade_pct=50.0,
    )
    # Available cash = 2000 * 0.95 = 1900.0
    price = 95.0
    data = _make_ohlcv([price, price], atr_val=0.5)
    shares = engine._calculate_shares(p, "TEST", price, "volatility_weighted", data, 1)
    assert shares > 0

    order = Order(ticker="TEST", side=OrderSide.BUY, shares=shares)
    res = p.execute_order(order, {"TEST": price})
    assert res.status == OrderStatus.FILLED
    assert res.reason != "Insufficient funds"


def test_volatility_weighted_three_constraints():
    """Verify that volatility_weighted respects the minimum of risk-based size,
    cash budget, and position cap headroom.
    """
    engine = BacktestEngine()

    # Constraint 1: Risk-based size is tightest
    # Equity = $10,000, max_loss = 2% ($200), ATR = 5.0 -> stop distance = 10.0 -> 20 shares
    p_risk = Portfolio(
        initial_capital=10_000.0,
        commission_rate=0.001,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
        max_loss_per_trade_pct=2.0,
    )
    data_risk = _make_ohlcv([100.0, 100.0], atr_val=5.0)
    shares_risk = engine._calculate_shares(
        p_risk, "TEST", 100.0, "volatility_weighted", data_risk, 1
    )
    assert shares_risk == 20

    # Constraint 2: Position cap is tightest
    # Equity = $10,000, max_position = 5% ($500), price = 100 -> 5 shares
    p_cap = Portfolio(
        initial_capital=10_000.0,
        commission_rate=0.001,
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=5.0,
        max_loss_per_trade_pct=50.0,
    )
    data_cap = _make_ohlcv([100.0, 100.0], atr_val=0.1)
    shares_cap = engine._calculate_shares(
        p_cap, "TEST", 100.0, "volatility_weighted", data_cap, 1
    )
    assert shares_cap == 5

    # Constraint 3: Cash budget is tightest
    # Initial capital = $10,000, but cash left = $500, max_position = 100%, max_loss = 50%
    # Equity = $500. max_position 100% -> headroom = 500 / 100 = 5 shares.
    # Cash budget = $500. Cost per share = $101.0 -> 4.95 -> 4 shares.
    # ATR = 0.1 -> risk shares = 50% * 500 / 0.2 = 1250 shares.
    # So cash is tightest: min(1250, 4.95, 5.0) = 4 shares.
    p_cash = Portfolio(
        initial_capital=10_000.0,
        commission_rate=0.01,  # 1% comm -> cost per share = $101.0
        slippage_pct=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
        max_loss_per_trade_pct=50.0,
    )
    p_cash.cash = 500.0
    data_cash = _make_ohlcv([100.0, 100.0], atr_val=0.1)
    shares_cash = engine._calculate_shares(
        p_cash, "TEST", 100.0, "volatility_weighted", data_cash, 1
    )
    assert shares_cash == int(500.0 / 101.0)  # 4 shares

    res = p_cash.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=shares_cash), {"TEST": 100.0}
    )
    assert res.status == OrderStatus.FILLED


def test_volatility_weighted_atr_warmup():
    """Without prior ATR, volatility_weighted returns 0 shares (no silent fallback)."""
    engine = BacktestEngine()
    p = Portfolio(initial_capital=10_000.0)
    data = _make_ohlcv([100.0, 100.0], atr_val=2.0)

    # bar_idx = 0: prev = -1 -> no prior bar ATR
    assert (
        engine._calculate_shares(p, "TEST", 100.0, "volatility_weighted", data, 0) == 0
    )

    # ATR column missing entirely
    data_no_atr = data.drop(columns=["ATR"])
    assert (
        engine._calculate_shares(
            p, "TEST", 100.0, "volatility_weighted", data_no_atr, 1
        )
        == 0
    )

    # ATR is NaN
    data_nan = data.copy()
    data_nan.loc[data_nan.index[0], "ATR"] = float("nan")
    assert (
        engine._calculate_shares(p, "TEST", 100.0, "volatility_weighted", data_nan, 1)
        == 0
    )


# ===========================================================================
# 3. Flat USD Fee + Slippage + Commission Rate Interactions
# ===========================================================================


def test_flat_fee_and_proportional_commission_combined():
    """Verify sizing when both flat fee (commission_per_trade) and percentage
    (commission_rate) are active.
    """
    engine = BacktestEngine()
    price = 100.0
    slippage_pct = 0.1  # 0.1% -> 0.001
    comm_rate = 0.005  # 0.5%
    flat_fee = 4.95

    p = Portfolio(
        initial_capital=1_000.0,
        commission_rate=comm_rate,
        slippage_pct=slippage_pct,
        commission_per_trade=flat_fee,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )

    effective_price = price * (1 + slippage_pct / 100)  # 100.10
    cost_per_share = effective_price * (1 + comm_rate)  # 100.10 * 1.005 = 100.6005
    cash_budget = 1_000.0 - flat_fee  # 995.05
    expected_shares = int(cash_budget / cost_per_share)  # 9 shares

    data = _make_ohlcv([price, price])
    shares = engine._calculate_shares(p, "TEST", price, "equal_weight", data, 1)
    assert shares == expected_shares

    order = Order(ticker="TEST", side=OrderSide.BUY, shares=shares)
    res = p.execute_order(order, {"TEST": price})
    assert res.status == OrderStatus.FILLED
    assert res.reason != "Insufficient funds"
    assert p.cash >= 0.0


def test_cash_insufficient_for_flat_fee():
    """If available cash is less than or equal to commission_per_trade, size is 0."""
    engine = BacktestEngine()
    p = Portfolio(
        initial_capital=10.0,
        commission_per_trade=15.0,
        cash_reserve_pct=0.0,
    )
    data = _make_ohlcv([100.0, 100.0])
    shares = engine._calculate_shares(p, "TEST", 100.0, "equal_weight", data, 1)
    assert shares == 0


def test_cash_reserve_pct_with_commissions():
    """Cash reserve floor is strictly respected and never violated by commission."""
    engine = BacktestEngine()
    # 10% reserve on $10,000 cash = $1,000 reserve, $9,000 available
    p = Portfolio(
        initial_capital=10_000.0,
        commission_rate=0.01,  # 1%
        slippage_pct=0.0,
        cash_reserve_pct=10.0,
        max_position_pct=100.0,
    )
    price = 100.0
    cost_per_share = price * 1.01  # 101.0
    expected_shares = int(9_000.0 / 101.0)  # 89 shares

    data = _make_ohlcv([price, price])
    shares = engine._calculate_shares(p, "TEST", price, "equal_weight", data, 1)
    assert shares == expected_shares

    res = p.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=shares), {"TEST": price}
    )
    assert res.status == OrderStatus.FILLED
    # Remaining cash must be >= 10% of remaining cash balance
    assert p.cash >= 10_000.0 - 89 * 101.0
    assert p._can_afford(0.0) is True


# ===========================================================================
# 4. Exhaustive Parameter Matrix Sweep
# ===========================================================================


@pytest.mark.parametrize("sizing", ["equal_weight", "volatility_weighted"])
def test_exhaustive_parameter_sweep_never_insufficient_funds(sizing):
    """Broad parameter sweep across prices, cash amounts, slippages, and commission
    rates to rigorously verify that an order sized by _calculate_shares NEVER gets
    rejected for 'Insufficient funds' or 'Position exceeds limit'.
    """
    engine = BacktestEngine()

    test_prices = [10.0, 50.0, 123.45, 250.0]
    test_cash_levels = [250.0, 1_000.0, 5_000.0, 20_000.0]
    test_comm_rates = [0.0, 0.001, 0.002, 0.005, 0.01]
    test_slippage_pcts = [0.0, 0.05, 0.1]
    test_flat_fees = [0.0, 1.0, 4.95]
    test_reserves = [0.0, 5.0, 10.0]

    for price in test_prices:
        for cash in test_cash_levels:
            for comm_rate in test_comm_rates:
                for slippage in test_slippage_pcts:
                    for flat_fee in test_flat_fees:
                        for reserve in test_reserves:
                            p = Portfolio(
                                initial_capital=cash,
                                commission_rate=comm_rate,
                                slippage_pct=slippage,
                                commission_per_trade=flat_fee,
                                cash_reserve_pct=reserve,
                                max_position_pct=100.0,
                                max_loss_per_trade_pct=10.0,
                            )
                            data = _make_ohlcv([price, price], atr_val=2.0)
                            shares = engine._calculate_shares(
                                p, "SWEEP", price, sizing, data, 1
                            )
                            if shares <= 0:
                                continue

                            order = Order(
                                ticker="SWEEP", side=OrderSide.BUY, shares=shares
                            )
                            res = p.execute_order(order, {"SWEEP": price})
                            assert res.status == OrderStatus.FILLED, (
                                f"Failed on sizing={sizing}, price={price}, cash={cash}, "
                                f"comm_rate={comm_rate}, slippage={slippage}, fee={flat_fee}, "
                                f"reserve={reserve}: {res.reason}"
                            )


# ===========================================================================
# 5. Full Engine End-to-End Simulation
# ===========================================================================


class MockBuyStrategy(BaseStrategy):
    """Strategy that issues BUY on bar 0 and holds."""

    name = "MockBuy"

    def validate_params(self):
        pass

    def required_columns(self) -> list[str]:
        return ["Close"]

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        signals = self._init_signals_frame(df)
        if len(signals) > 1:
            signals.iloc[0, signals.columns.get_loc("signal")] = 1
            signals.iloc[0, signals.columns.get_loc("reason")] = "Test Buy Signal"
        return signals

    def backtest_ready_check(self, df: pd.DataFrame) -> bool:
        return True


def test_full_backtest_simulation_tight_cash_no_rejections():
    """End-to-end backtest simulation through BacktestEngine.run_backtest().
    Verify that with tight cash, slippage, and non-zero commissions, buy orders
    are executed cleanly without 'Insufficient funds' rejections in trades.
    """
    engine = BacktestEngine()
    engine.commission = 0.005  # 0.5%
    engine.slippage = 0.1  # 0.1%

    n_bars = 20
    prices = [100.0 + i * 0.5 for i in range(n_bars)]
    data = _make_ohlcv(prices, atr_val=1.5)

    risk_settings = {
        "commission_per_trade": 5.0,
        "max_position_size_pct": 100.0,
        "cash_reserve_pct": 5.0,
    }

    results = engine.run_backtest(
        strategy=MockBuyStrategy(),
        data=data,
        initial_capital=1_000.0,
        position_sizing="equal_weight",
        risk_settings=risk_settings,
    )

    assert results.final_value > 0
    # Exactly one filled trade, zero rejected trades
    rejected = [t for t in results.trades if t.get("status") == "rejected"]
    filled = [t for t in results.trades if t.get("status") == "filled"]
    assert len(rejected) == 0, f"Found unexpected rejected orders: {rejected}"
    assert len(filled) >= 1
    assert filled[0]["shares"] > 0
