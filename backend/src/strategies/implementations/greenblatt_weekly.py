"""Greenblatt Weekly strategy — weekly entry timing for value stocks.

Designed to run on WEEKLY bars (interval="1wk").
Use after FundamentalScreener has identified quality candidates.

Entry conditions (any one):
  - Weekly RSI < rsi_oversold (default 35)  OR
  - 10-week SMA crosses above 40-week SMA (weekly golden cross)

Exit conditions (first triggered):
  - Weekly RSI > rsi_overbought (default 65)  OR
  - 10-week SMA crosses below 40-week SMA  OR
  - Hard stop loss (stop_loss_atr_mult × weekly ATR)

Minimum hold: min_hold_bars weeks (default 12 = ~3 months).
This prevents exiting a position that just triggered an entry signal.
"""

import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.greenblatt_weekly")


class GreenblattWeekly(BaseStrategy):
    """Weekly entry timing for Greenblatt-screened value stocks."""

    name = "GreenblattWeekly"

    def validate_params(self):
        p = self.params
        p.setdefault("fast_sma", 10)           # weeks
        p.setdefault("slow_sma", 50)           # weeks (~1 year) — matches FeatureEngineer output
        p.setdefault("rsi_period", 14)
        p.setdefault("rsi_oversold", 35)
        p.setdefault("rsi_overbought", 65)
        p.setdefault("min_hold_bars", 12)      # weeks minimum hold (~3 months)
        p.setdefault("stop_loss_atr_mult", 2.0)

        if p["fast_sma"] >= p["slow_sma"]:
            raise ValueError("fast_sma must be < slow_sma")
        if p["rsi_oversold"] >= p["rsi_overbought"]:
            raise ValueError("rsi_oversold must be < rsi_overbought")

    def required_columns(self) -> list[str]:
        fast = self.params.get("fast_sma", 10)
        slow = self.params.get("slow_sma", 40)
        return ["Close", "RSI", "ATR", f"SMA_{fast}", f"SMA_{slow}"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        fast_col = f"SMA_{p['fast_sma']}"
        slow_col = f"SMA_{p['slow_sma']}"

        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        close = data["Close"]
        rsi = data["RSI"]
        atr = data["ATR"]
        fast_sma = data[fast_col]
        slow_sma = data[slow_col]

        in_position = False
        entry_bar = 0
        stop_price = 0.0

        for i in range(1, len(data)):
            # Need both SMA values valid
            if pd.isna(fast_sma.iloc[i]) or pd.isna(slow_sma.iloc[i]):
                continue
            if pd.isna(rsi.iloc[i]) or pd.isna(atr.iloc[i]):
                continue

            bars_held = i - entry_bar if in_position else 0

            # --- EXIT logic (checked first) ---
            if in_position:
                hit_stop = close.iloc[i] <= stop_price
                rsi_exit = rsi.iloc[i] > p["rsi_overbought"]
                sma_cross_down = (
                    fast_sma.iloc[i] < slow_sma.iloc[i]
                    and fast_sma.iloc[i - 1] >= slow_sma.iloc[i - 1]
                )

                min_hold_met = bars_held >= p["min_hold_bars"]

                if hit_stop:
                    signals.at[data.index[i], "signal"] = -1
                    signals.at[data.index[i], "confidence"] = 0.95
                    signals.at[data.index[i], "reason"] = (
                        f"Stop loss hit: {close.iloc[i]:.2f} <= {stop_price:.2f}"
                    )
                    in_position = False
                    continue

                if min_hold_met and (rsi_exit or sma_cross_down):
                    reason = (
                        f"RSI overbought ({rsi.iloc[i]:.1f} > {p['rsi_overbought']})"
                        if rsi_exit
                        else f"Weekly SMA cross-down: SMA{p['fast_sma']}={fast_sma.iloc[i]:.2f} < SMA{p['slow_sma']}={slow_sma.iloc[i]:.2f}"
                    )
                    confidence = 0.80 if rsi_exit else 0.75
                    signals.at[data.index[i], "signal"] = -1
                    signals.at[data.index[i], "confidence"] = confidence
                    signals.at[data.index[i], "reason"] = reason
                    in_position = False
                continue

            # --- ENTRY logic ---
            sma_cross_up = (
                fast_sma.iloc[i] > slow_sma.iloc[i]
                and fast_sma.iloc[i - 1] <= slow_sma.iloc[i - 1]
            )
            rsi_oversold = rsi.iloc[i] < p["rsi_oversold"]

            if rsi_oversold or sma_cross_up:
                reasons = []
                conf = 0.0
                if rsi_oversold:
                    reasons.append(f"Weekly RSI oversold ({rsi.iloc[i]:.1f} < {p['rsi_oversold']})")
                    conf = max(conf, 0.75)
                if sma_cross_up:
                    reasons.append(
                        f"Weekly golden cross: SMA{p['fast_sma']}={fast_sma.iloc[i]:.2f} > SMA{p['slow_sma']}={slow_sma.iloc[i]:.2f}"
                    )
                    conf = max(conf, 0.80)
                # Both triggers = higher confidence
                if rsi_oversold and sma_cross_up:
                    conf = 0.90

                signals.at[data.index[i], "signal"] = 1
                signals.at[data.index[i], "confidence"] = conf
                signals.at[data.index[i], "reason"] = " + ".join(reasons)

                in_position = True
                entry_bar = i
                stop_price = close.iloc[i] - p["stop_loss_atr_mult"] * atr.iloc[i]

        return signals
