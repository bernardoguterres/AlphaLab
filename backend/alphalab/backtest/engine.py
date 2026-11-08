"""Backtest engine with realistic execution, walk-forward testing, and Monte Carlo."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .order import Order, OrderSide, OrderType
from .portfolio import Portfolio
from ..strategies.base_strategy import BaseStrategy
from ..utils.logger import setup_logger
from ..utils.config import load_config

logger = setup_logger("alphalab.backtest")

# "risk_parity" used to be advertised (UI, API, docstring) but fell through
# to an undocumented "20% of cash" fallback. It is not implemented for a
# single-ticker backtest (there is nothing to balance risk across).
SUPPORTED_SIZING = {"equal_weight", "volatility_weighted"}


@dataclass
class BacktestResults:
    """Container for all backtest outputs."""

    strategy_name: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    signals: pd.DataFrame | None = None
    metrics: dict | None = None
    monte_carlo: dict | None = None
    benchmark: dict | None = None
    drawdown_halt: dict | None = None

    @property
    def total_return_pct(self) -> float:
        if self.initial_capital <= 0:
            return 0.0
        return (self.final_value / self.initial_capital - 1) * 100

    def to_dict(self) -> dict:
        from .metrics import PerformanceMetrics

        filled = [t for t in self.trades if t.get("status") == "filled"]
        return {
            "strategy": self.strategy_name,
            "initial_capital": self.initial_capital,
            "final_value": round(self.final_value, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            # completed round trips (was len(ledger): orders incl. rejected)
            "total_trades": len(PerformanceMetrics.round_trips(self.trades)),
            "filled_orders": len(filled),
            "rejected_orders": sum(
                1 for t in self.trades if t.get("status") == "rejected"
            ),
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "metrics": self.metrics,
            "monte_carlo": self.monte_carlo,
            "benchmark": self.benchmark,
            "drawdown_halt": self.drawdown_halt,
        }


class BacktestEngine:
    """Event-driven backtest engine with no look-ahead bias.

    Executes signals on the *next bar's open* to prevent cheating.
    Supports walk-forward validation and Monte Carlo analysis.
    """

    def __init__(self):
        config = load_config()
        self.default_capital = config.backtest.initial_capital
        self.commission = config.backtest.commission
        self.slippage = config.backtest.slippage

    def run_backtest(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        initial_capital: float = None,
        start_date: str = None,
        end_date: str = None,
        position_sizing: str = "equal_weight",
        monte_carlo_runs: int = 0,
        max_drawdown_pct: float = None,
        risk_settings: dict | None = None,
        monte_carlo_seed: int | None = None,
        drawdown_halt_enabled: bool = True,
        monte_carlo_block_length: int | None = None,
    ) -> BacktestResults:
        """Run a full backtest simulation.

        Args:
            strategy: A configured BaseStrategy instance.
            data: OHLCV DataFrame with features already computed.
            initial_capital: Starting cash.
            start_date / end_date: Optional date filters (YYYY-MM-DD).
            position_sizing: "equal_weight" (cash up to the cumulative
                max_position_pct cap) or "volatility_weighted" (2xATR-stop
                risk sizing within the same cap). Anything else raises.
            monte_carlo_runs: Block-bootstrap resamples of the realised
                returns (0 = disabled); see backtest/bootstrap.py.
            monte_carlo_seed / monte_carlo_block_length: reproducibility and
                dependence-length controls (seed is generated and reported
                when omitted).
            max_drawdown_pct: drawdown-halt threshold in percent of the
                portfolio's peak value (None = Portfolio's 10% default).
            drawdown_halt_enabled: False disables the halt entirely
                (max_drawdown_pct must then be None). The effective
                threshold is reported as drawdown_halt["threshold_pct"].
            risk_settings: Optional dict matching api.validators.RiskSettings
                (stop_loss_pct, take_profit_pct, max_position_size_pct,
                trailing_stop_enabled, trailing_stop_pct, commission_per_trade,
                ...) - wired into the Portfolio-level risk overlay (audit bug
                3.1; trailing stop wired 2026-08-09). max_daily_loss_pct and
                max_open_positions are accepted here but not simulated -
                this engine is single-ticker/single-position, so there is no
                "multiple positions to cap" or "rest of day" concept to
                enforce; both fields still flow through to the AlphaLive
                export, where they do apply.

        Returns:
            BacktestResults with equity curve, trades, and optional MC/WF data.
        """
        if position_sizing not in SUPPORTED_SIZING:
            raise ValueError(
                f"Unsupported position_sizing {position_sizing!r}; supported: "
                f"{sorted(SUPPORTED_SIZING)}"
            )
        if not drawdown_halt_enabled and max_drawdown_pct is not None:
            raise ValueError(
                "max_drawdown_pct cannot be set when the drawdown halt is disabled"
            )
        capital = initial_capital or self.default_capital
        df = self._filter_dates(data, start_date, end_date)

        if len(df) < 10:
            logger.error("Insufficient data for backtest (%d rows)", len(df))
            return BacktestResults(strategy_name=strategy.name, initial_capital=capital)

        if not strategy.backtest_ready_check(df):
            logger.error("Data missing required columns for %s", strategy.name)
            return BacktestResults(strategy_name=strategy.name, initial_capital=capital)

        # Generate signals
        signals = strategy.generate_signals(df)

        # Run core simulation
        portfolio, trades = self._simulate(
            df,
            signals,
            capital,
            position_sizing,
            max_drawdown_pct=max_drawdown_pct,
            risk_settings=risk_settings,
            drawdown_halt_enabled=drawdown_halt_enabled,
        )

        results = BacktestResults(
            strategy_name=strategy.name,
            initial_capital=capital,
            final_value=(
                portfolio.get_portfolio_value(
                    {col: df["Close"].iloc[-1] for col in portfolio.positions}
                )
                if portfolio.positions
                else portfolio.cash
            ),
            equity_curve=portfolio.value_history,
            trades=portfolio.ledger,
            signals=signals,
            drawdown_halt={
                # Effective threshold simulated (None = halt disabled); the
                # AlphaLive export reads this, not the request.
                "threshold_pct": (
                    round(portfolio.max_drawdown_pct * 100, 4)
                    if portfolio.max_drawdown_pct is not None
                    else None
                ),
                "halted": portfolio.halted,
                "halted_at": (
                    str(portfolio.halted_at)
                    if portfolio.halted_at is not None
                    else None
                ),
                "halted_drawdown_pct": portfolio.halted_drawdown_pct,
            },
        )

        # Buy-and-hold benchmark, executed under the strategy's conventions
        results.benchmark = self._compute_benchmark(
            df,
            capital,
            slippage_pct=self.slippage,
            commission_rate=self.commission,
            commission_per_trade=(risk_settings or {}).get("commission_per_trade")
            or 0.0,
        )

        # Monte Carlo
        if monte_carlo_runs > 0 and len(portfolio.value_history) > 2:
            results.monte_carlo = self._monte_carlo(
                portfolio.value_history,
                capital,
                monte_carlo_runs,
                seed=monte_carlo_seed,
                block_length=monte_carlo_block_length,
            )

        logger.info(
            "Backtest complete for %s: %.2f%% return, %d trades",
            strategy.name,
            results.total_return_pct,
            len(portfolio.ledger),
        )
        return results

    # ------------------------------------------------------------------
    # Core simulation loop
    # ------------------------------------------------------------------

    def _simulate(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
        capital: float,
        sizing: str,
        max_drawdown_pct: float = None,
        risk_settings: dict | None = None,
        drawdown_halt_enabled: bool = True,
    ) -> tuple[Portfolio, list]:
        """Bar-by-bar simulation executing signals on next bar's open."""
        portfolio_kwargs = dict(
            initial_capital=capital,
            commission_rate=self.commission,
            slippage_pct=self.slippage,
        )
        if not drawdown_halt_enabled:
            portfolio_kwargs["max_drawdown_pct"] = None
        elif max_drawdown_pct is not None:
            portfolio_kwargs["max_drawdown_pct"] = max_drawdown_pct
        if risk_settings:
            # commission_per_trade is a flat USD fee per filled order,
            # simulated by Portfolio's own flat-fee term (not mapped onto the
            # percentage commission_rate - different units).
            if risk_settings.get("commission_per_trade"):
                portfolio_kwargs["commission_per_trade"] = risk_settings[
                    "commission_per_trade"
                ]
            if risk_settings.get("stop_loss_pct") is not None:
                portfolio_kwargs["stop_loss_pct"] = risk_settings["stop_loss_pct"]
            if risk_settings.get("take_profit_pct") is not None:
                portfolio_kwargs["take_profit_pct"] = risk_settings["take_profit_pct"]
            if risk_settings.get("max_position_size_pct") is not None:
                portfolio_kwargs["max_position_pct"] = risk_settings[
                    "max_position_size_pct"
                ]
            if (
                risk_settings.get("trailing_stop_enabled")
                and risk_settings.get("trailing_stop_pct") is not None
            ):
                portfolio_kwargs["trailing_stop_pct"] = risk_settings[
                    "trailing_stop_pct"
                ]
        portfolio = Portfolio(**portfolio_kwargs)

        pending_signal = None  # Signal from previous bar to execute on this bar's open

        for i in range(len(data)):
            row = data.iloc[i]
            ts = data.index[i]
            ticker = data.attrs.get("ticker", "UNKNOWN")
            prices = {ticker: row["Close"]}
            open_prices = {ticker: row["Open"]} if "Open" in data.columns else prices

            # Execute pending signal from previous bar on this bar's open.
            # Audit bug 3.2: no longer gated on `not portfolio.halted` here -
            # a halt must still allow SELL (exit) orders through; Portfolio.
            # execute_order() itself now only rejects BUY orders while
            # halted, so a halted portfolio can still close positions.
            if pending_signal is not None:
                sig_val, sig_reason = pending_signal
                exec_price_map = open_prices

                if sig_val == 1:
                    shares = self._calculate_shares(
                        portfolio, ticker, row["Open"], sizing, data, i, open_prices
                    )
                    if shares > 0:
                        order = Order(
                            ticker=ticker,
                            side=OrderSide.BUY,
                            shares=shares,
                            order_type=OrderType.MARKET,
                            reason=sig_reason,
                        )
                        portfolio.execute_order(order, exec_price_map, timestamp=ts)

                elif sig_val == -1:
                    held = portfolio.get_position(ticker)
                    if held > 0:
                        order = Order(
                            ticker=ticker,
                            side=OrderSide.SELL,
                            shares=held,
                            order_type=OrderType.MARKET,
                            reason=sig_reason,
                        )
                        portfolio.execute_order(order, exec_price_map, timestamp=ts)

                pending_signal = None

            # Record today's value (using close)
            portfolio.record_value(ts, prices)

            # Check trailing stops
            portfolio.update_trailing_stops(prices)

            # Read today's signal for tomorrow's execution
            if i < len(signals) and ts in signals.index:
                sig = signals.loc[ts]
                sig_val = (
                    int(sig.get("signal", 0))
                    if not isinstance(sig, pd.DataFrame)
                    else 0
                )
                if sig_val != 0:
                    reason = (
                        sig.get("reason", "")
                        if not isinstance(sig, pd.DataFrame)
                        else ""
                    )
                    pending_signal = (sig_val, reason)

            # Trailing stop (previously tracked/ratcheted by
            # update_trailing_stops() above but never actually checked
            # against price anywhere - the whole feature was inert despite
            # being fully wired in the UI/API). Checked against this bar's
            # close, queued for the next bar's open like every other exit
            # here.
            trailing_exit_reason = portfolio.check_trailing_stop_exit(
                ticker, row["Close"]
            )
            if trailing_exit_reason is not None:
                pending_signal = (-1, trailing_exit_reason)

            # Portfolio-level stop-loss/take-profit overlay (audit bug 3.1):
            # checked against this bar's close, queued for execution on the
            # next bar's open (same no-look-ahead convention as strategy
            # signals). Takes priority over whatever the strategy decided
            # this bar - a risk-overlay exit is not something the strategy
            # opted into per-trade, it's an account-level bracket the user
            # configured, so it overrides rather than merges with a
            # same-bar strategy signal.
            risk_exit_reason = portfolio.check_risk_overlay_exit(ticker, row["Close"])
            if risk_exit_reason is not None:
                pending_signal = (-1, risk_exit_reason)

        return portfolio, portfolio.ledger

    def _calculate_shares(
        self,
        portfolio: Portfolio,
        ticker: str,
        price: float,
        sizing: str,
        data: pd.DataFrame,
        bar_idx: int,
        current_prices: dict = None,
    ) -> int:
        """Determine number of shares to buy based on sizing method."""
        if price <= 0:
            return 0

        available = portfolio.cash * (1 - portfolio.cash_reserve_pct)
        effective_price = price * (1 + portfolio.slippage_pct)
        cost_per_share = effective_price * (1 + portfolio.commission_rate)
        cash_budget = available - portfolio.commission_per_trade

        if sizing == "equal_weight":
            if cash_budget <= 0 or cost_per_share <= 0:
                return 0
            port_val = portfolio.get_portfolio_value(current_prices or {ticker: price})
            # Cumulative cap: only the headroom left above the existing
            # position may be bought (an add-on BUY while already at the cap
            # buys nothing).
            held_val = portfolio.get_position(ticker) * price
            headroom = max(0.0, port_val * portfolio.max_position_pct - held_val)
            return int(
                max(
                    0,
                    min(
                        cash_budget / cost_per_share,
                        headroom / effective_price,
                    ),
                )
            )

        if sizing == "volatility_weighted":
            # Risk-based: lose at most max_loss_per_trade_pct of equity if a
            # 2xATR stop is hit, within the cumulative position cap. No ATR
            # yet (warm-up) -> no entry; there is no silent fallback size.
            # The fill is at this bar's OPEN, so only the previous bar's ATR
            # is known; ATR[bar_idx] would use this bar's high/low/close.
            prev = bar_idx - 1
            atr = (
                data["ATR"].iloc[prev]
                if "ATR" in data.columns and prev >= 0
                else float("nan")
            )
            if not (atr > 0):
                return 0
            if cash_budget <= 0 or cost_per_share <= 0:
                return 0
            port_val = portfolio.get_portfolio_value(current_prices or {ticker: price})
            held_val = portfolio.get_position(ticker) * price
            shares = portfolio.calculate_position_size(price, price - 2 * atr, port_val)
            headroom = max(0.0, port_val * portfolio.max_position_pct - held_val)
            # Size the cash limit using the effective per-share cash cost
            # (including slippage and percentage commission), and position cap
            # headroom using effective price (slippage only, since position
            # valuation does not include commissions).
            return int(
                max(
                    0,
                    min(
                        shares,
                        cash_budget / cost_per_share,
                        headroom / effective_price,
                    ),
                )
            )

        raise ValueError(f"Unsupported position_sizing: {sizing!r}")

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------

    def _monte_carlo(
        self,
        equity_curve: list[dict],
        capital: float,
        n_runs: int,
        seed: int | None = None,
        block_length: int | None = None,
    ) -> dict:
        """Block-bootstrap uncertainty of the COMPLETED backtest's realised
        per-bar returns (see alphalab/backtest/bootstrap.py for the exact
        question answered and its limits). Replaces the old signal-shift
        "Monte Carlo", which shifted the whole signal series by -2..+2 bars
        (negative shifts traded before the signal existed), could only
        produce 5 distinct outcomes, and had no seed."""
        from .bootstrap import block_bootstrap
        from .metrics import PerformanceMetrics

        values = np.array([p["value"] for p in equity_curve], dtype=float)
        dates = pd.to_datetime([p["date"] for p in equity_curve])
        rets = values[1:] / values[:-1] - 1
        ppy = PerformanceMetrics._infer_periods_per_year(pd.DatetimeIndex(dates))
        return block_bootstrap(
            rets,
            initial_value=capital,
            n_runs=n_runs,
            periods_per_year=ppy,
            block_length=block_length,
            seed=seed,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_benchmark(
        data: pd.DataFrame,
        capital: float,
        slippage_pct: float = 0.0,
        commission_rate: float = 0.0,
        commission_per_trade: float = 0.0,
    ) -> dict:
        """Buy-and-hold benchmark executed like a strategy entry: buy whole
        shares at the FIRST bar's open plus the same slippage (percent) and
        commission model, hold, mark at each close. (It used to buy at the
        first CLOSE with no costs, a cheaper fill than any strategy entry.)"""
        if "Close" not in data.columns or len(data) < 2:
            return {}
        close = data["Close"]
        open0 = data["Open"].iloc[0] if "Open" in data.columns else close.iloc[0]
        fill = open0 * (1 + slippage_pct / 100)
        per_share = fill * (1 + commission_rate)
        shares = int(max(0.0, capital - commission_per_trade) / per_share)
        cost = shares * fill * (1 + commission_rate) + (
            commission_per_trade if shares else 0
        )
        cash_reserve = capital - cost
        equity = shares * close + cash_reserve
        bnh_curve = [
            {"date": idx, "value": round(val, 2)} for idx, val in equity.items()
        ]
        running_peak = equity.cummax()
        max_dd = float(((equity - running_peak) / running_peak * 100).min())
        bnh_final = float(equity.iloc[-1])

        # Field names match what every frontend consumer reads (Backtest.tsx,
        # OverlayEquityChart.tsx, CorrelationMatrix.tsx, types/index.ts).
        return {
            "total_return_pct": round((bnh_final / capital - 1) * 100, 2),
            "final_value": round(bnh_final, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "equity_curve": bnh_curve,
            "execution": "first bar open + slippage/commission, whole shares",
        }

    @staticmethod
    def _filter_dates(
        data: pd.DataFrame, start: str | None, end: str | None
    ) -> pd.DataFrame:
        df = data.copy()
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        return df
