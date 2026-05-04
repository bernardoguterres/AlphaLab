"""Tests for FundamentalScreener."""

import unittest
from unittest.mock import MagicMock, patch

from src.screener.fundamental_screener import FundamentalScreener, ScreenerResult


def _make_info(pe=15.0, roe=0.20, market_cap=5e9, dte=0.5, name="Test Co", sector="Tech"):
    return {
        "trailingPE": pe,
        "returnOnEquity": roe,
        "marketCap": market_cap,
        "debtToEquity": dte,
        "shortName": name,
        "sector": sector,
        "regularMarketPrice": 100.0,
    }


def _mock_ticker(info: dict):
    t = MagicMock()
    t.info = info
    return t


class TestFundamentalScreener(unittest.TestCase):

    def _make_screener(self, tickers=None):
        return FundamentalScreener(
            universe=tickers or ["A", "B", "C"],
            min_market_cap_b=1.0,
            max_debt_to_equity=2.0,
            request_delay=0.0,
        )

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_basic_screen_returns_ranked_results(self, mock_ticker_cls):
        infos = {
            "A": _make_info(pe=10.0, roe=0.30),   # High EY (0.10), high ROE
            "B": _make_info(pe=20.0, roe=0.10),   # Low EY (0.05), low ROE
            "C": _make_info(pe=15.0, roe=0.20),   # Mid EY (0.067), mid ROE
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(infos[t])

        screener = self._make_screener()
        results = screener.screen(top_n=3)

        self.assertEqual(len(results), 3)
        # A should rank first: best earnings yield AND best ROE
        self.assertEqual(results[0].ticker, "A")

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_filters_out_small_cap(self, mock_ticker_cls):
        infos = {
            "A": _make_info(pe=10.0, roe=0.30, market_cap=500_000_000),  # 0.5B < 1B
            "B": _make_info(pe=15.0, roe=0.20, market_cap=5_000_000_000),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(infos[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)
        self.assertIn("B", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_filters_out_high_debt(self, mock_ticker_cls):
        # yfinance debtToEquity is a percentage: 300 = 300% = 3.0× ratio (filtered out)
        infos = {
            "A": _make_info(pe=10.0, roe=0.30, dte=300.0),  # 3.0× D/E → filtered
            "B": _make_info(pe=15.0, roe=0.20, dte=50.0),   # 0.5× D/E → passes
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(infos[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_skips_negative_pe(self, mock_ticker_cls):
        infos = {
            "A": _make_info(pe=-5.0, roe=0.30),   # Negative P/E (loss-making)
            "B": _make_info(pe=15.0, roe=0.20),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(infos[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_handles_fetch_failure_gracefully(self, mock_ticker_cls):
        def side_effect(ticker):
            if ticker == "BAD":
                raise Exception("Network error")
            return _mock_ticker(_make_info())
        mock_ticker_cls.side_effect = side_effect

        screener = self._make_screener(["BAD", "GOOD"])
        results = screener.screen(top_n=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ticker, "GOOD")

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_top_n_limits_output(self, mock_ticker_cls):
        tickers = [f"T{i}" for i in range(10)]
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(
            _make_info(pe=float(tickers.index(t) + 5))
        )

        screener = FundamentalScreener(universe=tickers, request_delay=0.0)
        results = screener.screen(top_n=3)

        self.assertLessEqual(len(results), 3)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_combined_rank_is_sum_of_individual_ranks(self, mock_ticker_cls):
        infos = {
            "A": _make_info(pe=10.0, roe=0.30),
            "B": _make_info(pe=20.0, roe=0.10),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(infos[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        for r in results:
            self.assertEqual(r.combined_rank, r.earnings_yield_rank + r.roe_rank)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_earnings_yield_is_inverse_of_pe(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _mock_ticker(_make_info(pe=20.0, roe=0.15))

        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.earnings_yield, 1.0 / 20.0, places=5)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_missing_pe_returns_none(self, mock_ticker_cls):
        info = _make_info()
        info["trailingPE"] = None
        mock_ticker_cls.return_value = _mock_ticker(info)

        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNone(result)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_missing_roe_returns_none(self, mock_ticker_cls):
        info = _make_info()
        info["returnOnEquity"] = None
        mock_ticker_cls.return_value = _mock_ticker(info)

        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
