"""Bollinger Bands + RSI Combination Strategy.

Mean reversion strategy that buys when price touches lower BB AND RSI confirms oversold.
Exits when price returns to middle BB or RSI becomes overbought.

Simple, proven strategy that works in both trending and ranging markets.
Generates more signals than pure RSI because it catches bounces off support.

Target: 10-20 trades/month on daily bars, 2-5/day on 15Min bars.
"""

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.bollinger_rsi")


class BollingerRSICombo(BaseStrategy):
    """Buy dips at lower BB with RSI confirmation.

    Entry Conditions (ALL must be true):
    1. Price <= Lower Bollinger Band
    2. RSI < oversold threshold (default 45)

    Exit Conditions (ANY triggers exit):
    1. Price >= Middle Bollinger Band (SMA)
    2. RSI > overbought threshold (default 55)

    Why this works:
    - Lower BB provides dynamic support level
    - RSI confirms we're not catching a falling knife
    - Targets mean reversion to SMA (proven statistical edge)
    - Works in uptrends (buy dips) and ranges (oscillation)
    """

    name = "Bollinger_RSI_Combo"

    def validate_params(self):
        p = self.params
        p.setdefault("bb_period", 20)
        p.setdefault("bb_std", 2.0)
        p.setdefault("rsi_period", 14)
        p.setdefault("rsi_oversold", 45)  # More relaxed than pure RSI
        p.setdefault("rsi_overbought", 55)  # Tighter than pure RSI
        p.setdefault("exit_at_middle", True)  # Exit when price reaches BB middle

        if not (0 < p["rsi_oversold"] < p["rsi_overbought"] < 100):
            raise ValueError("Need 0 < rsi_oversold < rsi_overbought < 100")

    def required_columns(self) -> list[str]:
        return ["Close", "BB_Lower", "BB_Middle", "BB_Upper", "RSI"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate entry/exit signals.

        State machine: Tracks whether we're in a position.
        - When out: Look for BUY signals (BB lower touch + RSI oversold)
        - When in: Look for SELL signals (BB middle reach OR RSI overbought)
        """
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        close = data["Close"]
        bb_lower = data["BB_Lower"]
        bb_middle = data["BB_Middle"]
        bb_upper = data["BB_Upper"]
        rsi = data["RSI"]

        # State machine
        in_position = False
        entry_price = 0.0

        for i in range(len(data)):
            # Skip if data is NaN
            if any(pd.isna([close.iloc[i], bb_lower.iloc[i], bb_middle.iloc[i], rsi.iloc[i]])):
                continue

            close_curr = close.iloc[i]
            rsi_curr = rsi.iloc[i]

            if in_position:
                # Look for exit conditions
                exit_reason = None

                # Exit 1: Price reached middle BB (take profit at mean)
                if p["exit_at_middle"] and close_curr >= bb_middle.iloc[i]:
                    pnl_pct = ((close_curr - entry_price) / entry_price) * 100
                    exit_reason = f"BB middle reached (+{pnl_pct:.1f}%)"

                # Exit 2: RSI overbought
                elif rsi_curr > p["rsi_overbought"]:
                    pnl_pct = ((close_curr - entry_price) / entry_price) * 100
                    exit_reason = f"RSI overbought {rsi_curr:.1f} ({pnl_pct:+.1f}%)"

                if exit_reason:
                    signals.iloc[i, signals.columns.get_loc("signal")] = -1
                    signals.iloc[i, signals.columns.get_loc("reason")] = exit_reason
                    # Higher confidence if RSI is very overbought
                    conf = min(1.0, (rsi_curr - p["rsi_overbought"]) / (100 - p["rsi_overbought"]) + 0.5)
                    signals.iloc[i, signals.columns.get_loc("confidence")] = conf
                    in_position = False

            else:
                # Look for entry conditions
                bb_touch = close_curr <= bb_lower.iloc[i]
                rsi_oversold = rsi_curr < p["rsi_oversold"]

                if bb_touch and rsi_oversold:
                    # Calculate confidence based on how far below BB and RSI levels
                    bb_penetration = (bb_lower.iloc[i] - close_curr) / bb_lower.iloc[i] * 100
                    rsi_distance = (p["rsi_oversold"] - rsi_curr) / p["rsi_oversold"]
                    confidence = min(1.0, (bb_penetration * 10 + rsi_distance) / 2)

                    signals.iloc[i, signals.columns.get_loc("signal")] = 1
                    signals.iloc[i, signals.columns.get_loc("confidence")] = max(0.3, confidence)
                    signals.iloc[i, signals.columns.get_loc("reason")] = (
                        f"BB lower touch + RSI {rsi_curr:.1f}"
                    )

                    in_position = True
                    entry_price = close_curr

        total_signals = (signals["signal"] != 0).sum()
        buys = (signals["signal"] == 1).sum()
        sells = (signals["signal"] == -1).sum()

        logger.info(
            "%s generated %d signals (%d buys, %d sells) on %d bars",
            self.name, total_signals, buys, sells, len(data)
        )

        return signals
