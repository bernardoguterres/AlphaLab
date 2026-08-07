"""Equal-weight benchmark: buy-and-hold the FULL universe, equally weighted,
rebalanced periodically.

Built by reusing PortfolioConstructor with top_n = len(universe) (select
everyone, rank is irrelevant) - a real, cost-modeled backtest through the
same engine used for every strategy in this codebase, not an approximation.

Why this benchmark matters, and why it was missing until 2026-07-12: a
diversified/rotation/ranked-selection strategy was only being compared
against cap-weighted SPY buy-and-hold and the Faber SMA overlay (also
SPY-based). Neither controls for a simple confound - 2018-2024 was a period
of extreme mega-cap-tech concentration in the S&P 500 (a small number of
names drove most of the index's return), so ANY diversified or equal-weight
strategy is structurally disadvantaged against cap-weighted SPY in this
specific window almost by construction (the same reason equal-weight S&P
500 index funds badly lagged cap-weighted S&P 500 funds over this period).
"Beats SPY buy-and-hold" can therefore partly just be restating "cap-weight
concentration hurt this window," not that the strategy's ranking/selection
logic added value over passive equal-weighting of the SAME universe it
draws from. This benchmark isolates that: same universe, same rebalance
cadence, same costs - no ranking at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .portfolio_constructor import PortfolioConstructor, PortfolioConstructorResult


@dataclass
class _UniformCandidate:
    ticker: str
    combined_rank: int


def equal_weight_benchmark(
    price_data: dict[str, pd.DataFrame],
    rebalance_period_bars: int,
    initial_capital: float = 100_000.0,
    commission_rate: float = 0.0,
    slippage_pct: float = 0.05,
    max_drawdown_pct: float = 40.0,
) -> PortfolioConstructorResult:
    """Equal-weight, periodically-rebalanced buy-and-hold of every ticker in
    price_data - the passive baseline a ranked-selection strategy drawing
    from the same universe should be compared against, alongside (not
    instead of) SPY buy-and-hold and the Faber overlay.

    Args:
        price_data: ticker -> DataFrame with "Close", same shape
            PortfolioConstructor.run() expects.
        rebalance_period_bars: use the SAME cadence as the strategy being
            compared against, so turnover/cost drag is apples-to-apples.
        initial_capital, commission_rate, slippage_pct, max_drawdown_pct:
            passed straight through to PortfolioConstructor/Portfolio.

    Returns:
        PortfolioConstructorResult - same shape as any other
        PortfolioConstructor run, so existing metrics/DSR code works
        unchanged on it.
    """
    tickers = list(price_data.keys())
    candidates = [_UniformCandidate(t, i) for i, t in enumerate(tickers)]
    pc = PortfolioConstructor(
        top_n=len(tickers),
        rebalance_period_bars=rebalance_period_bars,
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        slippage_pct=slippage_pct,
        max_drawdown_pct=max_drawdown_pct,
    )
    return pc.run(candidates, price_data)
