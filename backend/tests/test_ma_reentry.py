"""MA crossover re-entry after a protective exit (opt-in).

Without the option, an MA crossover strategy closed by a stop-loss /
take-profit / trailing stop stays flat until the next golden cross, even when
the trend it entered on is still intact. With
``reentry_after_protective_exit=True`` the backtest engine re-opens the
position while the short MA is above the long MA, once more than
``reentry_wait_bars`` completed bars have passed since the exit bar.
AlphaLive mirrors the same rule (alphalive/strategy/signal_engine.py).
"""

import numpy as np
import pandas as pd
import pytest

from alphalab.backtest.engine import BacktestEngine
from alphalab.strategies.implementations.moving_average_crossover import (
    MovingAverageCrossover,
)

RISK = {"stop_loss_pct": 50.0, "take_profit_pct": 10.0, "max_position_size_pct": 100.0}


def _frame(close):
    close = np.asarray(close, dtype=float)
    dates = pd.bdate_range("2021-01-04", periods=len(close))
    df = pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1e6},
        index=dates,
    )
    df.attrs["ticker"] = "TEST"
    return df


def _run(close, **params):
    p = {
        "short_window": 5,
        "long_window": 20,
        "volume_confirmation": False,
        "cooldown_days": 0,
    }
    p.update(params)
    result = BacktestEngine().run_backtest(
        MovingAverageCrossover(p),
        _frame(close),
        risk_settings=RISK,
        drawdown_halt_enabled=False,
    )
    return result.trades


STEADY_RISE = np.r_[np.full(60, 100.0), np.linspace(100, 160, 80)]


def test_default_stays_flat_after_take_profit():
    trades = _run(STEADY_RISE)
    sides = [t["side"] for t in trades]
    assert sides == ["buy", "sell"]
    assert "Take-profit" in trades[1]["reason"] or "take" in trades[1]["reason"].lower()


def test_reentry_reopens_while_trend_intact():
    trades = _run(STEADY_RISE, reentry_after_protective_exit=True, reentry_wait_bars=1)
    buys = [t for t in trades if t["side"] == "buy"]
    assert len(buys) >= 2
    assert buys[1]["reason"].startswith("Re-entry after protective exit")

    # Timing: the take-profit fills inside bar t (intrabar, like AlphaLive);
    # re-entry is decided at the close of the first bar i with i - t > wait
    # (t+2), filled at the open of t+3 -> exactly 3 bars after the exit fill.
    idx = pd.bdate_range("2021-01-04", periods=len(STEADY_RISE))
    pos = {str(d)[:10]: k for k, d in enumerate(idx)}
    first_sell = next(t for t in trades if t["side"] == "sell")
    assert (
        pos[str(buys[1]["timestamp"])[:10]] - pos[str(first_sell["timestamp"])[:10]]
        == 3
    )


@pytest.mark.parametrize("wait", [0, 1, 3])
def test_wait_bars_shift_reentry(wait):
    trades = _run(
        STEADY_RISE, reentry_after_protective_exit=True, reentry_wait_bars=wait
    )
    idx = pd.bdate_range("2021-01-04", periods=len(STEADY_RISE))
    pos = {str(d)[:10]: k for k, d in enumerate(idx)}
    sell = next(t for t in trades if t["side"] == "sell")
    rebuy = next(
        t for t in trades if t["side"] == "buy" and t["reason"].startswith("Re-entry")
    )
    assert (
        pos[str(rebuy["timestamp"])[:10]] - pos[str(sell["timestamp"])[:10]] == wait + 2
    )


def test_no_reentry_after_trend_reverses():
    # Rise (golden cross, take-profit fires), then a hard fall that pulls the
    # short MA under the long MA before the wait elapses: no re-entry.
    close = np.r_[
        np.full(60, 100.0), np.linspace(100, 112, 12), np.linspace(110, 70, 30)
    ]
    trades = _run(close, reentry_after_protective_exit=True, reentry_wait_bars=10)
    assert not any(t["reason"].startswith("Re-entry") for t in trades)


def test_option_off_matches_previous_signals_exactly():
    data = _frame(STEADY_RISE)
    base = {"short_window": 5, "long_window": 20, "volume_confirmation": False}
    a = MovingAverageCrossover(dict(base)).generate_signals(data)
    b = MovingAverageCrossover(
        dict(base, reentry_after_protective_exit=False)
    ).generate_signals(data)
    pd.testing.assert_frame_equal(a, b)
    assert "reentry_ok" not in a.columns


@pytest.mark.parametrize(
    "bad",
    [
        {"reentry_after_protective_exit": "yes"},
        {"reentry_wait_bars": -1},
        {"reentry_wait_bars": 101},
        {"reentry_wait_bars": 1.5},
        {"reentry_wait_bars": True},
    ],
)
def test_invalid_params_rejected(bad):
    with pytest.raises(ValueError):
        MovingAverageCrossover({"short_window": 5, "long_window": 20, **bad})


@pytest.mark.parametrize("cooldown", [0, 5, 20])
def test_cooldown_gates_reentry_like_alphalive(cooldown):
    """AlphaLive's risk cooldown (execution.cooldown_bars = cooldown_days)
    needs >= cooldown completed bars since the last strategy order's decision
    bar before ANY entry, re-entries included. The backtest mirrors it."""
    trades = _run(
        STEADY_RISE,
        reentry_after_protective_exit=True,
        reentry_wait_bars=1,
        cooldown_days=cooldown,
    )
    idx = pd.bdate_range("2021-01-04", periods=len(STEADY_RISE))
    pos = {str(d)[:10]: k for k, d in enumerate(idx)}
    entry_decision = pos[str(trades[0]["timestamp"])[:10]] - 1
    # the protective exit fills inside its own bar (no next-open delay)
    exit_decision = pos[
        str(next(t for t in trades if t["side"] == "sell")["timestamp"])[:10]
    ]
    rebuy = next(t for t in trades if t["reason"].startswith("Re-entry"))
    rebuy_decision = pos[str(rebuy["timestamp"])[:10]] - 1
    assert rebuy_decision == max(exit_decision + 2, entry_decision + cooldown)


def test_low_volume_death_cross_still_exits():
    """Volume/separation filters screen entries only: a death cross on a
    quiet day must still emit SELL (it used to be dropped, trapping the
    position until a later cross)."""
    close = np.r_[
        np.full(40, 100.0), np.linspace(100, 120, 20), np.linspace(119, 95, 20)
    ]
    vol = np.full(len(close), 1e6)
    data = _frame(close)
    data["Volume"] = vol
    s = MovingAverageCrossover(
        {
            "short_window": 5,
            "long_window": 20,
            "volume_confirmation": True,
            "cooldown_days": 0,
        }
    )
    sig = s.generate_signals(data)["signal"]
    death = int(np.flatnonzero(sig.to_numpy() == -1)[0])
    data.iloc[death, data.columns.get_loc("Volume")] = 1e3  # quiet day
    sig2 = s.generate_signals(data)["signal"]
    assert sig2.iloc[death] == -1
