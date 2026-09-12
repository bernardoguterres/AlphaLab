"""Portfolio management with realistic order execution and risk controls."""

import math
from datetime import datetime


from .order import Order, OrderSide, OrderStatus
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
        max_drawdown_pct: float | None = 10.0,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        trailing_stop_pct: float | None = None,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct / 100
        self.max_position_pct = max_position_pct / 100
        self.cash_reserve_pct = cash_reserve_pct / 100
        self.max_loss_per_trade_pct = max_loss_per_trade_pct / 100
        # None disables the drawdown-halt control entirely (true no-op - see
        # _check_drawdown_halt). Any finite value is a percent-of-peak
        # threshold; >= threshold triggers (see _check_drawdown_halt).
        self.max_drawdown_pct = (
            max_drawdown_pct / 100 if max_drawdown_pct is not None else None
        )
        # Portfolio-level risk overlay (from the Risk Settings UI's
        # RiskSettings.stop_loss_pct/take_profit_pct) - independent of any
        # stop-loss a strategy implements internally (e.g. RSIMeanReversion's
        # own ATR-based stop). None = disabled (audit bug 3.1: previously
        # Portfolio had no concept of these at all, and take-profit didn't
        # exist anywhere in the simulation).
        self.stop_loss_pct = stop_loss_pct / 100 if stop_loss_pct is not None else None
        self.take_profit_pct = (
            take_profit_pct / 100 if take_profit_pct is not None else None
        )
        # Ratcheting stop from each position's peak price since entry (from
        # the Risk Settings UI's RiskSettings.trailing_stop_enabled/pct).
        # None = disabled. Independent of the fixed stop_loss_pct/
        # take_profit_pct overlay above and of any strategy-internal
        # trailing stop (e.g. MomentumBreakout's own ATR-based one).
        self.trailing_stop_pct = (
            trailing_stop_pct / 100 if trailing_stop_pct is not None else None
        )

        self.positions: dict[str, int] = {}  # ticker -> shares
        self.avg_cost: dict[str, float] = {}  # ticker -> avg cost per share
        self.trailing_stops: dict[str, float] = {}  # ticker -> stop price

        self.ledger: list[dict] = []
        self.value_history: list[dict] = []
        self.peak_value = initial_capital
        self.halted = False
        # First-breach record (deterministic - set once, never overwritten
        # by a later, possibly deeper drawdown). None until halted.
        self.halted_at = None
        self.halted_drawdown_pct: float | None = None

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute_order(
        self,
        order: Order,
        current_prices: dict[str, float],
        timestamp: datetime | None = None,
    ) -> Order:
        """Process an order and update portfolio state.

        Args:
            order: The Order to execute.
            current_prices: Dict of ticker -> current market price.
            timestamp: Execution timestamp.

        Returns:
            The same Order object with updated status/filled fields.
        """
        # Audit bug 3.2: a drawdown halt must never freeze an open position
        # indefinitely - it blocks new entries (BUY), but SELL orders
        # (closing/reducing exposure) always go through. Previously this
        # blocked ALL orders once halted, with no way to ever close the
        # position for the rest of the backtest.
        if self.halted and order.side == OrderSide.BUY:
            order.status = OrderStatus.REJECTED
            order.reason = (
                "Trading halted - max drawdown exceeded (new entries blocked)"
            )
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
                    order.reason = (
                        f"Position exceeds {self.max_position_pct*100:.0f}% limit"
                    )
                    self._log_trade(order, timestamp)
                    return order

            # Execute buy
            self.cash -= total_cost
            prev_shares = self.positions.get(order.ticker, 0)
            prev_cost = self.avg_cost.get(order.ticker, 0) * prev_shares
            new_shares = prev_shares + order.shares
            self.positions[order.ticker] = new_shares
            if new_shares > 0:
                self.avg_cost[order.ticker] = (
                    prev_cost + exec_price * order.shares
                ) / new_shares
            if (
                self.trailing_stop_pct is not None
                and order.ticker not in self.trailing_stops
            ):
                self.trailing_stops[order.ticker] = exec_price * (
                    1 - self.trailing_stop_pct
                )

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

        # Drawdown-halt detection is no longer done here. Checking only on a
        # fill meant a price-only crash with no order in between went
        # undetected until whenever the next order happened to occur -
        # sometimes bars later, sometimes never. record_value() now runs the
        # same check on every bar's mark-to-market equity update instead
        # (causal, one evaluation per bar, no look-ahead) - see
        # _check_drawdown_halt's docstring. Every call site in this module
        # and portfolio_constructor.py already calls record_value() exactly
        # once per bar after any same-bar order execution, so this is a
        # strict improvement in detection latency, not a behavior removal.

        return order

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_portfolio_value(self, current_prices: dict[str, float]) -> float:
        position_value = sum(
            current_prices.get(t, 0) * s for t, s in self.positions.items()
        )
        return self.cash + position_value

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
        max_by_size = (
            int(current_portfolio_value * self.max_position_pct / price)
            if price > 0
            else 0
        )
        return max(0, min(shares, max_by_size))

    def check_trailing_stop_exit(self, ticker: str, close_price: float) -> str | None:
        """Check the ratcheting trailing stop for an open position against
        this bar's close price.

        Returns a reason string if price has fallen to or through the
        current trailing stop level, or None if trailing stops are
        disabled/not yet initialized for this ticker or the level hasn't
        been breached. Does not execute anything itself - callers queue the
        exit for the next bar's open, same no-look-ahead convention as
        check_risk_overlay_exit and strategy signals.
        """
        if self.trailing_stop_pct is None:
            return None
        held = self.positions.get(ticker, 0)
        if held <= 0:
            return None
        stop_level = self.trailing_stops.get(ticker)
        if stop_level is None:
            return None
        if close_price <= stop_level:
            return (
                f"Trailing stop triggered ({self.trailing_stop_pct*100:.1f}% "
                f"below peak, stop={stop_level:.2f})"
            )
        return None

    def check_risk_overlay_exit(self, ticker: str, close_price: float) -> str | None:
        """Check the portfolio-level stop-loss/take-profit overlay for an
        open position against this bar's close price.

        Returns a reason string if the position should be force-exited
        (stop-loss checked first), or None if neither is configured/triggered.
        Does not execute anything itself - callers queue the exit for the
        next bar's open, same no-look-ahead convention as strategy signals.
        """
        held = self.positions.get(ticker, 0)
        if held <= 0:
            return None
        entry_price = self.avg_cost.get(ticker)
        if not entry_price:
            return None

        if self.stop_loss_pct is not None:
            stop_level = entry_price * (1 - self.stop_loss_pct)
            if close_price <= stop_level:
                return (
                    f"Stop-loss triggered ({self.stop_loss_pct*100:.1f}% below entry)"
                )

        if self.take_profit_pct is not None:
            target_level = entry_price * (1 + self.take_profit_pct)
            if close_price >= target_level:
                return f"Take-profit triggered ({self.take_profit_pct*100:.1f}% above entry)"

        return None

    def update_trailing_stops(self, current_prices: dict[str, float]):
        """Ratchet each open position's trailing stop up toward the current price.

        No-op unless trailing_stop_pct is configured - previously ratcheted
        every open position toward a hardcoded 5% (price * 0.95) regardless
        of whether trailing stops were enabled or what percentage the user
        configured, while nothing anywhere checked the resulting level
        against price to actually trigger an exit (audit fix: see
        check_trailing_stop_exit below, now wired into engine.py).
        """
        if self.trailing_stop_pct is None:
            return
        for ticker in list(self.positions.keys()):
            price = current_prices.get(ticker)
            if price is None:
                continue
            if ticker in self.trailing_stops:
                # Ratchet up the stop, never down
                self.trailing_stops[ticker] = max(
                    self.trailing_stops[ticker], price * (1 - self.trailing_stop_pct)
                )

    def record_value(self, timestamp, current_prices: dict[str, float]):
        """Snapshot portfolio value for equity curve and evaluate the
        drawdown halt causally against this bar's mark-to-market equity.

        This is the single per-bar mark-to-market point every simulation
        loop (BacktestEngine._simulate, PortfolioConstructor's static and
        dynamic modes) calls exactly once per bar, so it is also the single
        place drawdown is evaluated - see _check_drawdown_halt.
        """
        val = self.get_portfolio_value(current_prices)
        self.value_history.append({"date": timestamp, "value": round(val, 2)})
        self.peak_value = max(self.peak_value, val)
        self._check_drawdown_halt(val, timestamp)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _can_afford(self, cost: float) -> bool:
        reserve = self.initial_capital * self.cash_reserve_pct
        return self.cash - cost >= reserve

    def _get_execution_price(self, order: Order, market_price: float) -> float | None:
        return market_price

    def _check_drawdown_halt(self, current_value: float, timestamp=None):
        """Evaluate the max-drawdown halt against one mark-to-market value.

        Threshold semantics: dd >= max_drawdown_pct triggers - equality
        halts (a drawdown exactly at the configured limit is treated as a
        breach, not "not yet").

        Disabled (true no-op): max_drawdown_pct=None on the Portfolio skips
        this check entirely - halted can never become True.

        First-breach-only: once self.halted is True, this returns
        immediately without re-evaluating or overwriting halted_at /
        halted_drawdown_pct - the first breach is recorded deterministically
        and a later, possibly deeper drawdown (or calling this twice for the
        same bar) does not change what was recorded. This also makes
        multiple evaluations of the same bar's value idempotent.

        Invalid/zero/negative equity: peak_value <= 0 (never a legitimate
        state past __init__ with positive initial_capital, but guarded) or a
        non-finite current_value (NaN/inf from bad price data) skip the
        check rather than raising or halting on a meaningless ratio. A
        genuinely negative or zero current_value against a positive peak is
        a real, valid breach (dd >= 1.0) and is allowed to trigger normally.
        """
        if self.max_drawdown_pct is None or self.halted:
            return
        if self.peak_value <= 0:
            return
        if current_value is None or not math.isfinite(current_value):
            return
        dd = (self.peak_value - current_value) / self.peak_value
        if dd >= self.max_drawdown_pct:
            self.halted = True
            self.halted_at = timestamp
            self.halted_drawdown_pct = round(dd * 100, 4)
            logger.warning(
                "Trading HALTED: drawdown %.1f%% exceeds limit %.1f%%",
                dd * 100,
                self.max_drawdown_pct * 100,
            )

    def _log_trade(self, order: Order, timestamp):
        entry = order.to_dict()
        entry["portfolio_cash"] = round(self.cash, 2)
        entry["timestamp"] = str(timestamp) if timestamp else None
        self.ledger.append(entry)
