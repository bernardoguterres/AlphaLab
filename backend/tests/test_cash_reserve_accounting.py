"""Regression and edge-case tests for cash reserve accounting, next-bar execution causality,
slippage/commission calculations, and drawdown halt enforcement.
"""

import numpy as np
import pandas as pd
import pytest

from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.order import Order, OrderSide, OrderStatus
from alphalab.backtest.portfolio import Portfolio

# ---------------------------------------------------------------------------
# 1. Cash reserve floors and boundary accounting
# ---------------------------------------------------------------------------


def test_portfolio_can_afford_with_cash_below_initial_capital_reserve():
    """If initial capital was $100,000, 5% is $5,000.
    If the portfolio holds positions and has $4,000 in cash left,
    it should still be able to buy $2,000 worth of shares (reserving 5% of remaining cash, i.e. $200).
    Under the old bug, reserve was 5% of initial_capital ($5,000), so cash ($4,000) could never afford anything.
    """
    p = Portfolio(initial_capital=100_000.0, cash_reserve_pct=5.0)
    p.cash = 4_000.0

    # Buying $2,000 of stock should be affordable (cash reserve on $4,000 is $200, available $3,800)
    assert p._can_afford(2_000.0) is True


def test_cash_reserve_concrete_boundary_10k_initial_1k_cash_10pct_reserve():
    """Concrete example requested in engineering pass:
    - Initial capital: $10,000
    - Current cash: $1,000
    - Reserve setting: 10% (cash_reserve_pct=10.0)

    Under previous implementation:
        reserve = initial_capital * 10% = $1,000
        allowed spend = current_cash - reserve = 1,000 - 1,000 = $0.00
        (Any buy order, even for $1, was rejected)

    Under overnight implementation:
        reserve = current_cash * 10% = 1,000 * 0.10 = $100.00
        allowed spend = current_cash - reserve = 1,000 - 100 = $900.00
    """
    p = Portfolio(
        initial_capital=10_000.0,
        cash_reserve_pct=10.0,
        slippage_pct=0.0,
        commission_rate=0.0,
        max_position_pct=100.0,
    )
    p.cash = 1_000.0

    # Test exact boundary:
    # 1. Exact $900.00 spend is allowed (remaining cash = $100.00 >= $100.00 reserve)
    assert p._can_afford(900.0) is True

    # 2. $900.01 spend is rejected (remaining cash = $99.99 < $100.00 reserve)
    assert p._can_afford(900.01) is False

    # 3. Execution boundary via execute_order
    order_exact = Order(ticker="TEST", side=OrderSide.BUY, shares=9)
    res_exact = p.execute_order(order_exact, {"TEST": 100.0})
    assert res_exact.status == OrderStatus.FILLED
    assert p.cash == 100.0  # Exactly at the 10% reserve threshold ($100 left)


def test_cash_reserve_boundary_with_fees_and_commission():
    """Boundary test with flat USD fee and percentage commission rate:
    - Current cash: $1,000
    - Reserve: 10% ($100 reserved, max spend $900)
    - Flat fee: $5.00 per trade
    - Commission rate: 1% (0.01)
    - Buying shares at $100:
        cost per share = 100 * 1.01 = 101.00
        total cost for N shares = N * 101.00 + 5.00
        For 8 shares: cost = 8 * 101.00 + 5.00 = 808.00 + 5.00 = $813.00 <= $900.00 (allowed)
        For 9 shares: cost = 9 * 101.00 + 5.00 = 909.00 + 5.00 = $914.00 > $900.00 (rejected)
    """
    p = Portfolio(
        initial_capital=10_000.0,
        cash_reserve_pct=10.0,
        slippage_pct=0.0,
        commission_rate=0.01,
        commission_per_trade=5.0,
        max_position_pct=100.0,
    )
    p.cash = 1_000.0

    # 8 shares costs $813.00 -> affordable
    assert p._can_afford(813.0) is True
    res8 = p.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=8), {"TEST": 100.0}
    )
    assert res8.status == OrderStatus.FILLED
    assert p.cash == 1_000.0 - 813.0  # $187.00 remaining

    # Reset cash to $1,000 and try 9 shares ($914.00) -> rejected as exceeding $900 budget
    p2 = Portfolio(
        initial_capital=10_000.0,
        cash_reserve_pct=10.0,
        slippage_pct=0.0,
        commission_rate=0.01,
        commission_per_trade=5.0,
        max_position_pct=100.0,
    )
    p2.cash = 1_000.0
    assert p2._can_afford(914.0) is False
    res9 = p2.execute_order(
        Order(ticker="TEST", side=OrderSide.BUY, shares=9), {"TEST": 100.0}
    )
    assert res9.status == OrderStatus.REJECTED
    assert res9.reason == "Insufficient funds"


