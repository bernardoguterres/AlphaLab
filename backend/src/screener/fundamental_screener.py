"""Greenblatt Magic Formula fundamental screener using yfinance.

Ranks a universe of stocks by the two factors from Joel Greenblatt's
*The Little Book That Beats the Market* (2005/2010):

  1. Earnings Yield    = EBIT / Enterprise Value
     (higher = more operating earnings per dollar of total takeover cost)
  2. Return on Capital  = EBIT / (Net Working Capital + Net Fixed Assets)
     (higher = more operating earnings per dollar of tangible invested capital)

Combined rank (lower is better) selects the top candidates.

This replaces an earlier proxy (1/trailing-P/E + ROE) that was shipped under
the "Greenblatt Magic Formula" name without implementing the original
formula. See docs/STRATEGY_RESEARCH_PLAN.md §B/§G/§H for the audit that
found the mismatch and the faithful-rebuild rationale. The pre-2026-07-12
proxy's historical results are frozen in docs/experiments/registry.jsonl
(entry EXP-2026-07-12-B06) as a superseded, non-equivalent variant - they are
not evidence about this formula and this formula's results are not evidence
about that one.

Known limitations, stated explicitly rather than papered over (see
docs/STRATEGY_RESEARCH_PLAN.md §D):
  - No point-in-time fundamentals: yfinance exposes only the current
    snapshot, so any historical backtest using this screener applies
    today's financials to past price data (look-ahead bias). Callers doing
    historical validation must disclose this.
  - No point-in-time universe: whatever ticker list is passed in is assumed
    to have existed and been eligible throughout the backtest period, which
    is not verified. Survivorship bias if the universe is hand-picked
    present-day large caps (as AlphaLab's default 23-ticker universe is).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import yfinance as yf

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.screener.fundamental")

# Greenblatt's original methodology excludes financials and utilities:
# EBIT/EV and EBIT/(NWC+FixedAssets) are not meaningful for regulated,
# balance-sheet-driven (rather than operating-asset-driven) businesses.
EXCLUDED_SECTORS = {"Financial Services", "Financials", "Utilities"}

# Row-label fallbacks across yfinance schema variants (older/newer pandas
# datareader versions use slightly different labels for the same line item).
_EBIT_ROWS = ["EBIT", "Total Operating Income As Reported", "Operating Income"]
_NWC_ROWS = ["Working Capital"]  # yfinance computes this directly
_CURRENT_ASSET_ROWS = ["Current Assets", "Total Current Assets"]
_CURRENT_LIAB_ROWS = ["Current Liabilities", "Total Current Liabilities"]
_NET_PPE_ROWS = ["Net PPE", "Net Property Plant Equipment"]


@dataclass
class ScreenerResult:
    ticker: str
    company_name: str
    sector: str
    earnings_yield: float  # EBIT / EV  (higher = cheaper)
    return_on_capital: float  # EBIT / (NWC + Net Fixed Assets)  (higher = more efficient)
    ebit: float
    enterprise_value: float
    invested_capital: float  # NWC + Net Fixed Assets
    market_cap_b: float  # billions
    debt_to_equity: float
    earnings_yield_rank: int  # 1 = best
    roc_rank: int  # 1 = best
    combined_rank: int  # earnings_yield_rank + roc_rank (lower = better)
    raw: dict = field(default_factory=dict, repr=False)


class FundamentalScreener:
    """Screen a stock universe using Greenblatt's original Magic Formula factors.

    Args:
        universe: List of ticker symbols to screen.
        min_market_cap_b: Minimum market cap in billions (filters micro-caps).
        max_debt_to_equity: Maximum debt/equity ratio (filters over-leveraged).
        request_delay: Seconds between yfinance calls to avoid rate-limiting.
        exclude_financials_utilities: Drop Financial Services/Utilities sectors,
            per Greenblatt's original methodology (EBIT-based ratios are not
            meaningful for those business models). Default True.
    """

    def __init__(
        self,
        universe: list[str],
        min_market_cap_b: float = 1.0,
        max_debt_to_equity: float = 2.0,
        request_delay: float = 0.3,
        exclude_financials_utilities: bool = True,
    ):
        self.universe = universe
        self.min_market_cap_b = min_market_cap_b
        self.max_debt_to_equity = max_debt_to_equity
        self.request_delay = request_delay
        self.exclude_financials_utilities = exclude_financials_utilities

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
                f"Only {len(qualified)} tickers passed filters - "
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
        bundle = self._safe_fetch(ticker)
        if bundle is None:
            return None
        return self._parse(ticker, *bundle)

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

    def _safe_fetch(self, ticker: str) -> tuple[dict, object, object] | None:
        """Fetch .info, .income_stmt, .balance_sheet for one ticker.

        Returns None if the ticker has no price data or any of the three
        calls fails outright - a partial/missing statement is handled later
        in _parse (a ticker with no line-item data simply can't be ranked).
        """
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if not info or info.get("regularMarketPrice") is None:
                logger.debug(f"{ticker}: no price data, skipping")
                return None
            income_stmt = t.income_stmt
            balance_sheet = t.balance_sheet
            return info, income_stmt, balance_sheet
        except Exception as exc:
            logger.warning(f"{ticker}: fetch failed - {exc}")
            return None

    @staticmethod
    def _first_row(df, row_names: list[str]) -> float | None:
        """Return the most recent (first) column's value for the first matching row label."""
        if df is None or not hasattr(df, "index"):
            return None
        for name in row_names:
            if name in df.index:
                try:
                    series = df.loc[name]
                    val = series.iloc[0] if hasattr(series, "iloc") else series
                    if val is None:
                        continue
                    val = float(val)
                    if val != val:  # NaN check without importing math/numpy
                        continue
                    return val
                except (TypeError, ValueError, IndexError):
                    continue
        return None

    def _parse(self, ticker: str, info: dict, income_stmt, balance_sheet) -> ScreenerResult | None:
        sector = info.get("sector", "Unknown")
        if self.exclude_financials_utilities and sector in EXCLUDED_SECTORS:
            logger.debug(f"{ticker}: sector {sector} excluded (Greenblatt convention)")
            return None

        ebit = self._first_row(income_stmt, _EBIT_ROWS)
        ev = info.get("enterpriseValue")
        market_cap = info.get("marketCap")
        debt_to_equity = info.get("debtToEquity")

        nwc = self._first_row(balance_sheet, _NWC_ROWS)
        if nwc is None:
            current_assets = self._first_row(balance_sheet, _CURRENT_ASSET_ROWS)
            current_liabilities = self._first_row(balance_sheet, _CURRENT_LIAB_ROWS)
            if current_assets is not None and current_liabilities is not None:
                nwc = current_assets - current_liabilities
        net_fixed_assets = self._first_row(balance_sheet, _NET_PPE_ROWS)

        # Must have EBIT, EV, and both invested-capital components to rank.
        if ebit is None or ev is None or nwc is None or net_fixed_assets is None:
            logger.debug(f"{ticker}: missing EBIT/EV/NWC/NetPPE, skipping")
            return None

        # Greenblatt's screen excludes loss-making companies (EBIT must be positive)
        # and requires positive tangible invested capital for the ROC ratio to be
        # economically meaningful.
        if ebit <= 0:
            return None
        invested_capital = nwc + net_fixed_assets
        if invested_capital <= 0:
            return None
        if ev <= 0:
            return None

        market_cap_b = (market_cap or 0) / 1e9
        # yfinance debtToEquity is reported as a percentage (e.g. 79.5 = 79.5% = 0.795×)
        # Normalise to a ratio so max_debt_to_equity=2.0 means "2× debt vs equity"
        raw_dte = debt_to_equity if debt_to_equity is not None else 0.0
        dte = raw_dte / 100.0

        return ScreenerResult(
            ticker=ticker,
            company_name=info.get("shortName", ticker),
            sector=sector,
            earnings_yield=ebit / ev,
            return_on_capital=ebit / invested_capital,
            ebit=ebit,
            enterprise_value=ev,
            invested_capital=invested_capital,
            market_cap_b=market_cap_b,
            debt_to_equity=dte,
            earnings_yield_rank=0,  # filled in _rank()
            roc_rank=0,
            combined_rank=0,
            raw=info,
        )

    def _filter(self, results: list[ScreenerResult]) -> list[ScreenerResult]:
        out = []
        for r in results:
            if r.market_cap_b < self.min_market_cap_b:
                logger.debug(
                    f"{r.ticker}: market cap {r.market_cap_b:.1f}B < min, skip"
                )
                continue
            if r.debt_to_equity > self.max_debt_to_equity:
                logger.debug(f"{r.ticker}: D/E {r.debt_to_equity:.1f} > max, skip")
                continue
            out.append(r)
        return out

    def _rank(self, results: list[ScreenerResult]) -> list[ScreenerResult]:
        # Assign per-factor ranks in-place (one pass each), then sort once for final output
        for i, r in enumerate(
            sorted(results, key=lambda r: r.earnings_yield, reverse=True)
        ):
            r.earnings_yield_rank = i + 1

        for i, r in enumerate(
            sorted(results, key=lambda r: r.return_on_capital, reverse=True)
        ):
            r.roc_rank = i + 1

        for r in results:
            r.combined_rank = r.earnings_yield_rank + r.roc_rank

        return sorted(results, key=lambda r: r.combined_rank)
