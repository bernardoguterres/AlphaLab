"""Tests for GreenblattWeekly strategy."""

import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from alphalab.strategies.implementations.greenblatt_weekly import GreenblattWeekly


def _make_weekly_data(n=200, base_price=100.0, trend="flat", seed=42) -> pd.DataFrame:
    """Generate synthetic weekly OHLCV data with pre-computed indicators."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2016-01-04", periods=n, freq="W-MON")

    if trend == "up":
        prices = base_price + np.linspace(0, 80, n) + rng.normal(0, 2, n)
    elif trend == "down":
        prices = base_price + np.linspace(0, -60, n) + rng.normal(0, 2, n)
    else:
        prices = base_price + rng.normal(0, 5, n).cumsum() * 0.3

    prices = np.maximum(prices, 1.0)
    closes = pd.Series(prices, index=dates)

    df = pd.DataFrame(index=dates)
    df["Open"] = closes * 0.99
    df["High"] = closes * 1.02
    df["Low"] = closes * 0.98
    df["Close"] = closes
    df["Volume"] = rng.integers(1_000_000, 5_000_000, n)

    df["SMA_10"] = closes.rolling(10).mean()
    df["SMA_50"] = closes.rolling(50).mean()

    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    return df


class TestGreenblattWeekly(unittest.TestCase):

    def _run(self, data, params=None):
        """Scenario tests set specific RSI values in data["RSI"]; the
        strategy computes RSI from its rsi_period parameter (2026-10), so
        feed the prepared column through its indicator helper."""
        from unittest.mock import patch

        strat = GreenblattWeekly(params=params or {})
        with patch(
            "alphalab.strategies.implementations.greenblatt_weekly.rsi_ewm",
            lambda close, period: data["RSI"].reindex(close.index),
        ):
            return strat.generate_signals(data)

    def test_signals_dataframe_has_required_columns(self):
        signals = self._run(_make_weekly_data())
        self.assertIn("signal", signals.columns)
        self.assertIn("confidence", signals.columns)
        self.assertIn("reason", signals.columns)

    def test_signal_values_valid(self):
        signals = self._run(_make_weekly_data())
        self.assertTrue(signals["signal"].isin([-1, 0, 1]).all())

    def test_confidence_between_zero_and_one(self):
        signals = self._run(_make_weekly_data())
        self.assertTrue((signals["confidence"] >= 0.0).all())
        self.assertTrue((signals["confidence"] <= 1.0).all())

    def test_no_consecutive_buy_signals(self):
        signals = self._run(_make_weekly_data(n=200))
        buys = signals[signals["signal"] == 1]
        if len(buys) >= 2:
            indices = buys.index.tolist()
            for i in range(len(indices) - 1):
                between = signals.loc[indices[i] : indices[i + 1], "signal"]
                self.assertIn(
                    -1, between.values, "BUY followed by BUY with no SELL between"
                )

    def test_no_sell_without_position(self):
        signals = self._run(_make_weekly_data())
        in_pos = False
        for sig in signals["signal"]:
            if sig == 1:
                in_pos = True
            elif sig == -1:
                self.assertTrue(in_pos, "SELL generated with no open position")
                in_pos = False

    def test_trailing_stop_fires_on_large_drop(self):
        """A 30% drop from peak should always trigger the trailing stop (default 20%)."""
        data = _make_weekly_data(n=200, trend="up", seed=10)
        # Force entry at bar 80 via oversold RSI
        data.loc[data.index[80], "RSI"] = 25.0
        # Crash 30% at bar 100
        peak = data["Close"].iloc[80]
        data.loc[data.index[100], "Close"] = peak * 0.65

        signals = self._run(
            data, params={"min_hold_bars": 1, "trailing_stop_pct": 0.20}
        )
        sells = signals[signals["signal"] == -1]
        stop_sells = sells[sells["reason"].str.contains("Trailing stop", na=False)]
        self.assertGreater(len(stop_sells), 0, "Trailing stop should have fired")

    def test_no_rsi_exit_by_default(self):
        """RSI overbought should NOT trigger exit with default params."""
        data = _make_weekly_data(n=200, trend="up", seed=7)
        # Force entry then push RSI above 65
        data.loc[data.index[80], "RSI"] = 25.0
        for i in range(90, 110):
            data.loc[data.index[i], "RSI"] = 80.0

        signals = self._run(data, params={"min_hold_bars": 1})
        rsi_exits = signals[signals["reason"].str.contains("overbought", na=False)]
        self.assertEqual(len(rsi_exits), 0, "RSI exit should be disabled by default")

    def test_no_sma_death_cross_exit_by_default(self):
        """SMA death-cross should NOT trigger exit with default params."""
        data = _make_weekly_data(n=200, trend="up", seed=8)
        data.loc[data.index[80], "RSI"] = 25.0
        # Force death-cross at bar 100
        slow = data["SMA_50"].iloc[100]
        data.loc[data.index[99], "SMA_10"] = slow + 1
        data.loc[data.index[100], "SMA_10"] = slow - 1

        signals = self._run(data, params={"min_hold_bars": 1})
        cross_exits = signals[signals["reason"].str.contains("death-cross", na=False)]
        self.assertEqual(
            len(cross_exits), 0, "SMA death-cross exit should be disabled by default"
        )

    def test_rsi_exit_fires_when_enabled(self):
        """RSI exit SHOULD fire when exit_rsi_overbought=True and min_hold met."""
        data = _make_weekly_data(n=200, trend="up", seed=9)
        data.loc[data.index[60], "RSI"] = 25.0
        for i in range(75, 90):
            data.loc[data.index[i], "RSI"] = 80.0

        signals = self._run(
            data,
            params={
                "min_hold_bars": 10,
                "exit_rsi_overbought": True,
                "trailing_stop_pct": 0.50,  # loose stop so RSI fires first
            },
        )
        rsi_exits = signals[signals["reason"].str.contains("overbought", na=False)]
        self.assertGreater(len(rsi_exits), 0, "RSI exit should fire when enabled")

    def test_weekly_hold_preserves_calendar_labels_and_trailing_stop_priority(self):
        index = pd.to_datetime(
            ["2024-01-01", "2024-01-08", "2024-01-16", "2024-01-29"], utc=True
        )
        data = pd.DataFrame(
            {
                "Close": [100, 100, 105, 105],
                "SMA_10": [100] * 4,
                "SMA_50": [100] * 4,
                "RSI": [50, 25, 80, 80],
            },
            index=index,
        )
        params = {"min_hold_bars": 2, "exit_rsi_overbought": True}

        signals = self._run(data, params=params)
        # A UTC-midnight label still belongs to its own date. Treating it
        # as an instant in ET would move Monday Jan 8 into the prior week.
        self.assertEqual(signals["signal"].tolist(), [0, 1, 0, -1])

        data.loc[index[2], "Close"] = 75
        stop_signals = self._run(data, params=params)
        self.assertEqual(stop_signals.loc[index[2], "signal"], -1)
        self.assertTrue(
            stop_signals.loc[index[2], "reason"].startswith("Trailing stop:")
        )

    def test_default_min_hold_is_52(self):
        strat = GreenblattWeekly(params={})
        self.assertEqual(strat.params["min_hold_bars"], 52)

    def test_default_trailing_stop_is_20_pct(self):
        strat = GreenblattWeekly(params={})
        self.assertAlmostEqual(strat.params["trailing_stop_pct"], 0.20)

    def test_validate_params_fast_ge_slow_raises(self):
        with self.assertRaises(ValueError):
            GreenblattWeekly(params={"fast_sma": 50, "slow_sma": 10})

    def test_validate_params_rsi_threshold_raises(self):
        with self.assertRaises(ValueError):
            GreenblattWeekly(params={"rsi_oversold": 60, "rsi_overbought": 40})

    def test_validate_params_trailing_stop_out_of_range(self):
        with self.assertRaises(ValueError):
            GreenblattWeekly(params={"trailing_stop_pct": 0.99})

    def test_handles_insufficient_data_gracefully(self):
        data = _make_weekly_data(n=10)
        signals = self._run(data)
        self.assertTrue((signals["signal"] == 0).all())

    def test_only_close_is_required_for_indicators(self):
        strat = GreenblattWeekly(params={"fast_sma": 10, "slow_sma": 50})
        self.assertEqual(strat.required_columns(), ["Close"])


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize(
    ("endpoint", "interval", "round_trips"),
    [
        ("backtest", "1wk", 1),
        ("batch-backtest", "1wk", 1),
        ("backtest", "1d", 0),
        ("backtest", "1mo", 0),
    ],
)
def test_greenblatt_optional_exit_counts_elapsed_weeks_only_on_weekly_runs(
    endpoint, interval, round_trips
):
    from alphalab.api.routes import create_app

    warmup = pd.date_range(end="2023-12-29", periods=55, freq="W-FRI")
    index = warmup.append(
        pd.DatetimeIndex(["2024-01-05", "2024-01-12", "2024-01-26", "2024-02-02"])
    )
    close = np.array([100.0] * len(warmup) + [90.0, 91.0, 130.0, 130.0])
    bars = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )
    fetcher = Mock()
    fetcher.fetch.return_value = {"data": bars, "metadata": {"from_cache": True}}
    with patch("alphalab.api.routes.DataFetcher", return_value=fetcher):
        client = create_app().test_client()

    payload = {
        "strategy": "greenblatt_weekly",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "interval": interval,
        "params": {
            "min_hold_bars": 3,
            "exit_rsi_overbought": True,
            "exit_sma_cross": False,
        },
        "risk_settings": {"stop_loss_pct": 25.0, "take_profit_pct": 100.0},
        "drawdown_halt_enabled": False,
    }
    if endpoint == "backtest":
        payload["ticker"] = "AAPL"
    else:
        payload["tickers"] = ["AAPL"]
    response = client.post(f"/api/strategies/{endpoint}", json=payload)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]
    if endpoint == "batch-backtest":
        result = result["results"][0]
    else:
        fills = [order for order in result["trades"] if order["status"] == "filled"]
        assert [order["side"] for order in fills] == ["buy"] + ["sell"] * round_trips
        if round_trips:
            assert pd.Timestamp(fills[-1]["filled_timestamp"]) == index[-1]
    assert result["total_trades"] == round_trips


@pytest.mark.parametrize("endpoint", ["backtest", "optimize", "optimize/heatmap"])
def test_greenblatt_supports_custom_sma_windows(endpoint):
    from alphalab.api.routes import create_app

    dates = pd.date_range("2023-01-06", periods=60, freq="W-FRI")
    close = np.array([100.0] * 55 + [90.0, 95.0, 130.0, 126.0, 125.0])
    bars = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=dates,
    )
    fetcher = Mock()
    fetcher.fetch.return_value = {"data": bars}
    with patch("alphalab.api.routes.DataFetcher", return_value=fetcher):
        client = create_app().test_client()

    payload = {
        "ticker": "AAPL",
        "strategy": "greenblatt_weekly",
        "start_date": dates[0].date().isoformat(),
        "end_date": dates[-1].date().isoformat(),
        "interval": "1wk",
        "risk_settings": {"stop_loss_pct": 25.0, "take_profit_pct": 100.0},
        "drawdown_halt_enabled": False,
    }
    if endpoint == "backtest":
        payload["params"] = {"fast_sma": 7, "slow_sma": 30}
    elif endpoint == "optimize":
        payload["param_grid"] = {"fast_sma": [7, 10], "slow_sma": [30, 50]}
    else:
        payload.update(
            {
                "param1_name": "fast_sma",
                "param1_min": 7,
                "param1_max": 10,
                "param1_step": 3,
                "param2_name": "slow_sma",
                "param2_min": 30,
                "param2_max": 50,
                "param2_step": 20,
            }
        )

    response = client.post(f"/api/strategies/{endpoint}", json=payload)
    assert response.status_code == 200, response.get_json()
    result = response.json["data"]
    if endpoint == "backtest":
        assert any(
            order["side"] == "buy" and order["status"] == "filled"
            for order in result["trades"]
        )
        export = client.post(
            "/api/strategies/export", json={"backtest_id": result["backtest_id"]}
        )
        assert export.status_code == 200, export.get_json()
        assert export.json["timeframe"] == "1Week"
        params = export.json["strategy"]["parameters"]
        assert (params["fast_sma"], params["slow_sma"]) == (7, 30)
    elif endpoint == "optimize":
        candidates = {
            (candidate["params"]["fast_sma"], candidate["params"]["slow_sma"])
            for candidate in result["all_results"]
        }
        assert candidates == {(7, 30), (7, 50), (10, 30), (10, 50)}
    else:
        assert result["param1_values"] == [7, 10]
        assert result["param2_values"] == [30, 50]
        heatmap = np.asarray(result["heatmap_data"], dtype=float)
        assert heatmap.shape == (2, 2)
        assert np.isfinite(heatmap).all()
