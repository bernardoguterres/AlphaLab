"""Backtest engine with realistic execution, walk-forward testing, and Monte Carlo."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd

from .order import Order, OrderSide, OrderType
from .portfolio import Portfolio
from ..strategies.base_strategy import BaseStrategy
from ..utils.logger import setup_logger
from ..utils.config import load_config

logger = setup_logger("alphalab.backtest")


@dataclass
class BacktestResults:
    """Container for all backtest outputs."""

    strategy_name: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    signals: Optional[pd.DataFrame] = None
    metrics: Optional[dict] = None
    monte_carlo: Optional[dict] = None
    walk_forward: Optional[list[dict]] = None
    benchmark: Optional[dict] = None

    @property
    def total_return_pct(self) -> float:
        if self.initial_capital <= 0:
            return 0.0
        return (self.final_value / self.initial_capital - 1) * 100

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "initial_capital": self.initial_capital,
            "final_value": round(self.final_value, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "total_trades": len(self.trades),
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "metrics": self.metrics,
            "monte_carlo": self.monte_carlo,
            "walk_forward": self.walk_forward,
            "benchmark": self.benchmark,
        }


class BacktestEngine:
    """Event-driven backtest engine with no look-ahead bias.

    Executes signals on the *next bar's open* to prevent cheating.
    Supports walk-forward validation and Monte Carlo analysis.
    """

    def __init__(self):
        config = load_config()
        bt_cfg = config.get("backtest", {})
        self.default_capital = bt_cfg.get("initial_capital", 100_000)
        self.commission = bt_cfg.get("commission", 0.0)
        self.slippage = bt_cfg.get("slippage", 0.05)

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
    ) -> BacktestResults:
        """Run a full backtest simulation.

        Args:
            strategy: A configured BaseStrategy instance.
            data: OHLCV DataFrame with features already computed.
            initial_capital: Starting cash.
            start_date / end_date: Optional date filters (YYYY-MM-DD).
            position_sizing: "equal_weight", "risk_parity", or "volatility_weighted".
            monte_carlo_runs: Number of randomized runs (0 = disabled).

        Returns:
            BacktestResults with equity curve, trades, and optional MC/WF data.
        """
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
        portfolio, trades = self._simulate(df, signals, capital, position_sizing,
                                           max_drawdown_pct=max_drawdown_pct)

        results = BacktestResults(
            strategy_name=strategy.name,
            initial_capital=capital,
            final_value=portfolio.get_portfolio_value(
                {col: df["Close"].iloc[-1] for col in portfolio.positions}
            ) if portfolio.positions else portfolio.cash,
            equity_curve=portfolio.value_history,
            trades=portfolio.ledger,
            signals=signals,
        )

        # Buy-and-hold benchmark
        results.benchmark = self._compute_benchmark(df, capital)

        # Monte Carlo
        if monte_carlo_runs > 0:
            results.monte_carlo = self._monte_carlo(
                df, strategy, capital, position_sizing, monte_carlo_runs
            )

        logger.info(
            "Backtest complete for %s: %.2f%% return, %d trades",
            strategy.name, results.total_return_pct, len(portfolio.ledger),
        )
        return results

    def walk_forward(
        self,
        strategy_class,
        strategy_params: dict,
        data: pd.DataFrame,
        train_pct: float = 0.7,
        n_splits: int = 3,
        initial_capital: float = None,
    ) -> list[BacktestResults]:
        """Rolling walk-forward validation.

        Splits data into n_splits windows, trains on train_pct of each,
        tests on the remainder.
        """
        capital = initial_capital or self.default_capital
        n = len(data)
        split_size = n // n_splits
        results = []

        for i in range(n_splits):
            start = i * split_size
            end = min(start + split_size, n)
            window = data.iloc[start:end]

            train_end = int(len(window) * train_pct)
            test_data = window.iloc[train_end:]

            if len(test_data) < 10:
                continue

            strategy = strategy_class(strategy_params)
            r = self.run_backtest(strategy, test_data, initial_capital=capital)
            r.walk_forward = [{"split": i, "test_start": str(test_data.index[0]),
                               "test_end": str(test_data.index[-1])}]
            results.append(r)

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
    ) -> tuple[Portfolio, list]:
        """Bar-by-bar simulation executing signals on next bar's open."""
        portfolio_kwargs = dict(
            initial_capital=capital,
            commission_rate=self.commission,
            slippage_pct=self.slippage,
        )
        if max_drawdown_pct is not None:
            portfolio_kwargs["max_drawdown_pct"] = max_drawdown_pct
        portfolio = Portfolio(**portfolio_kwargs)

        pending_signal = None  # Signal from previous bar to execute on this bar's open

        for i in range(len(data)):
            row = data.iloc[i]
            ts = data.index[i]
            ticker = data.attrs.get("ticker", "UNKNOWN")
            prices = {ticker: row["Close"]}
            open_prices = {ticker: row["Open"]} if "Open" in data.columns else prices

            # Execute pending signal from previous bar on this bar's open
            if pending_signal is not None and not portfolio.halted:
                sig_val, sig_reason = pending_signal
                exec_price_map = open_prices

                if sig_val == 1:
                    shares = self._calculate_shares(
                        portfolio, ticker, row["Open"], sizing, data, i
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
                sig_val = int(sig.get("signal", 0)) if not isinstance(sig, pd.DataFrame) else 0
                if sig_val != 0:
                    reason = sig.get("reason", "") if not isinstance(sig, pd.DataFrame) else ""
                    pending_signal = (sig_val, reason)

        return portfolio, portfolio.ledger

    def _calculate_shares(
        self,
        portfolio: Portfolio,
        ticker: str,
        price: float,
        sizing: str,
        data: pd.DataFrame,
        bar_idx: int,
    ) -> int:
        """Determine number of shares to buy based on sizing method."""
        if price <= 0:
            return 0

        available = portfolio.cash * (1 - portfolio.cash_reserve_pct)

        if sizing == "equal_weight":
            # Use up to max_position_pct of portfolio, accounting for slippage
            port_val = portfolio.cash  # approximate (no other position values without prices)
            max_alloc = port_val * portfolio.max_position_pct
            budget = min(available, max_alloc)
            effective_price = price * (1 + portfolio.slippage_pct)
            return int(budget / effective_price)

        if sizing == "volatility_weighted" and "ATR" in data.columns:
            atr = data["ATR"].iloc[bar_idx]
            if atr > 0:
                stop_price = price - 2 * atr
                return portfolio.calculate_position_size(
                    price, stop_price, portfolio.cash
                )

        # Fallback
        return int(available * 0.2 / price)

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------

    def _monte_carlo(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy,
        capital: float,
        sizing: str,
        n_runs: int,
    ) -> dict:
        """Randomize entry timing by ±1-2 days and aggregate results."""
        final_values = []

        for run in range(n_runs):
            # Shift signals randomly
            signals = strategy.generate_signals(data)
            shift = np.random.randint(-2, 3)
            signals = signals.shift(shift).fillna(0)
            # Re-cast signal column
            if "signal" in signals.columns:
                signals["signal"] = signals["signal"].astype(int)

            portfolio, _ = self._simulate(data, signals, capital, sizing)
            # Final value
            last_price = data["Close"].iloc[-1]
            ticker = data.attrs.get("ticker", "UNKNOWN")
            fv = portfolio.get_portfolio_value({ticker: last_price})
            final_values.append(fv)

        arr = np.array(final_values)
        return {
            "runs": n_runs,
            "mean_final_value": round(float(arr.mean()), 2),
            "median_final_value": round(float(np.median(arr)), 2),
            "std_final_value": round(float(arr.std()), 2),
            "min_final_value": round(float(arr.min()), 2),
            "max_final_value": round(float(arr.max()), 2),
            "prob_profit": round(float((arr > capital).mean()), 4),
            "percentile_5": round(float(np.percentile(arr, 5)), 2),
            "percentile_95": round(float(np.percentile(arr, 95)), 2),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_benchmark(data: pd.DataFrame, capital: float) -> dict:
        """Compute buy-and-hold benchmark for comparison."""
        if "Close" not in data.columns or len(data) < 2:
            return {}
        close = data["Close"]
        start_price = close.iloc[0]
        end_price = close.iloc[-1]
        bnh_return = (end_price / start_price - 1) * 100
        shares = int(capital / start_price)
        bnh_final = shares * end_price + (capital - shares * start_price)

        # Benchmark equity curve
        bnh_curve = []
        for idx, price in close.items():
            val = shares * price + (capital - shares * start_price)
            bnh_curve.append({"date": idx, "value": round(val, 2)})

        # Max drawdown
        peak = capital
        max_dd = 0.0
        for pt in bnh_curve:
            peak = max(peak, pt["value"])
            dd = (pt["value"] - peak) / peak * 100
            max_dd = min(max_dd, dd)

        return {
            "buy_and_hold_return_pct": round(bnh_return, 2),
            "buy_and_hold_final_value": round(bnh_final, 2),
            "buy_and_hold_max_drawdown_pct": round(max_dd, 2),
            "buy_and_hold_equity_curve": bnh_curve,
        }

    @staticmethod
    def _filter_dates(
        data: pd.DataFrame, start: Optional[str], end: Optional[str]
    ) -> pd.DataFrame:
        df = data.copy()
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        return df
