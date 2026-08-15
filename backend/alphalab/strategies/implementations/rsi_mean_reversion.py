"""RSI Mean Reversion strategy with Bollinger Band confirmation, ADX filter, and stop-loss."""

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.rsi_mr")


def rsi_wilder(close: pd.Series, period: int) -> pd.Series:
    """Canonical RSI (Wilder, 1978), the single agreed-upon definition for
    deployable Alpha strategies (Prompt 2.5 remediation, 2026-08-15 - see
    FINAL_ENGINEERING_AUDIT.md / END_TO_END_VALIDATION.md).

    This strategy previously read a fixed, shared `data["RSI"]` column
    (FeatureEngineer's hardcoded RSI(14), an EWM formula with no warm-up
    guard) regardless of its own `rsi_period` parameter - so a nominal
    "RSI(9)" backtest never actually computed or traded on a 9-period RSI.
    This function is strategy-local (touches nothing else - the other six
    AlphaLab strategies that read `data["RSI"]` are unaffected) and is
    parameterized by the real `rsi_period`.

    Semantics (independently re-implemented in AlphaLive's
    alphalive/strategy/indicators.py::rsi_wilder() - same formula, seeding,
    warm-up and NaN behaviour, cross-checked by shared golden-value tests
    in both repos' test suites, not a shared dependency, matching this
    project's deliberate "two independent implementations + parity test"
    pattern used everywhere else):

    - avg_gain/avg_loss seed at index `period` (0-indexed) as the simple
      mean of the first `period` gains/losses (positions 1..period, since
      the first close has no prior bar to diff against).
    - Every subsequent bar uses Wilder's recursive smoothing:
      avg = (prev_avg * (period - 1) + current) / period.
    - RSI = 100 - 100 / (1 + avg_gain / avg_loss).
    - avg_loss == 0 and avg_gain > 0 -> RSI = 100 (pure uptrend).
    - avg_gain == 0 and avg_loss == 0 -> RSI = 50 (flat/no movement).
    - Rows before index `period` are NaN (insufficient warm-up) - the
      strategy must never trade on an immature RSI value.
    """
    n = len(close)
    rsi = pd.Series(np.nan, index=close.index, dtype=float)
    if n <= period:
        return rsi

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)

    avg_gain[period] = gain.iloc[1 : period + 1].mean()
    avg_loss[period] = loss.iloc[1 : period + 1].mean()

    gain_vals = gain.to_numpy()
    loss_vals = loss.to_numpy()
    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain_vals[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss_vals[i]) / period

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi_vals = 100.0 - (100.0 / (1.0 + rs))

    flat = (avg_gain == 0) & (avg_loss == 0)
    pure_uptrend = (avg_loss == 0) & (avg_gain > 0)
    rsi_vals = np.where(flat, 50.0, rsi_vals)
    rsi_vals = np.where(pure_uptrend, 100.0, rsi_vals)
    rsi_vals[:period] = np.nan

    rsi = pd.Series(rsi_vals, index=close.index, dtype=float).clip(0, 100)
    rsi.iloc[:period] = np.nan
    return rsi


class RSIMeanReversion(BaseStrategy):
    """Buy oversold / sell overbought using RSI with confirming indicators.

    State-aware: after a buy signal, only generates sell signals until
    the position is exited (overbought, stop-loss, or max holding period).
    Prevents cascading buys that cause extreme drawdowns.

    rsi_period now genuinely controls the RSI calculation this strategy
    trades on (fixed 2026-08-15 - see rsi_wilder() above). Previously it
    was accepted as a parameter but silently ignored.
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
        if p["rsi_period"] < 2:
            raise ValueError("rsi_period must be >= 2")

    def required_columns(self) -> list[str]:
        # RSI is no longer read from the precomputed feature set - this
        # strategy computes its own RSI(rsi_period) locally (see rsi_wilder
        # above) so its rsi_period parameter has a real effect.
        cols = ["Close", "ATR"]
        if self.params.get("use_bb_confirmation"):
            cols += ["BB_Lower", "BB_Upper"]
        if self.params.get("use_adx_filter"):
            cols.append("ADX")
        return cols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        signals = self._init_signals_frame(data)

        rsi = rsi_wilder(data["Close"], p["rsi_period"])
        close = data["Close"]
        atr = data["ATR"]

        # State machine: tracks whether we're in a position
        in_position = False
        entry_price = 0.0
        entry_bar = 0
        stop_loss = 0.0
        last_signal_bar = -p["cooldown_days"] - 1

        for i in range(len(data)):
            if pd.isna(rsi.iloc[i]):
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
                    conf = (rsi.iloc[i] - p["overbought"]) / (100 - p["overbought"])
                    signals.iloc[i, signals.columns.get_loc("confidence")] = max(
                        0.3, min(1.0, conf)
                    )
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

                # ADX filter - only trade when ADX confirms momentum
                if p["use_adx_filter"] and "ADX" in data.columns:
                    adx_val = data["ADX"].iloc[i]
                    if adx_val != adx_val:  # NaN
                        continue
                    if adx_val > p["adx_threshold"]:
                        continue  # skip trending markets for mean reversion

                # Entry signal
                signals.iloc[i, signals.columns.get_loc("signal")] = 1
                buy_conf = (p["oversold"] - rsi.iloc[i]) / p["oversold"]
                signals.iloc[i, signals.columns.get_loc("confidence")] = min(
                    1.0, buy_conf
                )

                reason = "RSI oversold"
                if p["use_bb_confirmation"]:
                    reason += " + BB lower touch"
                signals.iloc[i, signals.columns.get_loc("reason")] = reason

                in_position = True
                entry_price = close.iloc[i]
                entry_bar = i
                atr_val = (
                    atr.iloc[i] if not pd.isna(atr.iloc[i]) else entry_price * 0.02
                )
                stop_loss = entry_price - p["stop_loss_atr_mult"] * atr_val
                last_signal_bar = i

        logger.info(
            "%s generated %d signals on %d bars",
            self.name,
            (signals["signal"] != 0).sum(),
            len(data),
        )
        return signals