def test_calculate_shares_includes_commission_rate():
    """_calculate_shares should account for commission_rate so execution does not exceed available cash."""
    engine = BacktestEngine()
    p = Portfolio(
        initial_capital=10_000.0,
        commission_rate=0.01,
        slippage_pct=0.0,
        cash_reserve_pct=5.0,
    )
    data = pd.DataFrame({"Close": [100.0], "Open": [100.0]})
    shares = engine._calculate_shares(p, "TEST", 100.0, "equal_weight", data, 0)
    total_cost = shares * 100.0 * 1.01
    assert total_cost <= p.cash * (1 - p.cash_reserve_pct)


def test_cash_reserve_floor_zero_percent():
    """With cash_reserve_pct=0.0, the reserve is $0 and entire cash balance is spendable."""
    p = Portfolio(
        initial_capital=1_000.0,
        cash_reserve_pct=0.0,
        slippage_pct=0.0,
        commission_rate=0.0,
    )
    assert p._can_afford(1_000.0) is True
    assert p._can_afford(1_000.01) is False


def test_cash_reserve_floor_100_percent():
    """With cash_reserve_pct=100.0, reserve equals entire cash balance, so no spending is allowed."""
    p = Portfolio(
        initial_capital=1_000.0,
        cash_reserve_pct=100.0,
        slippage_pct=0.0,
        commission_rate=0.0,
    )
    assert p._can_afford(0.0) is True
    assert p._can_afford(0.01) is False


def test_cash_reserve_ratchet_and_replenishment():
    """Successive buys ratchet cash down to reserve floors; selling replenishes cash and restores buying power."""
    p = Portfolio(
        initial_capital=10_000.0,
        cash_reserve_pct=10.0,
        slippage_pct=0.0,
        commission_rate=0.0,
        max_position_pct=100.0,
    )
    # Buy 1: Spend $9,000 on 90 shares of A @ $100 -> cash = $1,000, reserve = $100
    res1 = p.execute_order(
        Order(ticker="A", side=OrderSide.BUY, shares=90), {"A": 100.0}
    )
    assert res1.status == OrderStatus.FILLED
    assert p.cash == 1_000.0

    # Buy 2: Spend $900 on 9 shares of B @ $100 -> cash = $100, reserve = $10
    res2 = p.execute_order(
        Order(ticker="B", side=OrderSide.BUY, shares=9), {"B": 100.0}
    )
    assert res2.status == OrderStatus.FILLED
    assert p.cash == 100.0

    # Buy 3: Attempting to spend $95 on 1 share of C @ $95 exceeds available $90 -> rejected
    res3 = p.execute_order(Order(ticker="C", side=OrderSide.BUY, shares=1), {"C": 95.0})
    assert res3.status == OrderStatus.REJECTED
    assert res3.reason == "Insufficient funds"

    # Sell 90 shares of A @ $100 -> cash = $100 + $9,000 = $9,100, reserve = $910, available = $8,190
    res_sell = p.execute_order(
        Order(ticker="A", side=OrderSide.SELL, shares=90), {"A": 100.0}
    )
    assert res_sell.status == OrderStatus.FILLED
    assert p.cash == 9_100.0

    # Buy 4: Can now afford 80 shares of C @ $100 ($8,000 <= $8,190) -> filled
    res4 = p.execute_order(
        Order(ticker="C", side=OrderSide.BUY, shares=80), {"C": 100.0}
    )
    assert res4.status == OrderStatus.FILLED
    assert p.cash == 1_100.0


def test_cash_reserve_zero_cash_boundary():
    """Zero cash cannot afford any positive purchase."""
    p = Portfolio(initial_capital=1_000.0, cash_reserve_pct=5.0)
    p.cash = 0.0
    assert p._can_afford(0.0) is True
    assert p._can_afford(0.01) is False


# ---------------------------------------------------------------------------
# 2. Next-bar execution causality
# ---------------------------------------------------------------------------


class _SingleSignalStrategy:
    """Strategy helper that emits a single BUY on a specified bar index."""

    def __init__(self, target_bar_idx: int):
        self.target_bar_idx = target_bar_idx
        self.name = "single_signal"

    def backtest_ready_check(self, df):
        return True

    def generate_signals(self, df):
        s = pd.DataFrame(index=df.index)
        s["signal"] = 0
        s["reason"] = ""
        if 0 <= self.target_bar_idx < len(df):
            s.iloc[self.target_bar_idx, s.columns.get_loc("signal")] = 1
            s.iloc[self.target_bar_idx, s.columns.get_loc("reason")] = "entry_signal"
        return s


