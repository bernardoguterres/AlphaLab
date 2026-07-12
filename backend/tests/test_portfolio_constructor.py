"""Tests for PortfolioConstructor (cross-sectional rank -> top-N -> sized basket)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.portfolio_constructor import PortfolioConstructor


@dataclass
class _FakeCandidate:
    ticker: str
    combined_rank: int


def _make_price_data(tickers, n=120, seed=42, start="2021-01-01", drift=None):
    """Synthetic weekly Close-price series per ticker, common DatetimeIndex."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start, periods=n, freq="W-FRI")
    data = {}
    for i, t in enumerate(tickers):
        mu = (drift or {}).get(t, 0.001)
        rets = rng.normal(mu, 0.02, n)
        close = 100 * np.cumprod(1 + rets)
        data[t] = pd.DataFrame({"Close": close}, index=dates)
    return data


class TestPortfolioConstructor:
    """Tests for PortfolioConstructor class."""

    def test_selects_top_n_by_combined_rank(self):
        candidates = [
            _FakeCandidate("A", combined_rank=5),
            _FakeCandidate("B", combined_rank=1),
            _FakeCandidate("C", combined_rank=10),
            _FakeCandidate("D", combined_rank=3),
        ]
        price_data = _make_price_data(["A", "B", "C", "D"])
        pc = PortfolioConstructor(top_n=2, rebalance_period_bars=52)
        result = pc.run(candidates, price_data)

        assert set(result.tickers_used) == {"B", "D"}

    def test_equal_weight_target_at_first_rebalance(self):
        candidates = [
            _FakeCandidate(t, combined_rank=i) for i, t in enumerate(["A", "B", "C"])
        ]
        price_data = _make_price_data(["A", "B", "C"])
        pc = PortfolioConstructor(top_n=3, rebalance_period_bars=52)
        result = pc.run(candidates, price_data)

        first_rebalance_date = result.rebalance_history[0].date
        first_batch = [
            r for r in result.rebalance_history if r.date == first_rebalance_date
        ]
        assert len(first_batch) == 3
        for r in first_batch:
            assert r.target_weight == pytest.approx(1.0 / 3.0)

    def test_raises_with_fewer_than_two_tickers_available(self):
        candidates = [_FakeCandidate("A", combined_rank=1)]
        price_data = _make_price_data(["A"])
        pc = PortfolioConstructor(top_n=5, rebalance_period_bars=52)

        with pytest.raises(ValueError):
            pc.run(candidates, price_data)

    def test_missing_price_data_ticker_is_skipped_not_fatal(self):
        candidates = [
            _FakeCandidate("A", combined_rank=1),
            _FakeCandidate("B", combined_rank=2),
            _FakeCandidate("NODATA", combined_rank=3),
        ]
        price_data = _make_price_data(["A", "B"])  # NODATA missing entirely
        pc = PortfolioConstructor(top_n=3, rebalance_period_bars=52)
        result = pc.run(candidates, price_data)

        assert "NODATA" not in result.tickers_used
        assert set(result.tickers_used) == {"A", "B"}

    def test_equity_curve_is_nondecreasing_length_and_starts_near_initial_capital(self):
        candidates = [
            _FakeCandidate(t, combined_rank=i) for i, t in enumerate(["A", "B"])
        ]
        price_data = _make_price_data(["A", "B"], n=60)
        pc = PortfolioConstructor(
            top_n=2, rebalance_period_bars=52, initial_capital=50_000.0
        )
        result = pc.run(candidates, price_data)

        assert len(result.equity_curve) == 60
        # First bar is a rebalance bar (i=0), so value should be close to
        # initial capital minus slippage/commission on the initial buys, not
        # wildly different.
        first_value = result.equity_curve[0]["value"]
        assert 45_000.0 < first_value <= 50_000.0

    def test_rebalances_at_configured_period(self):
        candidates = [
            _FakeCandidate(t, combined_rank=i) for i, t in enumerate(["A", "B"])
        ]
        price_data = _make_price_data(["A", "B"], n=120)
        pc = PortfolioConstructor(top_n=2, rebalance_period_bars=52)
        result = pc.run(candidates, price_data)

        rebalance_dates = sorted(set(r.date for r in result.rebalance_history))
        # 120 bars, rebalance every 52 -> bars 0, 52, 104 -> 3 rebalance events
        assert len(rebalance_dates) == 3

    def test_only_equal_weight_supported(self):
        with pytest.raises(NotImplementedError):
            PortfolioConstructor(weighting="rank_weighted")

    def test_default_drawdown_halt_is_wider_than_portfolio_default(self):
        # Portfolio's own default (10%) is tuned for intraday/daily strategies
        # and halts far too early for a periodically-rebalanced basket - the
        # same failure mode GreenblattWeekly needed max_drawdown_pct=40 to
        # avoid. A sharp drawdown mid-window must not silently freeze further
        # rebalancing under PortfolioConstructor's own default.
        candidates = [
            _FakeCandidate(t, combined_rank=i) for i, t in enumerate(["A", "B"])
        ]
        dates = pd.bdate_range("2021-01-01", periods=110, freq="W-FRI")
        # Sharp ~25% crash right after bar 5, well past Portfolio's 10% default
        # but within PortfolioConstructor's wider default.
        close_a = [100.0] * 5 + [75.0] * 105
        close_b = [100.0] * 5 + [75.0] * 105
        price_data = {
            "A": pd.DataFrame({"Close": close_a}, index=dates),
            "B": pd.DataFrame({"Close": close_b}, index=dates),
        }
        pc = PortfolioConstructor(top_n=2, rebalance_period_bars=52)
        result = pc.run(candidates, price_data)

        assert result.final_portfolio.halted is False
        # Second rebalance (bar 52) must still have executed real trades.
        second_rebalance_date = sorted(set(r.date for r in result.rebalance_history))[1]
        fills_after_first = [
            t
            for t in result.final_portfolio.ledger
            if t["status"] == "filled" and t["timestamp"] == str(second_rebalance_date)
        ]
        assert len(fills_after_first) > 0

    def test_rebalance_history_records_price_and_rank(self):
        candidates = [
            _FakeCandidate("A", combined_rank=7),
            _FakeCandidate("B", combined_rank=2),
        ]
        price_data = _make_price_data(["A", "B"])
        pc = PortfolioConstructor(top_n=2, rebalance_period_bars=52)
        result = pc.run(candidates, price_data)

        a_rows = [r for r in result.rebalance_history if r.ticker == "A"]
        assert all(r.rank == 7 for r in a_rows)
        assert all(r.price > 0 for r in a_rows)

    def test_target_shares_scale_with_portfolio_value(self):
        candidates = [
            _FakeCandidate(t, combined_rank=i) for i, t in enumerate(["A", "B"])
        ]
        price_data = _make_price_data(["A", "B"], n=60)
        pc_small = PortfolioConstructor(
            top_n=2, rebalance_period_bars=52, initial_capital=10_000.0
        )
        pc_large = PortfolioConstructor(
            top_n=2, rebalance_period_bars=52, initial_capital=100_000.0
        )

        result_small = pc_small.run(candidates, price_data)
        result_large = pc_large.run(candidates, price_data)

        small_shares = sum(r.target_shares for r in result_small.rebalance_history[:2])
        large_shares = sum(r.target_shares for r in result_large.rebalance_history[:2])
        assert large_shares > small_shares
