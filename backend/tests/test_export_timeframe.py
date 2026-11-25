"""B7: AlphaLive trades daily and weekly bars only. A monthly backtest used to
export as timeframe 1Day, so live re-evaluated a monthly strategy daily."""

import pytest

from alphalab.api.helpers import _export_timeframe
from alphalab.api.routes import create_app
from alphalab.strategies.implementations.moving_average_crossover import (
    MovingAverageCrossover,
)


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _store(client, interval, strategy="ma_crossover"):
    if strategy == "greenblatt_weekly":
        from alphalab.strategies.implementations.greenblatt_weekly import (
            GreenblattWeekly,
        )

        params = GreenblattWeekly().params
    else:
        params = MovingAverageCrossover().params
    client.application.extensions["results_store"][f"bt_{interval}"] = {
        "results": {
            "total_return_pct": 10.0,
            "total_trades": 3,
            "metrics": {
                "risk": {"sharpe_ratio": 1.0, "sortino_ratio": 1.2},
                "drawdown": {"max_drawdown_pct": -5.0},
                "trades": {"win_rate": 0.6, "profit_factor": 1.4},
            },
            "drawdown_halt": {"threshold_pct": None},
        },
        "request": {
            "ticker": "AAPL",
            "strategy": strategy,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100_000,
            "params": params,
            "risk_settings": {
                "stop_loss_pct": 2.0,
                "take_profit_pct": 5.0,
                "max_position_size_pct": 10.0,
                "max_daily_loss_pct": 3.0,
                "max_open_positions": 5,
                "trailing_stop_enabled": False,
                "trailing_stop_pct": 3.0,
                "commission_per_trade": 0.0,
            },
            "interval": interval,
        },
    }
    return client.post("/api/strategies/export", json={"backtest_id": f"bt_{interval}"})


def test_monthly_backtest_is_refused(client):
    resp = _store(client, "1mo")
    assert resp.status_code == 422
    assert "1mo" in resp.get_json()["message"]


@pytest.mark.parametrize("interval,timeframe", [("1d", "1Day"), ("1wk", "1Week")])
def test_daily_and_weekly_export_their_timeframe(client, interval, timeframe):
    resp = _store(client, interval)
    assert resp.status_code == 200
    assert resp.get_json()["timeframe"] == timeframe


def test_mapping_never_defaults_to_daily():
    with pytest.raises(ValueError):
        _export_timeframe("1mo")


@pytest.mark.parametrize("interval,expected", [("1d", 422), ("1wk", 200)])
def test_greenblatt_export_requires_weekly_bars(client, interval, expected):
    response = _store(client, interval, "greenblatt_weekly")
    assert response.status_code == expected
    if expected == 200:
        assert response.json["timeframe"] == "1Week"
        assert response.json["strategy"]["parameters"]["min_hold_bars"] == 52
    else:
        assert "weekly bars" in response.json["message"]
