"""Portfolio management with realistic order execution and risk controls."""

from datetime import datetime
from typing import Optional

import numpy as np

from .order import Order, OrderSide, OrderStatus, OrderType
from ..utils.logger import setup_logger

logger = setup_logger("alphalab.portfolio")


class Portfolio:
    """Track positions, cash, and execute orders with realistic costs.

    Supports market, limit, stop-loss, and trailing-stop orders with
    configurable slippage, commission, and risk management rules.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_rate: float = 0.0,
        slippage_pct: float = 0.05,
        max_position_pct: float = 20.0,
        cash_reserve_pct: float = 5.0,
        max_loss_per_trade_pct: float = 2.0,
        max_drawdown_pct: float = 10.0,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct / 100
        self.max_position_pct = max_position_pct / 100
        self.cash_reserve_pct = cash_reserve_pct / 100
        self.max_loss_per_trade_pct = max_loss_per_trade_pct / 100
        self.max_drawdown_pct = max_drawdown_pct / 100

        self.positions: dict[str, int] = {}  # ticker -> shares
        self.avg_cost: dict[str, float] = {}  # ticker -> avg cost per share
        self.trailing_stops: dict[str, float] = {}  # ticker -> stop price

        self.ledger: list[dict] = []
        self.value_history: list[dict] = []
        self.peak_value = initial_capital
        self.halted = False

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute_order(
        self,
        order: Order,
        current_prices: dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> Order:
        """Process an order and update portfolio state.

        Args:
            order: The Order to execute.
            current_prices: Dict of ticker -> current market price.
            timestamp: Execution timestamp.

        Returns:
            The same Order object with updated status/filled fields.
        """
        if self.halted:
            order.status = OrderStatus.REJECTED
            order.reason = "Trading halted — max drawdown exceeded"
            self._log_trade(order, timestamp)
            return order

        price = current_prices.get(order.ticker)
        if price is None or price <= 0:
            order.status = OrderStatus.REJECTED
            order.reason = f"No valid price for {order.ticker}"
            self._log_trade(order, timestamp)
            return order

        # Determine execution price based on order type
        exec_price = self._get_execution_price(order, price)
        if exec_price is None:
            order.status = OrderStatus.PENDING
            return order

        # Apply slippage
        if order.side == OrderSide.BUY:
            slippage = exec_price * self.slippage_pct
            exec_price += slippage
        else:
            slippage = exec_price * self.slippage_pct
            exec_price -= slippage

        commission = abs(exec_price * order.shares * self.commission_rate)

        # Risk checks
        if order.side == OrderSide.BUY:
            total_cost = exec_price * order.shares + commission
            if not self._can_afford(total_cost):
                order.status = OrderStatus.REJECTED
                order.reason = "Insufficient funds"
                self._log_trade(order, timestamp)
                return order

            # Position size check
            portfolio_val = self.get_portfolio_value(current_prices)
            if portfolio_val > 0:
                position_val = exec_price * order.shares
                if position_val / portfolio_val > self.max_position_pct:
                    order.status = OrderStatus.REJECTED
                    order.reason = f"Position exceeds {self.max_position_pct*100:.0f}% limit"
                    self._log_trade(order, timestamp)
                    return order

            # Execute buy
            self.cash -= total_cost
            prev_shares = self.positions.get(order.ticker, 0)
            prev_cost = self.avg_cost.get(order.ticker, 0) * prev_shares
            new_shares = prev_shares + order.shares
            self.positions[order.ticker] = new_shares
            if new_shares > 0:
                self.avg_cost[order.ticker] = (prev_cost + exec_price * order.shares) / new_shares

        else:  # SELL
            held = self.positions.get(order.ticker, 0)
            if held <= 0:
                order.status = OrderStatus.REJECTED
                order.reason = f"No position in {order.ticker}"
                self._log_trade(order, timestamp)
                return order

            sell_shares = min(order.shares, held)
            proceeds = exec_price * sell_shares - commission
            self.cash += proceeds
            self.positions[order.ticker] = held - sell_shares
            if self.positions[order.ticker] == 0:
                del self.positions[order.ticker]
                self.avg_cost.pop(order.ticker, None)
                self.trailing_stops.pop(order.ticker, None)
            order.shares = sell_shares

        order.status = OrderStatus.FILLED
        order.filled_price = round(exec_price, 4)
        order.commission = round(commission, 4)
        order.slippage = round(slippage * order.shares, 4)
        order.filled_timestamp = timestamp

        self._log_trade(order, timestamp)

        # Check portfolio-level stop
        portfolio_val = self.get_portfolio_value(current_prices)
        self._check_drawdown_halt(portfolio_val)

        return order

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_portfolio_value(self, current_prices: dict[str, float]) -> float:
        position_value = sum(
            current_prices.get(t, 0) * s for t, s in self.positions.items()
        )
        return self.cash + position_value

    def get_cash_balance(self) -> float:
        return self.cash

    def can_afford(self, ticker: str, shares: int, price: float) -> bool:
        cost = price * shares * (1 + self.slippage_pct) + abs(price * shares * self.commission_rate)
        return self._can_afford(cost)

    def get_position(self, ticker: str) -> int:
        return self.positions.get(ticker, 0)

    def calculate_position_size(
        self,
        price: float,
        stop_loss_price: float,
        current_portfolio_value: float,
    ) -> int:
        """ATR / risk-based position sizing.

        Sizes the position so that hitting the stop loss loses at most
        ``max_loss_per_trade_pct`` of portfolio value.
        """
        risk_per_share = abs(price - stop_loss_price)
        if risk_per_share <= 0:
            return 0
        max_risk = current_portfolio_value * self.max_loss_per_trade_pct
        shares = int(max_risk / risk_per_share)
        # Also cap by max position size
        max_by_size = int(current_portfolio_value * self.max_position_pct / price) if price > 0 else 0
        return max(0, min(shares, max_by_size))

    def update_trailing_stops(self, current_prices: dict[str, float]):
        """Update trailing stop prices based on current highs."""
        for ticker, shares in list(self.positions.items()):
            price = current_prices.get(ticker)
            if price is None:
                continue
            if ticker in self.trailing_stops:
                # Ratchet up the stop
                self.trailing_stops[ticker] = max(
                    self.trailing_stops[ticker], price * 0.95
                )

    def record_value(self, timestamp, current_prices: dict[str, float]):
        """Snapshot portfolio value for equity curve."""
        val = self.get_portfolio_value(current_prices)
        self.value_history.append({"date": timestamp, "value": round(val, 2)})
        self.peak_value = max(self.peak_value, val)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _can_afford(self, cost: float) -> bool:
        reserve = self.initial_capital * self.cash_reserve_pct
        return self.cash - cost >= reserve

    def _get_execution_price(self, order: Order, market_price: float) -> Optional[float]:
        if order.order_type == OrderType.MARKET:
            return market_price
        if order.order_type == OrderType.LIMIT:
            if order.limit_price is None:
                return market_price
            if order.side == OrderSide.BUY and market_price <= order.limit_price:
                return market_price
            if order.side == OrderSide.SELL and market_price >= order.limit_price:
                return market_price
            return None
        if order.order_type == OrderType.STOP_LOSS:
            if order.stop_price is None:
                return None
            if order.side == OrderSide.SELL and market_price <= order.stop_price:
                return market_price
            return None
        if order.order_type == OrderType.TRAILING_STOP:
            stop = self.trailing_stops.get(order.ticker)
            if stop and market_price <= stop:
                return market_price
            return None
        return market_price

    def _check_drawdown_halt(self, current_value: float):
        if self.peak_value <= 0:
            return
        dd = (self.peak_value - current_value) / self.peak_value
        if dd >= self.max_drawdown_pct:
            self.halted = True
            logger.warning(
                "Trading HALTED: drawdown %.1f%% exceeds limit %.1f%%",
                dd * 100, self.max_drawdown_pct * 100,
            )

    def _log_trade(self, order: Order, timestamp):
        entry = order.to_dict()
        entry["portfolio_cash"] = round(self.cash, 2)
        entry["timestamp"] = str(timestamp) if timestamp else None
        self.ledger.append(entry)
