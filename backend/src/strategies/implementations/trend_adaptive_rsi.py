"""Trend-Adaptive RSI Strategy.

Adapts RSI thresholds based on market trend to work in ALL market conditions.

UPTREND: Buy dips (RSI 40-50) instead of waiting for extreme oversold
DOWNTREND: Sell rips (RSI 50-60) instead of waiting for extreme overbought
RANGE: Use standard RSI (30/70)

This solves the problem of mean reversion strategies not trading in strong trends.

Target: 10-20 trades/month on daily bars, 2-4/day on 15Min bars.
"""

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.trend_adaptive")


class TrendAdaptiveRSI(BaseStrategy):
    """RSI mean reversion with adaptive thresholds based on trend.

    Trend Detection: Uses SMA(50) slope
    - Uptrend: Price > SMA(50) and SMA rising
    - Downtrend: Price < SMA(50) and SMA falling
    - Range: Otherwise

    Adaptive Thresholds:
    - Uptrend: Buy at RSI 45 (buy dips), Sell at RSI 65 (take profits)
    - Downtrend: Buy at RSI 35 (fade bounces), Sell at RSI 55 (short rips)
    - Range: Buy at RSI 35, Sell at RSI 65 (standard mean reversion)

    Why this works:
    - In uptrends, RSI rarely goes below 40 → we catch dips instead of waiting for crashes
    - In downtrends, RSI rarely goes above 60 → we fade bounces instead of waiting for spikes
    - In ranges, we use wider bands for true mean reversion
    - Trades in ALL market conditions instead of going quiet during trends
    """

    name = "Trend_Adaptive_RSI"

    def validate_params(self):
        p = self.params
        p.setdefault("rsi_period", 14)
        p.setdefault("trend_sma", 50)  # SMA period for trend detection
        p.setdefault("trend_lookback", 5)  # Bars to confirm trend direction

        # Uptrend thresholds (buy dips in uptrend)
        p.setdefault("uptrend_buy", 45)
        p.setdefault("uptrend_sell", 65)

        # Downtrend thresholds (sell rips in downtrend)
        p.setdefault("downtrend_buy", 35)
        p.setdefault("downtrend_sell", 55)

        # Range thresholds (standard mean reversion)
        p.setdefault("range_buy", 35)
        p.setdefault("range_sell", 65)

    def required_columns(self) -> list[str]:
        return ["Close", "RSI", f"SMA_{self.params.get('trend_sma', 50)}"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate adaptive signals based on market regime."""
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        close = data["Close"]
        rsi = data["RSI"]
        sma_col = f"SMA_{p['trend_sma']}"

        if sma_col not in data.columns:
            logger.error(f"Missing required column: {sma_col}")
            return signals

        sma = data[sma_col]

        # State machine
        in_position = False

        for i in range(p["trend_lookback"], len(data)):  # Need lookback for trend detection
            if pd.isna(close.iloc[i]) or pd.isna(rsi.iloc[i]) or pd.isna(sma.iloc[i]):
                continue

            close_curr = close.iloc[i]
            rsi_curr = rsi.iloc[i]
            sma_curr = sma.iloc[i]

            # Detect market regime
            above_sma = close_curr > sma_curr
            sma_slope = (sma.iloc[i] - sma.iloc[i - p["trend_lookback"]]) / sma.iloc[i - p["trend_lookback"]]

            if above_sma and sma_slope > 0.005:  # 0.5% rise over lookback = uptrend
                regime = "uptrend"
                buy_threshold = p["uptrend_buy"]
                sell_threshold = p["uptrend_sell"]
            elif not above_sma and sma_slope < -0.005:  # 0.5% fall = downtrend
                regime = "downtrend"
                buy_threshold = p["downtrend_buy"]
                sell_threshold = p["downtrend_sell"]
            else:  # Range
                regime = "range"
                buy_threshold = p["range_buy"]
                sell_threshold = p["range_sell"]

            if in_position:
                # Exit condition
                if rsi_curr > sell_threshold:
                    distance = rsi_curr - sell_threshold
                    confidence = min(1.0, distance / (100 - sell_threshold))

                    signals.iloc[i, signals.columns.get_loc("signal")] = -1
                    signals.iloc[i, signals.columns.get_loc("confidence")] = confidence
                    signals.iloc[i, signals.columns.get_loc("reason")] = (
                        f"Sell {regime}: RSI {rsi_curr:.1f} > {sell_threshold}"
                    )
                    in_position = False

            else:
                # Entry condition
                if rsi_curr < buy_threshold:
                    distance = buy_threshold - rsi_curr
                    confidence = min(1.0, distance / buy_threshold)

                    signals.iloc[i, signals.columns.get_loc("signal")] = 1
                    signals.iloc[i, signals.columns.get_loc("confidence")] = confidence
                    signals.iloc[i, signals.columns.get_loc("reason")] = (
                        f"Buy {regime}: RSI {rsi_curr:.1f} < {buy_threshold}"
                    )
                    in_position = True

        total_signals = (signals["signal"] != 0).sum()
        buys = (signals["signal"] == 1).sum()
        sells = (signals["signal"] == -1).sum()

        logger.info(
            "%s generated %d signals (%d buys, %d sells) on %d bars",
            self.name, total_signals, buys, sells, len(data)
        )

        return signals
