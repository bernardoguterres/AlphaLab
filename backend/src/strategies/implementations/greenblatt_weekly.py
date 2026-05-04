"""Greenblatt Weekly strategy — weekly entry timing for value stocks.

Designed to run on WEEKLY bars (interval="1wk").
Use after FundamentalScreener has identified quality candidates.

Entry (any one):
  - Weekly RSI < rsi_oversold (default 35)
  - 10-week SMA crosses above 50-week SMA (weekly golden cross)

Exit — in priority order:
  1. Trailing stop: close drops more than trailing_stop_pct below the
     position's peak price (default 20%). Always fires immediately.
  2. RSI overbought (optional, off by default): close after min_hold_bars
     if exit_rsi_overbought=True and RSI > rsi_overbought.
  3. SMA death-cross (optional, off by default): close after min_hold_bars
     if exit_sma_cross=True.

Default behaviour: hold for at least 52 weeks (~1 year), only exit on a
20% trailing drawdown from peak. This mirrors how Greenblatt's published
results actually work — let quality businesses compound, cut the losers.
RSI/SMA exits are available as optional levers but are disabled by default
because backtests showed they cut winners too early.
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
        p.setdefault("fast_sma", 10)
        p.setdefault("slow_sma", 50)            # 50 weeks ≈ 1 year
        p.setdefault("rsi_period", 14)
        p.setdefault("rsi_oversold", 35)
        p.setdefault("rsi_overbought", 65)
        p.setdefault("min_hold_bars", 52)        # 52 weeks = ~1 year
        p.setdefault("trailing_stop_pct", 0.20)  # 20% below peak
        p.setdefault("exit_rsi_overbought", False)
        p.setdefault("exit_sma_cross", False)

        if p["fast_sma"] >= p["slow_sma"]:
            raise ValueError("fast_sma must be < slow_sma")
        if p["rsi_oversold"] >= p["rsi_overbought"]:
            raise ValueError("rsi_oversold must be < rsi_overbought")
        if not 0.05 <= p["trailing_stop_pct"] <= 0.50:
            raise ValueError("trailing_stop_pct must be between 0.05 and 0.50")

    def required_columns(self) -> list[str]:
        fast = self.params.get("fast_sma", 10)
        slow = self.params.get("slow_sma", 50)
        return ["Close", "RSI", f"SMA_{fast}", f"SMA_{slow}"]

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
        fast_sma = data[fast_col]
        slow_sma = data[slow_col]

        in_position = False
        entry_bar = 0
        peak_price = 0.0

        for i in range(1, len(data)):
            if pd.isna(fast_sma.iloc[i]) or pd.isna(slow_sma.iloc[i]):
                continue
            if pd.isna(rsi.iloc[i]):
                continue

            price = close.iloc[i]
            bars_held = i - entry_bar if in_position else 0

            # --- EXIT logic ---
            if in_position:
                # Track peak for trailing stop
                if price > peak_price:
                    peak_price = price

                trailing_stop_level = peak_price * (1 - p["trailing_stop_pct"])
                hit_trailing_stop = price <= trailing_stop_level

                if hit_trailing_stop:
                    signals.at[data.index[i], "signal"] = -1
                    signals.at[data.index[i], "confidence"] = 0.95
                    signals.at[data.index[i], "reason"] = (
                        f"Trailing stop: {price:.2f} <= {trailing_stop_level:.2f} "
                        f"({p['trailing_stop_pct']:.0%} below peak {peak_price:.2f})"
                    )
                    in_position = False
                    continue

                min_hold_met = bars_held >= p["min_hold_bars"]

                if min_hold_met and p["exit_rsi_overbought"] and rsi.iloc[i] > p["rsi_overbought"]:
                    signals.at[data.index[i], "signal"] = -1
                    signals.at[data.index[i], "confidence"] = 0.75
                    signals.at[data.index[i], "reason"] = (
                        f"RSI overbought after {bars_held}w hold "
                        f"({rsi.iloc[i]:.1f} > {p['rsi_overbought']})"
                    )
                    in_position = False
                    continue

                sma_cross_down = (
                    fast_sma.iloc[i] < slow_sma.iloc[i]
                    and fast_sma.iloc[i - 1] >= slow_sma.iloc[i - 1]
                )
                if min_hold_met and p["exit_sma_cross"] and sma_cross_down:
                    signals.at[data.index[i], "signal"] = -1
                    signals.at[data.index[i], "confidence"] = 0.70
                    signals.at[data.index[i], "reason"] = (
                        f"SMA death-cross after {bars_held}w hold: "
                        f"SMA{p['fast_sma']}={fast_sma.iloc[i]:.2f} < SMA{p['slow_sma']}={slow_sma.iloc[i]:.2f}"
                    )
                    in_position = False
                continue

            # --- ENTRY logic ---
            sma_cross_up = (
                fast_sma.iloc[i] > slow_sma.iloc[i]
                and fast_sma.iloc[i - 1] <= slow_sma.iloc[i - 1]
            )
            rsi_oversold = rsi.iloc[i] < p["rsi_oversold"]

            if rsi_oversold or sma_cross_up:
                reasons, conf = [], 0.0
                if rsi_oversold:
                    reasons.append(f"Weekly RSI oversold ({rsi.iloc[i]:.1f} < {p['rsi_oversold']})")
                    conf = max(conf, 0.75)
                if sma_cross_up:
                    reasons.append(
                        f"Weekly golden cross: SMA{p['fast_sma']}={fast_sma.iloc[i]:.2f} "
                        f"> SMA{p['slow_sma']}={slow_sma.iloc[i]:.2f}"
                    )
                    conf = max(conf, 0.80)
                if rsi_oversold and sma_cross_up:
                    conf = 0.90

                signals.at[data.index[i], "signal"] = 1
                signals.at[data.index[i], "confidence"] = conf
                signals.at[data.index[i], "reason"] = " + ".join(reasons)

                in_position = True
                entry_bar = i
                peak_price = price

        return signals
