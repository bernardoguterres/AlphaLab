"""Protective exits are checked against each bar's range and filled within
the bar, as AlphaLive does with live prices (bug X2). They used to be checked
on the close and filled at the next open, so the backtest missed intraday
breaches and let gaps run further than the live bot would."""

import numpy as np
import pandas as pd
import pytest

from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.portfolio import Portfolio
from alphalab.strategies.base_strategy import BaseStrategy


def _held(**kw):
    p = Portfolio(initial_capital=100_000, **kw)
    p.positions["X"] = 10
    p.avg_cost["X"] = 100.0
    return p


class TestCheckIntrabarExit:
    def test_wick_below_stop_fills_at_stop_level(self):
        p = _held(stop_loss_pct=5.0)
        reason, price = p.check_intrabar_exit("X", 99.0, 101.0, 94.0)
        assert "Stop-loss" in reason
        assert price == pytest.approx(95.0)

    def test_close_based_check_would_have_missed_it(self):
        p = _held(stop_loss_pct=5.0)
        # low 94 breaches the 95 stop although the close (98) does not
        assert p.check_risk_overlay_exit("X", 98.0) is None
        assert p.check_intrabar_exit("X", 99.0, 101.0, 94.0) is not None

    def test_gap_through_stop_fills_at_open(self):
        p = _held(stop_loss_pct=5.0)
        reason, price = p.check_intrabar_exit("X", 90.0, 92.0, 89.0)
        assert "Stop-loss" in reason
        assert price == pytest.approx(90.0)

    def test_take_profit_intrabar_and_gap(self):
        p = _held(take_profit_pct=10.0)
        assert p.check_intrabar_exit("X", 105.0, 111.0, 104.0)[1] == pytest.approx(
            110.0
        )
        assert p.check_intrabar_exit("X", 113.0, 114.0, 112.0)[1] == pytest.approx(
            113.0
        )

    def test_stop_and_target_in_one_bar_assumes_stop(self):
        p = _held(stop_loss_pct=5.0, take_profit_pct=10.0)
        reason, price = p.check_intrabar_exit("X", 100.0, 112.0, 94.0)
        assert "Stop-loss" in reason and price == pytest.approx(95.0)

    def test_trailing_uses_earlier_peak_and_higher_of_two_stops(self):
        p = _held(stop_loss_pct=5.0, trailing_stop_pct=10.0)
        p.trailing_stops["X"] = 90.0
        p.update_trailing_stops({"X": 120.0})  # earlier bar's high -> 108
        reason, price = p.check_intrabar_exit("X", 115.0, 116.0, 107.0)
        assert "Trailing" in reason and price == pytest.approx(108.0)

    def test_no_position_or_no_levels(self):
        assert (
            Portfolio(initial_capital=1000).check_intrabar_exit("X", 1, 2, 0.5) is None
        )
        assert _held().check_intrabar_exit("X", 100.0, 200.0, 1.0) is None


class _BuyOnce(BaseStrategy):
    name = "buy_once"

    def validate_params(self):
        pass

    def required_columns(self):
        return ["Close"]

    def generate_signals(self, data):
        s = self._init_signals_frame(data)
        s.iloc[2, s.columns.get_loc("signal")] = 1
        return s


def _bars(lows):
    n = len(lows)
    idx = pd.bdate_range("2024-01-02", periods=n)
    close = np.full(n, 100.0)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": np.asarray(lows, dtype=float),
            "Close": close,
            "Volume": np.full(n, 1e6),
        },
        index=idx,
    )


def test_engine_exits_within_the_breaching_bar():
    lows = [99.0] * 12
    lows[6] = 90.0  # one intraday wick, closes back at 100
    data = _bars(lows)
    data.attrs["ticker"] = "X"
    res = BacktestEngine().run_backtest(
        _BuyOnce(),
        data,
        initial_capital=10_000,
        risk_settings={"stop_loss_pct": 5.0},
        drawdown_halt_enabled=False,
    )
    sells = [t for t in res.trades if t["side"] == "sell"]
    assert len(sells) == 1
    assert str(sells[0]["timestamp"])[:10] == str(data.index[6])[:10]
    # filled at the stop level (entry ~100.05 incl. slippage) less slippage
    assert sells[0]["filled_price"] == pytest.approx(
        100.05 * 0.95 * (1 - 0.0005), rel=2e-3
    )
