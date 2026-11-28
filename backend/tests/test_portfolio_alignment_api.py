from unittest.mock import patch

import pandas as pd
import pytest

from alphalab.api.routes import create_app


def curve(dates, values, interval="1d"):
    return {
        "request": {"interval": interval},
        "results": {
            "equity_curve": [
                {"date": date.isoformat(), "value": value}
                for date, value in zip(pd.DatetimeIndex(dates), values)
            ]
        },
    }


def optimize(*curves):
    with patch("alphalab.api.routes.DataFetcher"):
        app = create_app()
    app.extensions["results_store"].update(
        {str(i): item for i, item in enumerate(curves)}
    )
    with app.test_client() as client:
        return client.post(
            "/api/portfolio/optimize",
            json={
                "method": "equal_weight",
                "strategies": [
                    {"backtest_id": str(i), "ticker": f"T{i}", "strategy": "test"}
                    for i in range(len(curves))
                ],
            },
        )


def test_missing_observation_does_not_repeat_previous_gain():
    dates = pd.bdate_range("2024-01-02", periods=5)
    response = optimize(
        curve(dates.delete(2), [100, 110, 110, 110]),
        curve(dates, [100] * 5),
    )
    assert response.status_code == 200, response.json
    data = response.json["data"]
    assert data["optimal_weights"] == [0.5, 0.5]
    # One +10% day and three flat days across the common observed window.
    assert data["expected_return"] == pytest.approx(0.5 * (0.10 / 4) * 252)


def test_nonoverlapping_equity_returns_are_rejected():
    response = optimize(
        curve(pd.bdate_range("2024-01-02", periods=5), [100, 102, 101, 104, 105]),
        curve(pd.bdate_range("2024-02-02", periods=5), [100, 98, 101, 99, 100]),
    )
    assert response.status_code == 400, response.json


def test_weekly_returns_use_weekly_annualization():
    weeks = pd.date_range("2024-01-05", periods=5, freq="W-FRI")
    response = optimize(curve(weeks, [100, 110, 110, 110, 110], "1wk"))
    assert response.status_code == 200, response.json
    assert response.json["data"]["expected_return"] == pytest.approx(0.10 / 4 * 52)


def test_mixed_period_returns_are_rejected():
    days = pd.bdate_range("2024-01-02", periods=25)
    weeks = pd.date_range("2024-01-05", periods=5, freq="W-FRI")
    response = optimize(
        curve(days, list(range(100, 125))),
        curve(weeks, [100, 110, 110, 110, 110], "1wk"),
    )
    assert response.status_code == 400, response.json


def test_pre_overlap_gain_does_not_enter_portfolio_mean():
    dates = pd.bdate_range("2024-01-02", periods=6)
    response = optimize(
        curve(dates, [100, 110, 110, 110, 110, 110]),
        curve(dates[2:], [100] * 4),
    )
    assert response.status_code == 200, response.json
    assert response.json["data"]["expected_return"] == pytest.approx(0)


def test_legacy_weekly_curve_without_request_interval():
    weeks = pd.date_range("2024-01-05", periods=5, freq="W-FRI")
    response = optimize(curve(weeks, [100, 110, 110, 110, 110], "1wk")["results"])
    assert response.status_code == 200, response.json
    assert response.json["data"]["expected_return"] == pytest.approx(0.10 / 4 * 52)


def test_weekly_and_monthly_labels_align_to_one_observation_per_period():
    for interval, frequency, periods_per_year in (
        ("1wk", "W-FRI", 52),
        ("1mo", "ME", 12),
    ):
        ends = pd.date_range("2024-02-02", periods=5, freq=frequency)
        shifted = ends - pd.Timedelta(days=1)
        response = optimize(
            curve(ends, [100, 110, 110, 110, 110], interval),
            curve(shifted, [100, 100, 100, 100, 100], interval),
        )
        assert response.status_code == 200, response.json
        assert response.json["data"]["expected_return"] == pytest.approx(
            0.5 * (0.10 / 4) * periods_per_year
        )


def test_two_shared_marks_cannot_estimate_covariance():
    dates = pd.bdate_range("2024-01-02", periods=6)
    response = optimize(
        curve(dates[:4], [100, 101, 103, 105]),
        curve(dates[2:], [100, 102, 104, 107]),
    )
    assert response.status_code == 400, response.json
    assert "at least two shared returns" in response.json["message"]
