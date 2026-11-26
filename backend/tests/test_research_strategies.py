"""Hand-computable signal and execution cases for the research strategies."""

import pandas as pd
import pytest

from alphalab.backtest.engine import BacktestEngine
from alphalab.strategies.research import DonchianBreakout, TrendPullback


def price_frame(closes):
    close = pd.Series(
        closes, index=pd.bdate_range("2024-01-02", periods=len(closes)), dtype=float
    )
    frame = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 100_000,
        }
    )
    frame.attrs["ticker"] = "TEST"
    return frame


@pytest.mark.parametrize(
    ("strategy", "closes", "entry", "exit"),
    [
        (DonchianBreakout(), [100] * 55 + [102, 104, 98, 98], 55, 57),
        (TrendPullback(), [90] * 94 + [107] * 6 + [101, 101, 108, 108], 100, 102),
    ],
)
def test_rules_are_causal_and_fill_at_next_open(strategy, closes, entry, exit):
    data = price_frame(closes)
    # Set the next open apart from both the signal close and the fill bar close.
    data.loc[data.index[entry + 1], "Open"] = closes[entry + 1] + 0.5
    signal = strategy.generate_signals(data)["signal"]
    assert signal[signal != 0].to_dict() == {
        data.index[entry]: 1,
        data.index[exit]: -1,
    }
    for cutoff in (entry, entry + 1, exit + 1):
        pd.testing.assert_series_equal(
            strategy.generate_signals(data.iloc[:cutoff])["signal"],
            signal.iloc[:cutoff],
        )

    engine = BacktestEngine()
    engine.slippage = 0.0
    result = engine.run_backtest(
        strategy, data, initial_capital=10_000, drawdown_halt_enabled=False
    )
    fills = [order for order in result.trades if order["status"] == "filled"]
    assert [(order["side"], order["filled_timestamp"]) for order in fills] == [
        ("buy", str(data.index[entry + 1])),
        ("sell", str(data.index[exit + 1])),
    ]
    assert fills[0]["filled_price"] == data.iloc[entry + 1]["Open"]
    assert result.to_dict()["total_trades"] == 1
