"""Moving Average Crossover strategy with volume confirmation and whipsaw filter."""

import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.ma_cross")


class MovingAverageCrossover(BaseStrategy):
    """Generate signals when a short-period MA crosses above/below a long-period MA.

    Default is the classic Golden Cross / Death Cross (50/200).
    Includes volume confirmation, minimum MA separation, and cooldown.
    """

    name = "MA_Crossover"

    def validate_params(self):
        p = self.params
        p.setdefault("short_window", 50)
        p.setdefault("long_window", 200)
        p.setdefault("volume_confirmation", True)
        p.setdefault("volume_avg_period", 20)
        p.setdefault("min_separation_pct", 0.0)
        p.setdefault("cooldown_days", 5)
        # Re-entry after a protective exit (stop-loss / take-profit /
        # trailing stop). Off by default: entries happen only on a cross.
        # When on, a position closed by a protective exit is re-opened while
        # the short MA is still above the long MA, once more than
        # reentry_wait_bars completed bars have passed since the exit bar.
        # The backtest engine applies it (it alone knows when a protective
        # exit happened); AlphaLive mirrors the same rule.
        p.setdefault("reentry_after_protective_exit", False)
        p.setdefault("reentry_wait_bars", 1)

        if p["short_window"] >= p["long_window"]:
            raise ValueError("short_window must be < long_window")
        if p["short_window"] < 2:
            raise ValueError("short_window must be >= 2")
        if not isinstance(p["reentry_after_protective_exit"], bool):
            raise ValueError("reentry_after_protective_exit must be a bool")
        if (
            isinstance(p["reentry_wait_bars"], bool)
            or not isinstance(p["reentry_wait_bars"], int)
            or not 0 <= p["reentry_wait_bars"] <= 100
        ):
            raise ValueError("reentry_wait_bars must be an int in [0, 100]")

        self._reject_unknown_params(
            {
                "short_window",
                "long_window",
                "volume_confirmation",
                "volume_avg_period",
                "min_separation_pct",
                "cooldown_days",
                "reentry_after_protective_exit",
                "reentry_wait_bars",
            }
        )

    def required_columns(self) -> list[str]:
        cols = ["Close"]
        if self.params.get("volume_confirmation"):
            cols.append("Volume")
        return cols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        short_w = p["short_window"]
        long_w = p["long_window"]
        close = data["Close"]

        short_ma = close.rolling(short_w, min_periods=short_w).mean()
        long_ma = close.rolling(long_w, min_periods=long_w).mean()

        signals = self._init_signals_frame(data)

        prev_short = short_ma.shift(1)
        prev_long = long_ma.shift(1)

        # Raw crossover detection
        cross_up = (prev_short <= prev_long) & (short_ma > long_ma)
        cross_down = (prev_short >= prev_long) & (short_ma < long_ma)

        # Min separation filter: check that MAs were at least X% apart
        # *before* the cross (prevents whipsaws from tiny oscillations)
        prev_sep = ((prev_short - prev_long).abs() / prev_long * 100).fillna(0)
        sep_ok = prev_sep >= p["min_separation_pct"]

        # Volume confirmation
        vol_ok = pd.Series(True, index=data.index)
        if p["volume_confirmation"] and "Volume" in data.columns:
            vol_avg = data["Volume"].rolling(p["volume_avg_period"]).mean()
            vol_ok = data["Volume"] > vol_avg

        # Separation and volume filters screen ENTRIES only. Applying them to
        # the death cross too dropped exits on quiet days (AAPL was held from
        # 2019 through the 2022 bear market) - an entry filter must never
        # trap a position. Mirrored in AlphaLive's signal_engine.py.
        buy_mask = cross_up & sep_ok & vol_ok
        sell_mask = cross_down

        signals.loc[buy_mask, "signal"] = 1
        signals.loc[sell_mask, "signal"] = -1

        # Confidence based on separation
        signals.loc[buy_mask, "confidence"] = (prev_sep[buy_mask] / 5).clip(0, 1)
        signals.loc[sell_mask, "confidence"] = (prev_sep[sell_mask] / 5).clip(0, 1)

        # Reasons
        signals.loc[buy_mask, "reason"] = f"SMA{short_w} crossed above SMA{long_w}"
        signals.loc[sell_mask, "reason"] = f"SMA{short_w} crossed below SMA{long_w}"

        # Cooldown enforcement
        signals = self._apply_cooldown(signals, p["cooldown_days"])

        # Re-entry permission per bar (read by BacktestEngine._simulate only
        # after a protective exit). Absent column = feature off.
        if p["reentry_after_protective_exit"]:
            signals["reentry_ok"] = (short_ma > long_ma).fillna(False)
            signals.attrs["reentry_wait_bars"] = int(p["reentry_wait_bars"])
            # Exported to AlphaLive as execution.cooldown_bars, whose risk
            # cooldown also gates re-entries - mirror it in the backtest.
            signals.attrs["reentry_cooldown_bars"] = int(p["cooldown_days"])

        logger.info(
            "%s generated %d signals on %d bars",
            self.name,
            (signals["signal"] != 0).sum(),
            len(data),
        )
        return signals