def test_next_bar_execution_causality_uses_next_open_price():
    """Signals generated on bar T close MUST execute causally at bar T+1 open price."""
    n = 12
    dates = pd.bdate_range("2024-01-02", periods=n)
    # Bar 0: Open=100, Close=102.
    # Bar 1: Open=110, Close=115.
    opens = np.full(n, 100.0)
    opens[1] = 110.0
    closes = np.full(n, 102.0)
    closes[1] = 115.0

    df = pd.DataFrame(
        {
            "Open": opens,
            "High": np.maximum(opens, closes) + 1.0,
            "Low": np.minimum(opens, closes) - 1.0,
            "Close": closes,
            "Volume": np.full(n, 100_000),
        },
        index=dates,
    )
    df.attrs["ticker"] = "CAUSAL_TEST"

    # Emit signal at Bar 0 (which completes at Bar 0 close)
    engine = BacktestEngine()
    engine.slippage = 0.0
    res = engine.run_backtest(
        _SingleSignalStrategy(target_bar_idx=0),
        df,
        initial_capital=10_000,
        position_sizing="equal_weight",
        drawdown_halt_enabled=False,
    )

    filled = [t for t in res.trades if t.get("status") == "filled"]
    assert len(filled) == 1
    # Trade execution MUST use Bar 1 Open ($110.0), NOT Bar 0 Close ($102.0) or Bar 0 Open ($100.0)
    assert filled[0]["filled_price"] == 110.0
    assert filled[0]["timestamp"] == str(dates[1])


def test_next_bar_causality_with_overnight_price_gap():
    """Verify execution occurs at next bar's open price during large overnight gaps."""
    n = 12
    dates = pd.bdate_range("2024-02-01", periods=n)
    # Overnight gap from $50 close on bar 2 to $80 open on bar 3
    opens = np.full(n, 50.0)
    opens[3:] = 80.0
    closes = np.full(n, 50.0)
    closes[2] = 50.0
    closes[3:] = 80.0

    df = pd.DataFrame(
        {
            "Open": opens,
            "High": opens + 2.0,
            "Low": opens - 1.0,
            "Close": closes,
            "Volume": np.full(n, 500_000),
        },
        index=dates,
    )
    df.attrs["ticker"] = "GAP_TEST"

    engine = BacktestEngine()
    engine.slippage = 1.0  # 1% slippage (passed as 1.0 for 1%)
    res = engine.run_backtest(
        _SingleSignalStrategy(target_bar_idx=2),
        df,
        initial_capital=10_000,
        position_sizing="equal_weight",
        drawdown_halt_enabled=False,
    )

    filled = [t for t in res.trades if t.get("status") == "filled"]
    assert len(filled) == 1
    # Executed at bar 3 open (80.0) + 1% slippage (0.8) = 80.8
    assert filled[0]["filled_price"] == pytest.approx(80.8, abs=1e-4)
    assert filled[0]["timestamp"] == str(dates[3])


# ---------------------------------------------------------------------------
# 3. Slippage and commission calculations
# ---------------------------------------------------------------------------


def test_buy_order_slippage_and_commission_accounting():
    """BUY order: exec_price = price * (1 + slippage), commission = notional * rate + flat."""
    p = Portfolio(
        initial_capital=10_000.0,
        slippage_pct=1.0,  # 1% slippage
        commission_rate=0.005,  # 0.5% rate
        commission_per_trade=10.0,  # $10 flat
        cash_reserve_pct=5.0,
        max_position_pct=100.0,
    )
    # Market price = 100.0, 10 shares
    order = Order(ticker="TEST", side=OrderSide.BUY, shares=10)
    res = p.execute_order(order, {"TEST": 100.0})

    assert res.status == OrderStatus.FILLED
    # exec_price = 100 * 1.01 = 101.0
    assert res.filled_price == 101.0
    # slippage per share = 1.0; total slippage = 10.0
    assert res.slippage == 10.0
    # commission = 101.0 * 10 * 0.005 + 10.0 = 5.05 + 10.0 = 15.05
    assert res.commission == 15.05
    # total cost = 101.0 * 10 + 15.05 = 1025.05
    assert p.cash == pytest.approx(10_000.0 - 1025.05, abs=1e-4)


