"""Momentum Breakout strategy - buy on high breakout with volume surge."""

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.momentum")


class MomentumBreakout(BaseStrategy):
    """Enter when price breaks above recent highs with confirming volume and RSI.

    State-aware: after a buy, tracks position and exits on breakdown,
    stop-loss, or trailing stop. Prevents re-entering during cooldown.
    """

    name = "Momentum_Breakout"

    def validate_params(self):
        p = self.params
        p.setdefault("lookback", 20)
        p.setdefault("volume_surge_pct", 150)
        p.setdefault("volume_avg_period", 20)
        p.setdefault("rsi_min", 50)
        p.setdefault("stop_loss_atr_mult", 2.0)
        p.setdefault("trailing_stop_atr_mult", 3.0)
        p.setdefault("cooldown_days", 3)

        if p["lookback"] < 5:
            raise ValueError("lookback must be >= 5")
        if p["volume_surge_pct"] < 100:
            raise ValueError("volume_surge_pct must be >= 100")

    def required_columns(self) -> list[str]:
        return ["Close", "High", "Low", "Volume", "ATR", "RSI"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""
        signals["stop_loss"] = np.nan

        close = data["Close"]
        high = data["High"]
        low = data["Low"]
        volume = data["Volume"]
        atr = data["ATR"]
        rsi = data["RSI"]

        lookback = p["lookback"]
        high_n = high.rolling(lookback, min_periods=lookback).max()
        low_n = low.rolling(lookback, min_periods=lookback).min()
        vol_avg = volume.rolling(p["volume_avg_period"]).mean()

        # Extract to numpy arrays once, up front - avoids repeated .iloc[i]/pd.isna
        # Series overhead inside the per-bar loop below.
        close_arr = close.to_numpy()
        volume_arr = volume.to_numpy()
        atr_arr = atr.to_numpy()
        rsi_arr = rsi.to_numpy()
        high_n_arr = high_n.to_numpy()
        low_n_arr = low_n.to_numpy()
        vol_avg_arr = vol_avg.to_numpy()
        atr_valid = ~np.isnan(atr_arr)
        rsi_valid = ~np.isnan(rsi_arr)
        high_n_valid = ~np.isnan(high_n_arr)
        low_n_valid = ~np.isnan(low_n_arr)
        vol_avg_valid = ~np.isnan(vol_avg_arr)

        # State machine
        in_position = False
        entry_price = 0.0
        stop_price = 0.0
        trailing_stop = 0.0
        peak_price = 0.0
        last_signal_bar = -p["cooldown_days"] - 1

        for i in range(lookback, len(data)):
            current_close = close_arr[i]

            if in_position:
                # Update trailing stop
                if current_close > peak_price:
                    peak_price = current_close
                    atr_val = atr_arr[i] if atr_valid[i] else peak_price * 0.02
                    trailing_stop = peak_price - p["trailing_stop_atr_mult"] * atr_val

                exit_reason = None

                # 1. Hard stop-loss
                if current_close <= stop_price:
                    loss_pct = (current_close / entry_price - 1) * 100
                    exit_reason = f"Stop-loss hit ({loss_pct:.1f}%)"

                # 2. Trailing stop
                elif current_close <= trailing_stop:
                    pnl = (current_close / entry_price - 1) * 100
                    exit_reason = f"Trailing stop ({pnl:+.1f}%)"

                # 3. Breakdown below N-day low
                elif low_n_valid[i - 1] and current_close < low_n_arr[i - 1]:
                    pnl = (current_close / entry_price - 1) * 100
                    exit_reason = f"Breakdown below {lookback}-day low ({pnl:+.1f}%)"

                if exit_reason is not None:
                    signals.iloc[i, signals.columns.get_loc("signal")] = -1
                    signals.iloc[i, signals.columns.get_loc("confidence")] = 0.5
                    signals.iloc[i, signals.columns.get_loc("reason")] = exit_reason
                    in_position = False
                    last_signal_bar = i

            else:
                # Check entry conditions (with cooldown)
                if i - last_signal_bar <= p["cooldown_days"]:
                    continue

                # Breakout above N-day high
                if not high_n_valid[i - 1] or current_close <= high_n_arr[i - 1]:
                    continue

                # Volume surge confirmation
                avg_vol = vol_avg_arr[i]
                if not vol_avg_valid[i] or avg_vol <= 0:
                    continue
                volume_i = volume_arr[i]
                if volume_i <= (avg_vol * p["volume_surge_pct"] / 100):
                    continue

                # RSI momentum confirmation
                rsi_val = rsi_arr[i]
                if not rsi_valid[i] or rsi_val <= p["rsi_min"]:
                    continue

                # Entry signal
                atr_val = atr_arr[i] if atr_valid[i] else current_close * 0.02
                entry_price = current_close
                stop_price = entry_price - p["stop_loss_atr_mult"] * atr_val
                peak_price = entry_price
                trailing_stop = entry_price - p["trailing_stop_atr_mult"] * atr_val

                # Confidence based on volume surge magnitude
                surge_ratio = volume_i / avg_vol if avg_vol > 0 else 1
                conf = min(1.0, (surge_ratio - 1) / 4)

                signals.iloc[i, signals.columns.get_loc("signal")] = 1
                signals.iloc[i, signals.columns.get_loc("confidence")] = conf
                signals.iloc[i, signals.columns.get_loc("stop_loss")] = stop_price
                signals.iloc[i, signals.columns.get_loc("reason")] = (
                    f"Breakout above {lookback}-day high with volume surge"
                )
                in_position = True
                last_signal_bar = i

        logger.info(
            "%s generated %d signals on %d bars",
            self.name,
            (signals["signal"] != 0).sum(),
            len(data),
        )
        return signals
