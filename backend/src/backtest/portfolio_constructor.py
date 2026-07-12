"""Cross-sectional portfolio construction: rank -> top-N -> sized basket.

M2 of docs/STRATEGY_RESEARCH_PLAN.md §H. This is deliberately new orchestration,
not a modification of BacktestEngine or PortfolioOptimizer:

  - BacktestEngine._simulate() only ever loops one ticker's DataFrame against
    one Portfolio - there is no existing code path that holds N tickers in
    one shared capital pool. The batch-backtest API endpoint runs N
    *independent* single-ticker backtests, each with its own separate
    starting capital, which is not the same thing as a portfolio.
  - PortfolioOptimizer solves a different problem: post-hoc allocation of
    weights across N *already-computed* equity-curve return streams (needs a
    returns matrix / covariance). PortfolioConstructor instead ranks a
    universe *before* trading and decides, at each rebalance date, which
    names to hold and how much of each - a pre-trade decision, not a
    post-hoc blend. Its `_equal_weight()` one-liner isn't worth importing for;
    reimplemented directly below.

Reuses Portfolio (portfolio.py) for all order execution, cash tracking, and
equity-curve recording - PortfolioConstructor only decides *what orders to
place and when*, not how they're filled or costed.

Known limitations, stated explicitly (see docs/STRATEGY_RESEARCH_PLAN.md §D):
  - Equal-weight only in this milestone; rank-weighted/risk-parity are a
    later, separately-scoped extension (out of scope, not merely unbuilt).
  - No point-in-time re-ranking: the candidate list is assumed fixed for the
    whole backtest (same limitation as scripts/greenblatt_faithful_backtest.py).
    A future version that re-screens at each rebalance date needs
    point-in-time fundamentals to do so honestly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import pandas as pd

from .order import Order, OrderSide, OrderType
from .portfolio import Portfolio


class RankedCandidate(Protocol):
    """Structural type for anything PortfolioConstructor can rank on.

    ScreenerResult (src/screener/fundamental_screener.py) already satisfies
    this - any future ranking source (e.g. a sector relative-strength score)
    just needs a `.ticker` attribute and a sortable `.combined_rank`.
    """

    ticker: str
    combined_rank: int


@dataclass
class RebalanceRecord:
    date: datetime
    ticker: str
    rank: int
    target_weight: float
    target_shares: int
    price: float


@dataclass
class PortfolioConstructorResult:
    equity_curve: list[dict] = field(
        default_factory=list
    )  # {"date": ..., "value": ...}
    rebalance_history: list[RebalanceRecord] = field(default_factory=list)
    tickers_used: list[str] = field(default_factory=list)
    final_portfolio: Portfolio | None = None


class PortfolioConstructor:
    """Rank -> top-N -> equal-weight basket, backtested with realistic costs.

    Args:
        top_n: Number of top-ranked candidates to hold.
        rebalance_period_bars: Reset to target equal weight every N bars
            (e.g. 52 for annual rebalance on weekly bars, matching
            Greenblatt's own recommended cadence).
        weighting: Only "equal_weight" is implemented in this milestone.
        initial_capital, commission_rate, slippage_pct, cash_reserve_pct:
            Passed straight through to the underlying Portfolio.
    """

    def __init__(
        self,
        top_n: int = 6,
        rebalance_period_bars: int = 52,
        weighting: str = "equal_weight",
        initial_capital: float = 100_000.0,
        commission_rate: float = 0.0,
        slippage_pct: float = 0.05,
        cash_reserve_pct: float = 5.0,
        max_drawdown_pct: float = 40.0,
    ):
        if weighting != "equal_weight":
            raise NotImplementedError(
                f"weighting={weighting!r} not implemented in this milestone - "
                "only 'equal_weight' is supported (see module docstring)"
            )
        self.top_n = top_n
        self.rebalance_period_bars = rebalance_period_bars
        self.weighting = weighting
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct
        self.cash_reserve_pct = cash_reserve_pct
        # Portfolio's own default (10%) is tuned for intraday/daily strategies
        # and halts trading far too early for a periodically-rebalanced
        # basket - same issue GreenblattWeekly needed max_drawdown_pct=40 to
        # avoid (AlphaLab CLAUDE.md "Known Gotchas"). A halt here doesn't
        # liquidate; it just freezes further rebalancing while price marks
        # keep updating, which silently distorts results if the threshold is
        # too tight - default to 40% rather than inheriting Portfolio's 10%.
        self.max_drawdown_pct = max_drawdown_pct

    def run(
        self,
        candidates: list[RankedCandidate],
        price_data: dict[str, pd.DataFrame],
    ) -> PortfolioConstructorResult:
        """Run the portfolio backtest.

        Args:
            candidates: Ranked candidates, ascending by combined_rank (best
                first) - e.g. the output of FundamentalScreener.screen().
            price_data: ticker -> DataFrame with a DatetimeIndex and a
                "Close" column, one entry per candidate ticker that has data.

        Returns:
            PortfolioConstructorResult with the equity curve and the full
            rebalance-by-rebalance target-weight/target-shares table (the
            latter is what a future portfolio-construction parity fixture
            for AlphaLive would be generated from).
        """
        selected = [
            c.ticker for c in sorted(candidates, key=lambda c: c.combined_rank)
        ][: self.top_n]
        rank_by_ticker = {c.ticker: c.combined_rank for c in candidates}

        available = {
            t: price_data[t]
            for t in selected
            if t in price_data and not price_data[t].empty
        }
        if len(available) < 2:
            raise ValueError(
                f"Need at least 2 tickers with price data to build a portfolio, "
                f"got {len(available)} of {len(selected)} selected"
            )
        tickers_used = list(available.keys())

        # Intersection of dates so every held ticker has a price on every bar
        # the loop visits - avoids needing to guess a fill price for gaps.
        common_index = None
        for df in available.values():
            idx = df.index
            common_index = (
                idx if common_index is None else common_index.intersection(idx)
            )
        common_index = common_index.sort_values()

        max_position_pct = min(100.0, (100.0 / len(tickers_used)) + 10.0)
        portfolio = Portfolio(
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage_pct=self.slippage_pct,
            max_position_pct=max_position_pct,
            cash_reserve_pct=self.cash_reserve_pct,
            max_drawdown_pct=self.max_drawdown_pct,
        )

        result = PortfolioConstructorResult(tickers_used=tickers_used)
        target_weight = 1.0 / len(tickers_used)

        for i, date in enumerate(common_index):
            current_prices = {
                t: float(available[t].loc[date, "Close"]) for t in tickers_used
            }

            if i % self.rebalance_period_bars == 0:
                portfolio_value = portfolio.get_portfolio_value(current_prices)
                target_shares_by_ticker = {}
                for t in tickers_used:
                    price = current_prices[t]
                    target_dollars = portfolio_value * target_weight
                    target_shares = int(target_dollars / price) if price > 0 else 0
                    target_shares_by_ticker[t] = target_shares
                    result.rebalance_history.append(
                        RebalanceRecord(
                            date=date,
                            ticker=t,
                            rank=rank_by_ticker.get(t, -1),
                            target_weight=target_weight,
                            target_shares=target_shares,
                            price=price,
                        )
                    )

                # Sells first to free up cash before buys.
                for t in tickers_used:
                    held = portfolio.get_position(t)
                    delta = target_shares_by_ticker[t] - held
                    if delta < 0:
                        order = Order(
                            ticker=t,
                            side=OrderSide.SELL,
                            shares=-delta,
                            order_type=OrderType.MARKET,
                        )
                        portfolio.execute_order(order, current_prices, timestamp=date)
                for t in tickers_used:
                    held = portfolio.get_position(t)
                    delta = target_shares_by_ticker[t] - held
                    if delta > 0:
                        order = Order(
                            ticker=t,
                            side=OrderSide.BUY,
                            shares=delta,
                            order_type=OrderType.MARKET,
                        )
                        portfolio.execute_order(order, current_prices, timestamp=date)

            portfolio.record_value(date, current_prices)

        result.equity_curve = portfolio.value_history
        result.final_portfolio = portfolio
        return result
