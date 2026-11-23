"""A backtest covering less of the requested window than asked must say so
(E2E finding, Nov 2026: a corrupted cache entry ending 14 months early was
served as a normal result with no warning)."""

import pandas as pd

from alphalab.api.helpers import _coverage_warnings


def _idx(start, end, freq="B"):
    return pd.date_range(start, end, freq=freq)


def test_full_coverage_has_no_warning():
    assert (
        _coverage_warnings(_idx("2020-01-02", "2024-12-31"), "2020-01-01", "2024-12-31")
        == []
    )


def test_data_ending_early_is_reported():
    w = _coverage_warnings(_idx("2020-01-01", "2023-10-31"), "2020-01-01", "2024-12-31")
    assert len(w) == 1 and "Data ends 2023-10-31" in w[0] and "2024-12-31" in w[0]


def test_data_starting_late_is_reported():
    w = _coverage_warnings(_idx("2021-06-01", "2024-12-31"), "2020-01-01", "2024-12-31")
    assert len(w) == 1 and "Data starts 2021-06-01" in w[0]


def test_future_end_and_weekly_slack_are_not_gaps():
    future = (pd.Timestamp.today() + pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    today = pd.Timestamp.today().normalize()
    assert (
        _coverage_warnings(
            _idx("2020-01-01", today - pd.Timedelta(days=3)), "2020-01-01", future
        )
        == []
    )
    weekly = pd.date_range("2020-01-06", "2024-12-23", freq="W-MON")
    assert _coverage_warnings(weekly, "2020-01-01", "2024-12-31", "1wk") == []


def test_backtest_response_carries_the_warning(monkeypatch):
    """Through the real endpoint with a stub fetcher returning short data."""
    import numpy as np

    from alphalab.api.routes import create_app

    idx = _idx("2020-01-01", "2023-10-31")
    close = 100 + np.cumsum(np.random.default_rng(1).normal(0, 1, len(idx)))
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1e6,
        },
        index=idx,
    )
    app = create_app()
    monkeypatch.setattr(
        app.extensions["fetcher"],
        "fetch",
        lambda *a, **k: {"data": df, "from_cache": True},
    )
    resp = (
        app.test_client()
        .post(
            "/api/strategies/backtest",
            json={
                "ticker": "AAPL",
                "strategy": "ma_crossover",
                "params": {"short_window": 20, "long_window": 50},
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
            },
        )
        .get_json()
    )
    assert resp["status"] == "ok"
    assert any(
        "Data ends 2023-10-31" in w for w in resp["data"]["data_quality_warnings"]
    )
