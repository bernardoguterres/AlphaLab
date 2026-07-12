"""Tests for RelativeStrengthRanker (Levy 1967 price/SMA relative strength)."""

import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.screener.relative_strength_ranker import (
    RelativeStrengthRanker,
    RelativeStrengthResult,
    SPDR_SECTOR_ETFS,
)


def _series(closes: list[float], start="2023-01-06") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=len(closes), freq="W-FRI")
    return pd.DataFrame({"Close": closes}, index=dates)


class TestRelativeStrengthRanker:
    def test_ranks_highest_price_over_sma_ratio_first(self):
        # A: flat at 100 -> ratio 1.0. B: rose to 150, SMA(26) ~ 100 -> ratio > 1.
        flat = [100.0] * 26
        rising = [100.0] * 25 + [150.0]
        price_data = {"A": _series(flat), "B": _series(rising)}

        ranker = RelativeStrengthRanker(sma_weeks=26)
        results = ranker.rank(price_data)

        assert results[0].ticker == "B"
        assert results[0].combined_rank == 1
        assert results[1].ticker == "A"
        assert results[1].combined_rank == 2

    def test_excludes_tickers_with_insufficient_history(self):
        price_data = {
            "A": _series([100.0] * 26),
            "SHORT": _series([100.0] * 10),  # < 26 weeks
        }
        ranker = RelativeStrengthRanker(sma_weeks=26)
        results = ranker.rank(price_data)

        tickers = {r.ticker for r in results}
        assert "SHORT" not in tickers
        assert "A" in tickers

    def test_excludes_empty_or_missing_dataframes(self):
        price_data = {
            "A": _series([100.0] * 26),
            "EMPTY": pd.DataFrame({"Close": []}),
            "NONE": None,
        }
        ranker = RelativeStrengthRanker(sma_weeks=26)
        results = ranker.rank(price_data)

        tickers = {r.ticker for r in results}
        assert tickers == {"A"}

    def test_relative_strength_is_price_over_sma(self):
        closes = [100.0] * 25 + [130.0]
        price_data = {"A": _series(closes)}
        ranker = RelativeStrengthRanker(sma_weeks=26)
        results = ranker.rank(price_data)

        expected_sma = sum(closes) / 26
        assert results[0].sma == pytest.approx(expected_sma)
        assert results[0].price == pytest.approx(130.0)
        assert results[0].relative_strength == pytest.approx(130.0 / expected_sma)

    def test_returns_relative_strength_result_dataclass(self):
        price_data = {"A": _series([100.0] * 26)}
        results = RelativeStrengthRanker(sma_weeks=26).rank(price_data)
        assert isinstance(results[0], RelativeStrengthResult)

    def test_downtrending_ticker_ranks_last(self):
        strong = [100.0] * 25 + [140.0]
        weak = [100.0] * 25 + [60.0]
        flat = [100.0] * 26
        price_data = {
            "strong": _series(strong),
            "weak": _series(weak),
            "flat": _series(flat),
        }

        results = RelativeStrengthRanker(sma_weeks=26).rank(price_data)
        ordered = [r.ticker for r in results]
        assert ordered == ["strong", "flat", "weak"]

    def test_custom_sma_window(self):
        closes = [100.0] * 9 + [120.0]
        price_data = {"A": _series(closes)}
        results = RelativeStrengthRanker(sma_weeks=10).rank(price_data)
        assert len(results) == 1
        assert results[0].ticker == "A"

    def test_universe_constant_has_eleven_sector_etfs(self):
        assert len(SPDR_SECTOR_ETFS) == 11
        assert len(set(SPDR_SECTOR_ETFS)) == 11  # no duplicates
        assert "XLK" in SPDR_SECTOR_ETFS  # Technology
        assert "XLC" in SPDR_SECTOR_ETFS  # Communication Services

    def test_empty_universe_returns_empty_list(self):
        assert RelativeStrengthRanker().rank({}) == []
