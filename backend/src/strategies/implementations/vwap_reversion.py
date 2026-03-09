"""VWAP Mean Reversion strategy with RSI filter."""

import pandas as pd
import numpy as np

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.vwap_reversion")


class VWAPReversion(BaseStrategy):
    """Generate signals when price deviates significantly from VWAP.

    BUY: Price < VWAP - (deviation_threshold × std) AND RSI < oversold
    SELL: Price > VWAP + (deviation_threshold × std) AND RSI > overbought
    EXIT: Price returns to VWAP

    Uses rolling VWAP calculation and RSI confirmation to filter false signals.
    """

    name = "VWAP_Reversion"

    def validate_params(self):
        p = self.params
        p.setdefault("vwap_period", 20)
        p.setdefault("deviation_threshold", 2.0)
        p.setdefault("rsi_period", 14)
        p.setdefault("oversold", 30)
        p.setdefault("overbought", 70)
        p.setdefault("cooldown_days", 3)

        if not 5 <= p["vwap_period"] <= 50:
            raise ValueError("vwap_period must be between 5 and 50")
        if not 0.5 <= p["deviation_threshold"] <= 5.0:
            raise ValueError("deviation_threshold must be between 0.5 and 5.0")
        if not 5 <= p["rsi_period"] <= 30:
            raise ValueError("rsi_period must be between 5 and 30")
        if not 10 <= p["oversold"] <= 40:
            raise ValueError("oversold must be between 10 and 40")
        if not 60 <= p["overbought"] <= 90:
            raise ValueError("overbought must be between 60 and 90")
        if p["oversold"] >= p["overbought"]:
            raise ValueError("oversold must be less than overbought")
        if p["cooldown_days"] < 0:
            raise ValueError("cooldown_days must be >= 0")

    def required_columns(self) -> list[str]:
        return ["Close", "Volume", "RSI"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate mean reversion signals based on VWAP deviation."""
        p = self.params
        period = p["vwap_period"]
        deviation = p["deviation_threshold"]
        oversold = p["oversold"]
        overbought = p["overbought"]
        cooldown = p["cooldown_days"]

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        # Calculate rolling VWAP
        typical_price = (data["High"] + data["Low"] + data["Close"]) / 3
        vwap = (typical_price * data["Volume"]).rolling(period).sum() / data["Volume"].rolling(period).sum()

        # Calculate standard deviation of price from VWAP
        price_diff = data["Close"] - vwap
        vwap_std = price_diff.rolling(period).std()

        # Upper and lower deviation bands
        upper_band = vwap + (deviation * vwap_std)
        lower_band = vwap - (deviation * vwap_std)

        # Get RSI
        rsi = data["RSI"]

        # Track position state: 0 = no position, 1 = long, -1 = short
        position = 0
        last_signal_idx = -cooldown - 1

        for i in range(period, len(data)):
            idx = data.index[i]
            close = data["Close"].iloc[i]
            current_vwap = vwap.iloc[i]
            current_rsi = rsi.iloc[i]
            lower = lower_band.iloc[i]
            upper = upper_band.iloc[i]

            # Skip if any values are NaN
            if pd.isna([current_vwap, lower, upper, current_rsi]).any():
                continue

            # Enforce cooldown
            if i - last_signal_idx <= cooldown:
                continue

            # No position: look for entry
            if position == 0:
                # BUY: Price below lower band AND RSI oversold
                if close < lower and current_rsi < oversold:
                    signals.loc[idx, "signal"] = 1
                    signals.loc[idx, "confidence"] = min(1.0, (lower - close) / lower * 10)
                    signals.loc[idx, "reason"] = f"Price {close:.2f} < VWAP lower {lower:.2f}, RSI {current_rsi:.1f}"
                    position = 1
                    last_signal_idx = i

                # SELL: Price above upper band AND RSI overbought
                elif close > upper and current_rsi > overbought:
                    signals.loc[idx, "signal"] = -1
                    signals.loc[idx, "confidence"] = min(1.0, (close - upper) / upper * 10)
                    signals.loc[idx, "reason"] = f"Price {close:.2f} > VWAP upper {upper:.2f}, RSI {current_rsi:.1f}"
                    position = -1
                    last_signal_idx = i

            # Long position: exit when price returns to VWAP
            elif position == 1:
                if close >= current_vwap:
                    signals.loc[idx, "signal"] = -1
                    signals.loc[idx, "confidence"] = 0.8
                    signals.loc[idx, "reason"] = f"Exit long: price {close:.2f} returned to VWAP {current_vwap:.2f}"
                    position = 0
                    last_signal_idx = i

            # Short position: exit when price returns to VWAP
            elif position == -1:
                if close <= current_vwap:
                    signals.loc[idx, "signal"] = 1
                    signals.loc[idx, "confidence"] = 0.8
                    signals.loc[idx, "reason"] = f"Exit short: price {close:.2f} returned to VWAP {current_vwap:.2f}"
                    position = 0
                    last_signal_idx = i

        return signals
