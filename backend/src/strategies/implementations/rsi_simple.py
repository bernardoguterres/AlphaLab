"""Simple RSI Mean Reversion - Optimized for Daily Trading (1-3 trades/day).

NO BB confirmation, NO ADX filter, NO complex logic.
Just RSI with relaxed thresholds for frequent signals.

EXACT PARITY with AlphaLive implementation.
"""

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.rsi_simple")


class RSISimple(BaseStrategy):
    """Ultra-simple RSI mean reversion for frequent trading.

    Entry: RSI < oversold (default 40)
    Exit: RSI > overbought (default 60)

    No confirmation filters, no state machine, no extra logic.
    Designed to match AlphaLive signal_engine.py EXACTLY for signal parity.

    Target: 5-15 signals/month on daily bars, 1-3/day on 15Min bars.
    """

    name = "RSI_Simple"

    def validate_params(self):
        p = self.params
        p.setdefault("period", 14)
        p.setdefault("oversold", 40)  # Relaxed from 30
        p.setdefault("overbought", 60)  # Relaxed from 70

        if not (0 < p["oversold"] < p["overbought"] < 100):
            raise ValueError("Need 0 < oversold < overbought < 100")

    def required_columns(self) -> list[str]:
        return ["Close", "RSI"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals matching AlphaLive logic EXACTLY.

        AlphaLive signal_engine.py _rsi_mean_reversion_signal():
        - BUY when RSI < oversold
        - SELL when RSI > overbought
        - HOLD otherwise

        No state machine, no extra filters.
        """
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        rsi = data["RSI"]

        for i in range(len(data)):
            if pd.isna(rsi.iloc[i]):
                continue

            rsi_curr = rsi.iloc[i]

            # BUY: Oversold
            if rsi_curr < p["oversold"]:
                distance = p["oversold"] - rsi_curr
                confidence = min(1.0, distance / p["oversold"])

                signals.iloc[i, signals.columns.get_loc("signal")] = 1
                signals.iloc[i, signals.columns.get_loc("confidence")] = confidence
                signals.iloc[i, signals.columns.get_loc("reason")] = (
                    f"RSI oversold: {rsi_curr:.1f} < {p['oversold']}"
                )

            # SELL: Overbought
            elif rsi_curr > p["overbought"]:
                distance = rsi_curr - p["overbought"]
                confidence = min(1.0, distance / (100 - p["overbought"]))

                signals.iloc[i, signals.columns.get_loc("signal")] = -1
                signals.iloc[i, signals.columns.get_loc("confidence")] = confidence
                signals.iloc[i, signals.columns.get_loc("reason")] = (
                    f"RSI overbought: {rsi_curr:.1f} > {p['overbought']}"
                )

        total_signals = (signals["signal"] != 0).sum()
        logger.info(
            "%s generated %d signals on %d bars (%.1f%% signal rate)",
            self.name, total_signals, len(data), 100 * total_signals / len(data) if len(data) > 0 else 0
        )

        return signals
