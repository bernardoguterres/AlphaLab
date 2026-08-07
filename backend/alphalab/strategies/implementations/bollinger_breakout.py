"""Bollinger Band Breakout strategy with confirmation and volume filter."""

import pandas as pd
import numpy as np

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.bb_breakout")


class BollingerBreakout(BaseStrategy):
    """Generate signals on consecutive closes outside Bollinger Bands.

    BUY: Price closes above upper BB for confirmation_bars consecutive bars
    SELL: Price closes below lower BB for confirmation_bars consecutive bars
    EXIT: Price returns to middle band (SMA)

    Includes optional volume filter and uses next-bar execution.
    """

    name = "Bollinger_Breakout"

    def validate_params(self):
        p = self.params
        p.setdefault("bb_period", 20)
        p.setdefault("bb_std_dev", 2.0)
        p.setdefault("confirmation_bars", 2)
        p.setdefault("volume_filter", True)
        p.setdefault("volume_threshold", 1.5)
        p.setdefault("cooldown_days", 3)

        if not 5 <= p["bb_period"] <= 100:
            raise ValueError("bb_period must be between 5 and 100")
        if not 0.5 <= p["bb_std_dev"] <= 4.0:
            raise ValueError("bb_std_dev must be between 0.5 and 4.0")
        if not 1 <= p["confirmation_bars"] <= 5:
            raise ValueError("confirmation_bars must be between 1 and 5")
        if p["volume_threshold"] < 1.0:
            raise ValueError("volume_threshold must be >= 1.0")
        if p["cooldown_days"] < 0:
            raise ValueError("cooldown_days must be >= 0")

    def required_columns(self) -> list[str]:
        cols = ["Close"]
        if self.params.get("volume_filter"):
            cols.append("Volume")
        return cols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        period = p["bb_period"]
        std_dev = p["bb_std_dev"]
        confirmation = p["confirmation_bars"]
        close = data["Close"]

        # Calculate Bollinger Bands
        sma = close.rolling(period, min_periods=period).mean()
        rolling_std = close.rolling(period, min_periods=period).std()
        upper_band = sma + (rolling_std * std_dev)
        lower_band = sma - (rolling_std * std_dev)

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        # Check for consecutive closes above/below bands
        above_upper = close > upper_band
        below_lower = close < lower_band
        at_middle = (close >= sma * 0.99) & (close <= sma * 1.01)  # Within 1% of SMA

        # Vectorized consecutive-bar check (replaces O(n·m) slice loop)
        consecutive_above = above_upper.rolling(confirmation).sum() >= confirmation
        consecutive_below = below_lower.rolling(confirmation).sum() >= confirmation

        # Volume filter (optional)
        vol_ok = pd.Series(True, index=data.index)
        if p["volume_filter"] and "Volume" in data.columns:
            vol_avg = data["Volume"].rolling(20).mean()
            vol_ok = data["Volume"] >= (vol_avg * p["volume_threshold"])

        # State machine for position tracking (scalar avoids SettingWithCopyWarning)
        current_position = 0
        for i in range(len(data)):
            # Entry signals (only if no position)
            if current_position == 0:
                # BUY signal: consecutive closes above upper band + volume
                if consecutive_above.iloc[i] and vol_ok.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc("signal")] = 1
                    signals.iloc[i, signals.columns.get_loc("reason")] = (
                        f"{confirmation} closes above upper BB"
                    )
                    distance_pct = (
                        (close.iloc[i] - upper_band.iloc[i]) / upper_band.iloc[i]
                    ) * 100
                    signals.iloc[i, signals.columns.get_loc("confidence")] = min(
                        distance_pct / 2, 1.0
                    )
                    current_position = 1

                # SELL signal: consecutive closes below lower band + volume
                elif consecutive_below.iloc[i] and vol_ok.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc("signal")] = -1
                    signals.iloc[i, signals.columns.get_loc("reason")] = (
                        f"{confirmation} closes below lower BB"
                    )
                    distance_pct = (
                        (lower_band.iloc[i] - close.iloc[i]) / lower_band.iloc[i]
                    ) * 100
                    signals.iloc[i, signals.columns.get_loc("confidence")] = min(
                        distance_pct / 2, 1.0
                    )
                    current_position = -1

            # Exit signals (if in position)
            elif current_position != 0:
                if at_middle.iloc[i]:
                    signals.iloc[i, signals.columns.get_loc("signal")] = (
                        -current_position
                    )
                    signals.iloc[i, signals.columns.get_loc("reason")] = (
                        "Price returned to middle band"
                    )
                    signals.iloc[i, signals.columns.get_loc("confidence")] = 0.5
                    current_position = 0

        # Apply cooldown
        signals = self._apply_cooldown(signals, p["cooldown_days"])

        logger.info(
            "%s generated %d signals on %d bars",
            self.name,
            (signals["signal"] != 0).sum(),
            len(data),
        )
        return signals
