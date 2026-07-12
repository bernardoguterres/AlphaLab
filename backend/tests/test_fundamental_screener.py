"""Tests for FundamentalScreener (true Greenblatt Magic Formula: EBIT/EV + EBIT/(NWC+NetPPE))."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.screener.fundamental_screener import FundamentalScreener, ScreenerResult


def _make_info(
    enterprise_value=1000e9,
    market_cap=900e9,
    dte=0.5,
    name="Test Co",
    sector="Technology",
):
    return {
        "enterpriseValue": enterprise_value,
        "marketCap": market_cap,
        "debtToEquity": dte,
        "shortName": name,
        "sector": sector,
        "regularMarketPrice": 100.0,
    }


def _make_income_stmt(ebit=50e9):
    return pd.DataFrame({"2025-09-30": [ebit]}, index=["EBIT"])


def _make_balance_sheet(working_capital=10e9, net_ppe=20e9):
    return pd.DataFrame(
        {"2025-09-30": [working_capital, net_ppe]},
        index=["Working Capital", "Net PPE"],
    )


def _mock_ticker(info, income_stmt, balance_sheet):
    t = MagicMock()
    t.info = info
    t.income_stmt = income_stmt
    t.balance_sheet = balance_sheet
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
        specs = {
            # A: EY=50/500=0.10 (best), ROC=50/20=2.5 (best) -> should rank first
            "A": (
                _make_info(enterprise_value=500e9),
                _make_income_stmt(50e9),
                _make_balance_sheet(10e9, 10e9),
            ),
            # B: EY=20/800=0.025 (worst), ROC=20/40=0.5 (worst)
            "B": (
                _make_info(enterprise_value=800e9),
                _make_income_stmt(20e9),
                _make_balance_sheet(20e9, 20e9),
            ),
            # C: mid on both
            "C": (
                _make_info(enterprise_value=600e9),
                _make_income_stmt(30e9),
                _make_balance_sheet(15e9, 15e9),
            ),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener()
        results = screener.screen(top_n=3)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].ticker, "A")

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_earnings_yield_is_ebit_over_ev(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(enterprise_value=1000e9),
            _make_income_stmt(50e9),
            _make_balance_sheet(10e9, 20e9),
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.earnings_yield, 50e9 / 1000e9, places=6)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_return_on_capital_is_ebit_over_nwc_plus_net_ppe(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(),
            _make_income_stmt(50e9),
            _make_balance_sheet(working_capital=10e9, net_ppe=20e9),
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.invested_capital, 30e9, places=2)
        self.assertAlmostEqual(result.return_on_capital, 50e9 / 30e9, places=6)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_negative_working_capital_still_ranked_if_invested_capital_positive(
        self, mock_ticker_cls
    ):
        # Real-world case (e.g. Apple): negative working capital, large net PPE,
        # net invested capital still positive - must not be excluded.
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(),
            _make_income_stmt(130e9),
            _make_balance_sheet(working_capital=-17e9, net_ppe=45e9),
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.invested_capital, 28e9, places=2)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_falls_back_to_current_assets_minus_liabilities_when_no_working_capital_row(
        self, mock_ticker_cls
    ):
        bs = pd.DataFrame(
            {"2025-09-30": [40e9, 25e9, 20e9]},
            index=["Current Assets", "Current Liabilities", "Net PPE"],
        )
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(), _make_income_stmt(50e9), bs
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNotNone(result)
        # NWC = 40 - 25 = 15; invested_capital = 15 + 20 = 35
        self.assertAlmostEqual(result.invested_capital, 35e9, places=2)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_negative_ebit_excluded(self, mock_ticker_cls):
        specs = {
            "A": (_make_info(), _make_income_stmt(-5e9), _make_balance_sheet()),
            "B": (_make_info(), _make_income_stmt(20e9), _make_balance_sheet()),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)
        self.assertIn("B", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_negative_invested_capital_excluded(self, mock_ticker_cls):
        specs = {
            # NWC + NetPPE = -50 + 10 = -40 <= 0 -> excluded, ratio not meaningful
            "A": (
                _make_info(),
                _make_income_stmt(20e9),
                _make_balance_sheet(working_capital=-50e9, net_ppe=10e9),
            ),
            "B": (_make_info(), _make_income_stmt(20e9), _make_balance_sheet()),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_missing_ebit_returns_none(self, mock_ticker_cls):
        empty_income = pd.DataFrame({"2025-09-30": []}, index=[])
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(), empty_income, _make_balance_sheet()
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNone(result)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_missing_enterprise_value_returns_none(self, mock_ticker_cls):
        info = _make_info()
        info["enterpriseValue"] = None
        mock_ticker_cls.return_value = _mock_ticker(
            info, _make_income_stmt(), _make_balance_sheet()
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNone(result)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_financials_sector_excluded_by_default(self, mock_ticker_cls):
        specs = {
            "A": (
                _make_info(sector="Financial Services"),
                _make_income_stmt(),
                _make_balance_sheet(),
            ),
            "B": (
                _make_info(sector="Technology"),
                _make_income_stmt(),
                _make_balance_sheet(),
            ),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)
        self.assertIn("B", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_utilities_sector_excluded_by_default(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(sector="Utilities"), _make_income_stmt(), _make_balance_sheet()
        )
        screener = FundamentalScreener(universe=["X"], request_delay=0.0)
        result = screener.fetch_one("X")

        self.assertIsNone(result)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_can_disable_sector_exclusion(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _mock_ticker(
            _make_info(sector="Utilities"), _make_income_stmt(), _make_balance_sheet()
        )
        screener = FundamentalScreener(
            universe=["X"], request_delay=0.0, exclude_financials_utilities=False
        )
        result = screener.fetch_one("X")

        self.assertIsNotNone(result)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_filters_out_small_cap(self, mock_ticker_cls):
        specs = {
            "A": (
                _make_info(market_cap=500_000_000),
                _make_income_stmt(),
                _make_balance_sheet(),
            ),
            "B": (
                _make_info(market_cap=5_000_000_000),
                _make_income_stmt(),
                _make_balance_sheet(),
            ),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)
        self.assertIn("B", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_filters_out_high_debt(self, mock_ticker_cls):
        specs = {
            "A": (_make_info(dte=300.0), _make_income_stmt(), _make_balance_sheet()),
            "B": (_make_info(dte=50.0), _make_income_stmt(), _make_balance_sheet()),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        tickers = [r.ticker for r in results]
        self.assertNotIn("A", tickers)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_handles_fetch_failure_gracefully(self, mock_ticker_cls):
        def side_effect(ticker):
            if ticker == "BAD":
                raise Exception("Network error")
            return _mock_ticker(
                _make_info(), _make_income_stmt(), _make_balance_sheet()
            )

        mock_ticker_cls.side_effect = side_effect

        screener = self._make_screener(["BAD", "GOOD"])
        results = screener.screen(top_n=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ticker, "GOOD")

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_top_n_limits_output(self, mock_ticker_cls):
        tickers = [f"T{i}" for i in range(10)]
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(
            _make_info(enterprise_value=(500 + tickers.index(t)) * 1e9),
            _make_income_stmt(),
            _make_balance_sheet(),
        )

        screener = FundamentalScreener(universe=tickers, request_delay=0.0)
        results = screener.screen(top_n=3)

        self.assertLessEqual(len(results), 3)

    @patch("src.screener.fundamental_screener.yf.Ticker")
    def test_combined_rank_is_sum_of_individual_ranks(self, mock_ticker_cls):
        specs = {
            "A": (
                _make_info(enterprise_value=500e9),
                _make_income_stmt(50e9),
                _make_balance_sheet(),
            ),
            "B": (
                _make_info(enterprise_value=900e9),
                _make_income_stmt(10e9),
                _make_balance_sheet(),
            ),
        }
        mock_ticker_cls.side_effect = lambda t: _mock_ticker(*specs[t])

        screener = self._make_screener(["A", "B"])
        results = screener.screen(top_n=5)

        for r in results:
            self.assertEqual(r.combined_rank, r.earnings_yield_rank + r.roc_rank)


if __name__ == "__main__":
    unittest.main()
