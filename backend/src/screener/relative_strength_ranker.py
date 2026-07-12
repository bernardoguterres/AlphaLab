"""Relative-strength ranker for sector rotation (Levy 1967, practitioner
sector-rotation adaptation).

Levy, R.A. (1967). "Relative Strength as a Criterion for Investment
Selection." Journal of Finance 22(4), 595-610.
https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1967.tb00295.x

Original signal: current price / 26-week trailing moving average, ranked
across instruments; buy the highest ratios (price well above its own
trend). This module ranks the 11 SPDR Select Sector ETFs by that ratio -
see docs/STRATEGY_RESEARCH_PLAN.md §B/§C (shortlist item 2).

Unlike FundamentalScreener (which must use a single present-day snapshot
because fundamentals have no point-in-time source available to this
project), this ranker is price-only: price history is not look-ahead
biased, so it is designed to be called fresh at EVERY rebalance date using
only trailing data - see PortfolioConstructor's `rank_fn` mode
(backend/src/backtest/portfolio_constructor.py, added 2026-07-12
specifically to support this).

Data-quality note: sector ETFs are a far more stable, survivorship-bias-
resistant universe than individual stocks (none of the 11 SPDR sector ETFs
have delisted since their 1998/2018 inceptions), but GICS sector
definitions have changed over time (notably the 2018 creation of
Communication Services, XLC) - a genuinely point-in-time backtest reaching
back before 2018 would need to account for that. Not handled here; flagged
per docs/STRATEGY_RESEARCH_PLAN.md's own disclosure convention.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# The 11 SPDR Select Sector ETFs (State Street). XLC (Communication
# Services) only exists from 2018-06-19 onward - callers backtesting before
# that date should exclude it or expect it to be silently skipped by
# `rank()` (no price data yet = not rankable, same as any other missing-data
# ticker).
SPDR_SECTOR_ETFS = [
    "XLC",  # Communication Services
    "XLY",  # Consumer Discretionary
    "XLP",  # Consumer Staples
    "XLE",  # Energy
    "XLF",  # Financials
    "XLV",  # Health Care
    "XLI",  # Industrials
    "XLB",  # Materials
    "XLRE",  # Real Estate
    "XLK",  # Technology
    "XLU",  # Utilities
]

DEFAULT_SMA_WEEKS = 26


@dataclass
class RelativeStrengthResult:
    ticker: str
    price: float
    sma: float
    relative_strength: float  # price / sma, higher = stronger
    combined_rank: int  # 1 = strongest (highest relative_strength)


class RelativeStrengthRanker:
    """Ranks a universe by Levy's price / trailing-SMA relative-strength ratio.

    Args:
        sma_weeks: trailing SMA window in weeks (Levy's original: 26).
    """

    def __init__(self, sma_weeks: int = DEFAULT_SMA_WEEKS):
        self.sma_weeks = sma_weeks

    def rank(self, price_data: dict[str, pd.DataFrame]) -> list[RelativeStrengthResult]:
        """Rank the given universe using only the data provided (the caller
        is responsible for only passing trailing/point-in-time-safe data -
        this method does not itself trim anything, matching
        PortfolioConstructor's `rank_fn` contract of handing in
        already-trailing-trimmed price_data).

        Args:
            price_data: ticker -> DataFrame with a DatetimeIndex and a
                "Close" column.

        Returns:
            Ranked results, best (highest relative_strength) first. Tickers
            with fewer than sma_weeks bars of history are excluded (can't
            compute a full SMA yet).
        """
        raw = []
        for ticker, df in price_data.items():
            if df is None or df.empty or len(df) < self.sma_weeks:
                continue
            closes = df["Close"].dropna()
            if len(closes) < self.sma_weeks:
                continue
            sma = float(closes.tail(self.sma_weeks).mean())
            price = float(closes.iloc[-1])
            if sma <= 0:
                continue
            raw.append((ticker, price, sma, price / sma))

        raw.sort(key=lambda r: r[3], reverse=True)  # highest ratio first

        return [
            RelativeStrengthResult(
                ticker=ticker,
                price=price,
                sma=sma,
                relative_strength=ratio,
                combined_rank=i + 1,
            )
            for i, (ticker, price, sma, ratio) in enumerate(raw)
        ]
