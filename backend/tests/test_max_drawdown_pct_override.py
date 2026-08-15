"""Tests for the max_drawdown_pct override on POST /api/strategies/backtest
(Prompt 2.5 remediation, 2026-08-15 - see FINAL_ENGINEERING_AUDIT.md /
END_TO_END_VALIDATION.md issue 3).

Before this fix, BacktestRequest had no max_drawdown_pct field at all - the
single-backtest endpoint could not receive an override, silently diverging
from CLAUDE.md's documented requirement to pass max_drawdown_pct=40 for
weekly strategies (the engine's 10% default halts them too early).
"""

from unittest.mock import patch

import pandas as pd
import pytest

from alphalab.api.validators import BacktestRequest
from alphalab.backtest.engine import BacktestEngine, BacktestResults
from alphalab.data.processor import FeatureEngineer
from alphalab.strategies.implementations.moving_average_crossover import (
    MovingAverageCrossover,
)


def _stub_results() -> BacktestResults:
    """A trivially valid BacktestResults, for tests that only need to prove
    request->engine argument threading, not exercise the real simulation
    pipeline (patch.object(..., wraps=..., autospec=True) on this Flask
    view was observed to corrupt something downstream of a real call under
    pytest specifically - not reproducible standalone - so these tests
    avoid `wraps` and just record call args against a canned return)."""
    return BacktestResults(
        strategy_name="Stub",
        initial_capital=100000.0,
        final_value=100000.0,
        equity_curve=[
            {"date": pd.Timestamp("2020-01-01"), "value": 100000.0},
            {"date": pd.Timestamp("2020-01-02"), "value": 100000.0},
        ],
        trades=[],
        benchmark={
            "total_return_pct": 0.0,
            "final_value": 100000.0,
            "max_drawdown_pct": 0.0,
            "equity_curve": [
                {"date": pd.Timestamp("2020-01-01"), "value": 100000.0},
                {"date": pd.Timestamp("2020-01-02"), "value": 100000.0},
            ],
        },
    )


def test_max_drawdown_pct_omitted_defaults_to_none():
    """Omitting the field must preserve prior behaviour exactly (the engine
    applies its own 10% default when max_drawdown_pct is None)."""
    req = BacktestRequest(
        ticker="AAPL",
        strategy="ma_crossover",
        start_date="2020-01-01",
        end_date="2020-06-01",
    )
    assert req.max_drawdown_pct is None


@pytest.mark.parametrize("value", [40.0, 15.5])
def test_max_drawdown_pct_accepts_valid_values(value):
    req = BacktestRequest(
        ticker="AAPL",
        strategy="greenblatt_weekly",
        start_date="2020-01-01",
        end_date="2020-06-01",
        max_drawdown_pct=value,
    )
    assert req.max_drawdown_pct == value


@pytest.mark.parametrize("value", [0.0, -5.0, 150.0])
def test_max_drawdown_pct_rejects_nonsensical_values(value):
    with pytest.raises(ValueError):
        BacktestRequest(
            ticker="AAPL",
            strategy="ma_crossover",
            start_date="2020-01-01",
            end_date="2020-06-01",
            max_drawdown_pct=value,
        )


def _synthetic_featured_data():
    prices = []
    for cycle in range(4):
        for i in range(15):
            prices.append(100 + i * 3)
        for i in range(15):
            prices.append(prices[-1] - (6 if cycle == 1 else 3))
    raw = pd.DataFrame(
        {
            "Open": prices,
            "High": [p + 1 for p in prices],
            "Low": [p - 1 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=pd.date_range("2020-01-01", periods=len(prices), freq="D"),
    )
    return FeatureEngineer().process(raw)


class _StubReport:
    warnings: list = []
    is_acceptable = True


def _mock_fetch_and_prepare(*_args, **_kwargs):
    return _synthetic_featured_data(), _StubReport(), None


def test_two_different_max_drawdown_pct_values_reach_the_engine():
    """Directly verify the endpoint's engine.run_backtest() call is invoked
    with the request's own max_drawdown_pct value, for two distinct
    values - not just schema acceptance. _fetch_and_prepare is mocked to
    return a small, controlled, valid featured DataFrame directly, so this
    test exercises exactly the request->engine threading this pass changed
    without depending on live/cached market data or the rest of the fetch
    pipeline (already covered by its own tests elsewhere)."""
    from alphalab.api.routes import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with patch(
        "alphalab.api.blueprints.backtest._fetch_and_prepare",
        side_effect=_mock_fetch_and_prepare,
    ), patch.object(
        BacktestEngine, "run_backtest", return_value=_stub_results()
    ) as spy:
        for value in (12.0, 55.0):
            resp = client.post(
                "/api/strategies/backtest",
                json={
                    "ticker": "AAPL",
                    "strategy": "ma_crossover",
                    "start_date": "2020-01-01",
                    "end_date": "2024-12-31",
                    "initial_capital": 100000,
                    "params": {
                        "short_window": 5,
                        "long_window": 10,
                        "volume_confirmation": False,
                        "cooldown_days": 0,
                    },
                    "max_drawdown_pct": value,
                },
            )
            assert resp.status_code == 200, resp.get_json()
            # Last call's kwargs must carry the exact value this request sent.
            _, kwargs = spy.call_args
            assert kwargs["max_drawdown_pct"] == value


def test_max_drawdown_pct_produces_observable_behavioral_difference():
    """A tight threshold must halt new entries earlier than a loose one on
    a dataset engineered to breach 1% drawdown but not 99% - proving the
    value genuinely reaches Portfolio's halt check, not just the engine's
    method signature."""
    featured = _synthetic_featured_data()
    strat = MovingAverageCrossover(
        {
            "short_window": 5,
            "long_window": 10,
            "volume_confirmation": False,
            "cooldown_days": 0,
        }
    )
    engine = BacktestEngine()

    tight = engine.run_backtest(
        strategy=strat, data=featured, initial_capital=100000, max_drawdown_pct=1.0
    )
    loose = engine.run_backtest(
        strategy=strat, data=featured, initial_capital=100000, max_drawdown_pct=99.0
    )

    assert len(tight.trades) < len(loose.trades), (
        f"Expected the 1% threshold to halt and block trades the 99% "
        f"threshold allows: tight={len(tight.trades)}, loose={len(loose.trades)}"
    )


def test_weekly_backtest_can_receive_the_documented_override():
    """greenblatt_weekly + max_drawdown_pct=40 (CLAUDE.md's documented
    required override) must be accepted and threaded through via the real
    HTTP endpoint without error."""
    from alphalab.api.routes import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with patch(
        "alphalab.api.blueprints.backtest._fetch_and_prepare",
        side_effect=_mock_fetch_and_prepare,
    ), patch.object(
        BacktestEngine, "run_backtest", return_value=_stub_results()
    ) as spy:
        resp = client.post(
            "/api/strategies/backtest",
            json={
                "ticker": "AAPL",
                "strategy": "greenblatt_weekly",
                "start_date": "2015-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
                "params": {},
                "max_drawdown_pct": 40.0,
            },
        )
        assert resp.status_code == 200, resp.get_json()
        _, kwargs = spy.call_args
        assert kwargs["max_drawdown_pct"] == 40.0
