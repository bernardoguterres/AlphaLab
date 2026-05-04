"""Greenblatt Magic Formula fundamental screener using yfinance.

Ranks a universe of stocks by two factors:
  1. Earnings Yield  = 1 / trailing P/E  (higher = more earnings per dollar paid)
  2. Return on Capital = Return on Equity (higher = more efficient use of capital)

Combined rank (lower is better) selects the top candidates for entry timing.
Roughly follows Joel Greenblatt's "The Little Book That Beats the Market" (2005).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import yfinance as yf

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.screener.fundamental")


@dataclass
class ScreenerResult:
    ticker: str
    company_name: str
    sector: str
    earnings_yield: float      # 1 / PE  (higher = cheaper)
    return_on_equity: float    # ROE     (higher = more efficient)
    pe_ratio: float
    market_cap_b: float        # billions
    debt_to_equity: float
    earnings_yield_rank: int   # 1 = best
    roe_rank: int              # 1 = best
    combined_rank: int         # earnings_yield_rank + roe_rank (lower = better)
    raw: dict = field(default_factory=dict, repr=False)


class FundamentalScreener:
    """Screen a stock universe using Greenblatt's Magic Formula factors.

    Args:
        universe: List of ticker symbols to screen.
        min_market_cap_b: Minimum market cap in billions (filters micro-caps).
        max_debt_to_equity: Maximum debt/equity ratio (filters over-leveraged).
        request_delay: Seconds between yfinance calls to avoid rate-limiting.
    """

    def __init__(
        self,
        universe: list[str],
        min_market_cap_b: float = 1.0,
        max_debt_to_equity: float = 2.0,
        request_delay: float = 0.3,
    ):
        self.universe = universe
        self.min_market_cap_b = min_market_cap_b
        self.max_debt_to_equity = max_debt_to_equity
        self.request_delay = request_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def screen(self, top_n: int = 20) -> list[ScreenerResult]:
        """Run the full Greenblatt screen. Returns top_n ranked candidates."""
        logger.info(
            f"Screening {len(self.universe)} tickers "
            f"(min_market_cap={self.min_market_cap_b}B, "
            f"max_d/e={self.max_debt_to_equity})"
        )

        raw_data = self._fetch_all()
        qualified = self._filter(raw_data)

        if len(qualified) < 2:
            logger.warning(
                f"Only {len(qualified)} tickers passed filters — "
                "consider loosening min_market_cap_b or max_debt_to_equity"
            )
            return qualified

        ranked = self._rank(qualified)
        top = ranked[:top_n]
        logger.info(
            f"Screen complete: {len(self.universe)} fetched → "
            f"{len(qualified)} qualified → top {len(top)} selected"
        )
        return top

    def fetch_one(self, ticker: str) -> ScreenerResult | None:
        """Fetch and return fundamentals for a single ticker, or None on failure."""
        info = self._safe_fetch(ticker)
        if info is None:
            return None
        return self._parse(ticker, info)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_all(self) -> list[ScreenerResult]:
        results = []
        for i, ticker in enumerate(self.universe):
            result = self.fetch_one(ticker)
            if result is not None:
                results.append(result)
            if i < len(self.universe) - 1:
                time.sleep(self.request_delay)
        return results

    def _safe_fetch(self, ticker: str) -> dict | None:
        try:
            info = yf.Ticker(ticker).info
            if not info or info.get("regularMarketPrice") is None:
                logger.debug(f"{ticker}: no price data, skipping")
                return None
            return info
        except Exception as exc:
            logger.warning(f"{ticker}: fetch failed — {exc}")
            return None

    def _parse(self, ticker: str, info: dict) -> ScreenerResult | None:
        pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")
        market_cap = info.get("marketCap")
        debt_to_equity = info.get("debtToEquity")

        # Must have PE and ROE to rank
        if pe is None or pe <= 0 or roe is None:
            return None

        market_cap_b = (market_cap or 0) / 1e9
        # yfinance debtToEquity is reported as a percentage (e.g. 79.5 = 79.5% = 0.795×)
        # Normalise to a ratio so max_debt_to_equity=2.0 means "2× debt vs equity"
        raw_dte = debt_to_equity if debt_to_equity is not None else 0.0
        dte = raw_dte / 100.0

        return ScreenerResult(
            ticker=ticker,
            company_name=info.get("shortName", ticker),
            sector=info.get("sector", "Unknown"),
            earnings_yield=1.0 / pe,
            return_on_equity=roe,
            pe_ratio=pe,
            market_cap_b=market_cap_b,
            debt_to_equity=dte,
            earnings_yield_rank=0,   # filled in _rank()
            roe_rank=0,
            combined_rank=0,
            raw=info,
        )

    def _filter(self, results: list[ScreenerResult]) -> list[ScreenerResult]:
        out = []
        for r in results:
            if r.market_cap_b < self.min_market_cap_b:
                logger.debug(f"{r.ticker}: market cap {r.market_cap_b:.1f}B < min, skip")
                continue
            if r.debt_to_equity > self.max_debt_to_equity:
                logger.debug(f"{r.ticker}: D/E {r.debt_to_equity:.1f} > max, skip")
                continue
            out.append(r)
        return out

    def _rank(self, results: list[ScreenerResult]) -> list[ScreenerResult]:
        # Rank by earnings yield descending (higher earnings yield = rank 1)
        by_ey = sorted(results, key=lambda r: r.earnings_yield, reverse=True)
        for i, r in enumerate(by_ey):
            r.earnings_yield_rank = i + 1

        # Rank by ROE descending (higher ROE = rank 1)
        by_roe = sorted(results, key=lambda r: r.return_on_equity, reverse=True)
        for i, r in enumerate(by_roe):
            r.roe_rank = i + 1

        # Combined rank = sum of both ranks (lower = better)
        for r in results:
            r.combined_rank = r.earnings_yield_rank + r.roe_rank

        return sorted(results, key=lambda r: r.combined_rank)
