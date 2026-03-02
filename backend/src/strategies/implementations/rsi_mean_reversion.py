"""RSI Mean Reversion strategy with Bollinger Band confirmation, ADX filter, and stop-loss."""

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.rsi_mr")


class RSIMeanReversion(BaseStrategy):
    """Buy oversold / sell overbought using RSI with confirming indicators.

    State-aware: after a buy signal, only generates sell signals until
    the position is exited (overbought, stop-loss, or max holding period).
    Prevents cascading buys that cause extreme drawdowns.
    """

    name = "RSI_MeanReversion"

    def validate_params(self):
        p = self.params
        p.setdefault("rsi_period", 14)
        p.setdefault("oversold", 30)
        p.setdefault("overbought", 70)
        p.setdefault("use_bb_confirmation", True)
        p.setdefault("use_adx_filter", False)
        p.setdefault("adx_threshold", 25)
        p.setdefault("cooldown_days", 3)
        p.setdefault("stop_loss_atr_mult", 2.5)
        p.setdefault("max_holding_days", 40)

        if not (0 < p["oversold"] < p["overbought"] < 100):
            raise ValueError("Need 0 < oversold < overbought < 100")

    def required_columns(self) -> list[str]:
        cols = ["Close", "RSI", "ATR"]
        if self.params.get("use_bb_confirmation"):
            cols += ["BB_Lower", "BB_Upper"]
        if self.params.get("use_adx_filter"):
            cols.append("ADX")
        return cols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        rsi = data["RSI"]
        close = data["Close"]
        atr = data["ATR"]

        # State machine: tracks whether we're in a position
        in_position = False
        entry_price = 0.0
        entry_bar = 0
        stop_loss = 0.0
        last_signal_bar = -p["cooldown_days"] - 1

        for i in range(len(data)):
            if rsi.iloc[i] != rsi.iloc[i]:  # NaN check
                continue

            if in_position:
                # Check exit conditions
                exit_reason = None
                current_close = close.iloc[i]

                # 1. RSI overbought exit
                overbought = rsi.iloc[i] > p["overbought"]
                if overbought:
                    bb_sell = True
                    if p["use_bb_confirmation"] and "BB_Upper" in data.columns:
                        bb_sell = current_close >= data["BB_Upper"].iloc[i]
                    if bb_sell:
                        exit_reason = "RSI overbought"
                        if p["use_bb_confirmation"]:
                            exit_reason += " + BB upper touch"

                # 2. Stop-loss exit
                if exit_reason is None and current_close <= stop_loss:
                    loss_pct = (current_close / entry_price - 1) * 100
                    exit_reason = f"Stop-loss hit ({loss_pct:.1f}%)"

                # 3. Max holding period exit
                if exit_reason is None and (i - entry_bar) >= p["max_holding_days"]:
                    pnl = (current_close / entry_price - 1) * 100
                    exit_reason = f"Max hold {p['max_holding_days']}d ({pnl:+.1f}%)"

                if exit_reason is not None:
                    signals.iloc[i, signals.columns.get_loc("signal")] = -1
                    signals.iloc[i, signals.columns.get_loc("reason")] = exit_reason
                    conf = ((rsi.iloc[i] - p["overbought"]) / (100 - p["overbought"]))
                    signals.iloc[i, signals.columns.get_loc("confidence")] = max(0.3, min(1.0, conf))
                    in_position = False
                    last_signal_bar = i

            else:
                # Check entry conditions (with cooldown)
                if i - last_signal_bar <= p["cooldown_days"]:
                    continue

                oversold = rsi.iloc[i] < p["oversold"]
                if not oversold:
                    continue

                # Bollinger Band confirmation
                if p["use_bb_confirmation"] and "BB_Lower" in data.columns:
                    if close.iloc[i] > data["BB_Lower"].iloc[i]:
                        continue

                # ADX filter — only trade when ADX confirms momentum
                if p["use_adx_filter"] and "ADX" in data.columns:
                    adx_val = data["ADX"].iloc[i]
                    if adx_val != adx_val:  # NaN
                        continue
                    if adx_val > p["adx_threshold"]:
                        continue  # skip trending markets for mean reversion

                # Entry signal
                signals.iloc[i, signals.columns.get_loc("signal")] = 1
                buy_conf = (p["oversold"] - rsi.iloc[i]) / p["oversold"]
                signals.iloc[i, signals.columns.get_loc("confidence")] = min(1.0, buy_conf)

                reason = "RSI oversold"
                if p["use_bb_confirmation"]:
                    reason += " + BB lower touch"
                signals.iloc[i, signals.columns.get_loc("reason")] = reason

                in_position = True
                entry_price = close.iloc[i]
                entry_bar = i
                atr_val = atr.iloc[i] if atr.iloc[i] == atr.iloc[i] else entry_price * 0.02
                stop_loss = entry_price - p["stop_loss_atr_mult"] * atr_val
                last_signal_bar = i

        logger.info(
            "%s generated %d signals on %d bars",
            self.name, (signals["signal"] != 0).sum(), len(data),
        )
        return signals