def test_sell_order_slippage_and_commission_accounting():
    """SELL order: exec_price = price * (1 - slippage), net proceeds = notional - commission."""
    p = Portfolio(
        initial_capital=10_000.0,
        slippage_pct=1.0,  # 1% slippage
        commission_rate=0.005,  # 0.5% rate
        commission_per_trade=10.0,  # $10 flat
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    # Manually seed a 10-share position and set cash to $0
    p.positions["TEST"] = 10
    p.avg_cost["TEST"] = 100.0
    p.cash = 0.0

    order = Order(ticker="TEST", side=OrderSide.SELL, shares=10)
    res = p.execute_order(order, {"TEST": 100.0})

    assert res.status == OrderStatus.FILLED
    # exec_price = 100 * (1 - 0.01) = 99.0
    assert res.filled_price == 99.0
    # slippage = 10 * 1.0 = 10.0
    assert res.slippage == 10.0
    # commission = 99.0 * 10 * 0.005 + 10.0 = 4.95 + 10.0 = 14.95
    assert res.commission == 14.95
    # proceeds = 99.0 * 10 - 14.95 = 990.0 - 14.95 = 975.05
    assert p.cash == pytest.approx(975.05, abs=1e-4)
    assert "TEST" not in p.positions


def test_sell_commission_exceeding_gross_proceeds():
    """If commission exceeds gross trade value, net proceeds are negative and reduce cash."""
    p = Portfolio(
        initial_capital=1_000.0,
        slippage_pct=0.0,
        commission_rate=0.0,
        commission_per_trade=15.0,  # $15 flat commission
    )
    p.positions["PENNY"] = 1
    p.avg_cost["PENNY"] = 5.0
    p.cash = 100.0

    # Sell 1 share at $5.0 with $15 commission -> net proceeds = 5 - 15 = -$10
    res = p.execute_order(
        Order(ticker="PENNY", side=OrderSide.SELL, shares=1), {"PENNY": 5.0}
    )
    assert res.status == OrderStatus.FILLED
    assert p.cash == 90.0  # 100 + (-10)


# ---------------------------------------------------------------------------
# 4. Drawdown halt enforcement
# ---------------------------------------------------------------------------


def test_drawdown_halt_rejects_buy_permits_sell():
    """Halted portfolio blocks new BUY entries but allows SELL orders to liquidate positions."""
    p = Portfolio(
        initial_capital=10_000.0,
        max_drawdown_pct=10.0,
        slippage_pct=0.0,
        commission_rate=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    # Buy 50 shares of T @ 100 ($5,000)
    p.execute_order(Order(ticker="T", side=OrderSide.BUY, shares=50), {"T": 100.0})
    p.record_value("2024-01-02", {"T": 100.0})  # Peak = 10,000

    # Price drops to $60 -> equity = $5,000 cash + $3,000 stock = $8,000 (20% drawdown >= 10% limit)
    p.record_value("2024-01-03", {"T": 60.0})
    assert p.halted is True

    # Attempt new BUY while halted -> rejected
    buy_order = Order(ticker="OTHER", side=OrderSide.BUY, shares=10)
    res_buy = p.execute_order(buy_order, {"T": 60.0, "OTHER": 50.0})
    assert res_buy.status == OrderStatus.REJECTED
    assert (
        res_buy.reason == "Trading halted - max drawdown exceeded (new entries blocked)"
    )

    # Attempt SELL of existing position -> permitted
    sell_order = Order(ticker="T", side=OrderSide.SELL, shares=50)
    res_sell = p.execute_order(sell_order, {"T": 60.0})
    assert res_sell.status == OrderStatus.FILLED
    assert p.get_position("T") == 0


def test_drawdown_halt_boundary_and_permanence_under_recovery():
    """Check exact threshold equality triggers halt and price recovery never unhalts."""
    p = Portfolio(initial_capital=10_000.0, max_drawdown_pct=10.0, slippage_pct=0.0)
    p.record_value("2024-01-01", {})  # Peak = 10,000

    # Just below threshold (9.9999% drawdown) -> does not halt
    p._check_drawdown_halt(9_000.01, timestamp="2024-01-02")
    assert not p.halted

    # Exact equality (10.0000% drawdown) -> halts
    p._check_drawdown_halt(9_000.00, timestamp="2024-01-03")
    assert p.halted is True
    assert p.halted_at == "2024-01-03"
    assert p.halted_drawdown_pct == pytest.approx(10.0, abs=1e-4)

    # Market completely recovers past peak -> remains permanently halted
    p.record_value("2024-01-04", {})
    p._check_drawdown_halt(15_000.00, timestamp="2024-01-04")
    assert p.halted is True
    assert p.halted_at == "2024-01-03"  # First breach timestamp preserved


def test_drawdown_halt_disabled_none_allows_trading():
    """max_drawdown_pct=None disables the halt control completely."""
    p = Portfolio(
        initial_capital=10_000.0,
        max_drawdown_pct=None,
        slippage_pct=0.0,
        commission_rate=0.0,
        cash_reserve_pct=0.0,
        max_position_pct=100.0,
    )
    # Severe drop to 10% of peak
    p.record_value("2024-01-01", {})
    p._check_drawdown_halt(1_000.0, timestamp="2024-01-02")
    assert p.halted is False
    assert p.halted_at is None

    # BUY order still fills normally
    res = p.execute_order(
        Order(ticker="XYZ", side=OrderSide.BUY, shares=10), {"XYZ": 50.0}
    )
    assert res.status == OrderStatus.FILLED
