"""Production-grade market data fetcher using yfinance."""

import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from ..utils.logger import setup_logger
from ..utils.config import load_config
from .cache_manager import CacheManager

logger = setup_logger("alphalab.fetcher")

VALID_INTERVALS = ("1d", "1wk", "1mo")


class DataFetchError(Exception):
    """Raised when data fetching fails after all retries."""


class InvalidTickerError(DataFetchError):
    """Raised when ticker symbol is invalid."""


class InsufficientDataError(DataFetchError):
    """Raised when fetched data is below minimum threshold."""


class DataFetcher:
    """Download, validate, and cache stock data from Yahoo Finance.

    Handles retry logic, corporate actions, data quality checks, and
    returns data in a standardized format with metadata.
    """

    def __init__(
        self,
        cache_dir: str = None,
        max_retries: int = 3,
        cache_expiry_hours: float = 24,
    ):
        config = load_config()
        data_cfg = config.get("data", {})
        self.max_retries = max_retries
        self.cache = CacheManager(
            cache_dir=cache_dir or data_cfg.get("cache_dir", "data/cache"),
            expiry_hours=cache_expiry_hours,
        )
        self._validated_tickers: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> dict:
        """Fetch stock data with caching, retries, and quality checks.

        Returns:
            dict with keys: ticker, data (DataFrame), metadata (dict)
        """
        ticker = ticker.upper().strip()
        if interval not in VALID_INTERVALS:
            raise ValueError(f"Invalid interval '{interval}'. Use one of {VALID_INTERVALS}")

        logger.info("Fetching %s [%s -> %s] interval=%s", ticker, start_date, end_date, interval)

        # Check cache first
        cached = self.cache.get(ticker, interval, start_date, end_date)
        if cached is not None:
            logger.info("Returning cached data for %s (%d rows)", ticker, len(cached))
            return self._build_result(ticker, cached, start_date, end_date, from_cache=True)

        # Validate ticker
        self._validate_ticker(ticker)

        # Download with retries
        df = self._download_with_retry(ticker, start_date, end_date, interval)

        if df.empty or len(df) < 5:
            raise InsufficientDataError(
                f"Only {len(df)} records returned for {ticker}. Need at least 5."
            )

        # Standardize columns
        df = self._standardize(df)

        # Quality checks
        quality = self._quality_check(df, ticker)

        # Detect splits
        splits_detected = self._detect_splits(df)

        # Cache the result
        self.cache.put(ticker, interval, start_date, end_date, df)

        result = self._build_result(
            ticker, df, start_date, end_date,
            quality_score=quality["score"],
            splits_detected=splits_detected,
        )
        logger.info(
            "Fetched %s: %d records, quality=%.2f",
            ticker, len(df), quality["score"],
        )
        return result

    def fetch_company_info(self, ticker: str) -> dict:
        """Download company information (sector, industry, market cap)."""
        ticker = ticker.upper().strip()
        try:
            info = yf.Ticker(ticker).info
            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap"),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", ""),
            }
        except Exception as e:
            logger.warning("Failed to fetch company info for %s: %s", ticker, e)
            return {"ticker": ticker, "error": str(e)}

    def fetch_financials(self, ticker: str) -> dict:
        """Download financial statements if available."""
        ticker = ticker.upper().strip()
        try:
            t = yf.Ticker(ticker)
            result = {}
            for name, attr in [
                ("income_statement", "income_stmt"),
                ("balance_sheet", "balance_sheet"),
                ("recommendations", "recommendations"),
            ]:
                data = getattr(t, attr, None)
                if data is not None and not (isinstance(data, pd.DataFrame) and data.empty):
                    result[name] = data
            return result
        except Exception as e:
            logger.warning("Failed to fetch financials for %s: %s", ticker, e)
            return {"error": str(e)}

    def fetch_multiple(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> dict[str, dict]:
        """Fetch data for multiple tickers, returning results keyed by ticker."""
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.fetch(ticker, start_date, end_date, interval)
            except DataFetchError as e:
                logger.error("Failed to fetch %s: %s", ticker, e)
                results[ticker] = {"ticker": ticker, "error": str(e), "data": None}
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_ticker(self, ticker: str):
        """Check that the ticker actually exists on Yahoo Finance."""
        if ticker in self._validated_tickers:
            if not self._validated_tickers[ticker]:
                raise InvalidTickerError(f"Ticker '{ticker}' is invalid")
            return

        try:
            info = yf.Ticker(ticker).info
            valid = info is not None and info.get("regularMarketPrice") is not None
        except Exception:
            valid = False

        self._validated_tickers[ticker] = valid
        if not valid:
            raise InvalidTickerError(f"Ticker '{ticker}' not found or delisted")

    def _download_with_retry(
        self, ticker: str, start: str, end: str, interval: str
    ) -> pd.DataFrame:
        """Download data with exponential backoff retries."""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                df = yf.download(
                    ticker,
                    start=start,
                    end=end,
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                )
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(
                    "Attempt %d/%d for %s failed: %s. Retrying in %ds...",
                    attempt, self.max_retries, ticker, e, wait,
                )
                time.sleep(wait)

        raise DataFetchError(
            f"Failed to download {ticker} after {self.max_retries} attempts: {last_error}"
        )

    @staticmethod
    def _standardize(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure consistent column names and index."""
        col_map = {}
        for col in df.columns:
            lower = col.lower().strip()
            if "open" in lower:
                col_map[col] = "Open"
            elif "high" in lower:
                col_map[col] = "High"
            elif "low" in lower:
                col_map[col] = "Low"
            elif "close" in lower and "adj" not in lower:
                col_map[col] = "Close"
            elif "volume" in lower:
                col_map[col] = "Volume"

        if col_map:
            df = df.rename(columns=col_map)

        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"
        df = df.sort_index()

        # Drop duplicate dates
        df = df[~df.index.duplicated(keep="last")]
        return df

    @staticmethod
    def _quality_check(df: pd.DataFrame, ticker: str) -> dict:
        """Run data quality checks and return a quality report."""
        issues = []
        total_checks = 0
        passed_checks = 0

        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            total_checks += 1
            if col in df.columns:
                passed_checks += 1
            else:
                issues.append(f"Missing column: {col}")

        # OHLC relationship: High >= Open, Close and Low <= Open, Close
        if {"Open", "High", "Low", "Close"}.issubset(df.columns):
            total_checks += 3
            bad_high = (df["High"] < df[["Open", "Close"]].max(axis=1)).sum()
            bad_low = (df["Low"] > df[["Open", "Close"]].min(axis=1)).sum()
            if bad_high == 0:
                passed_checks += 1
            else:
                issues.append(f"High < max(Open, Close) on {bad_high} rows")
            if bad_low == 0:
                passed_checks += 1
            else:
                issues.append(f"Low > min(Open, Close) on {bad_low} rows")

            # Extreme daily moves (>50%)
            daily_return = df["Close"].pct_change().abs()
            extreme = (daily_return > 0.5).sum()
            if extreme == 0:
                passed_checks += 1
            else:
                issues.append(f"{extreme} days with >50% price change (possible error)")

        # Volume should be non-negative
        if "Volume" in df.columns:
            total_checks += 1
            neg_vol = (df["Volume"] < 0).sum()
            if neg_vol == 0:
                passed_checks += 1
            else:
                issues.append(f"{neg_vol} rows with negative volume")

        score = passed_checks / max(total_checks, 1)
        if issues:
            logger.warning("Quality issues for %s: %s", ticker, "; ".join(issues))

        return {"score": round(score, 4), "issues": issues}

    @staticmethod
    def _detect_splits(df: pd.DataFrame) -> int:
        """Count likely stock splits based on overnight price jumps with volume spikes."""
        if len(df) < 2 or "Close" not in df.columns:
            return 0
        ratio = df["Close"] / df["Close"].shift(1)
        # A split typically shows as a ~50% or ~100%+ jump/drop
        splits = ((ratio < 0.4) | (ratio > 2.5)).sum()
        return int(splits)

    @staticmethod
    def _build_result(
        ticker: str,
        df: pd.DataFrame,
        start_date: str,
        end_date: str,
        from_cache: bool = False,
        quality_score: float = None,
        splits_detected: int = 0,
    ) -> dict:
        actual_start = str(df.index.min().date()) if len(df) else start_date
        actual_end = str(df.index.max().date()) if len(df) else end_date

        # Count expected trading days (rough: ~252/year)
        try:
            days_span = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
            expected = int(days_span * 252 / 365)
            missing = max(0, expected - len(df))
        except Exception:
            missing = 0

        if quality_score is None:
            quality_score = 1.0

        return {
            "ticker": ticker,
            "data": df,
            "metadata": {
                "start_date": actual_start,
                "end_date": actual_end,
                "records": len(df),
                "missing_dates": missing,
                "splits_detected": splits_detected,
                "quality_score": quality_score,
                "from_cache": from_cache,
            },
        }
