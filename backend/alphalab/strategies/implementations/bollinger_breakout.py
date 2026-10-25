"""Bollinger Band Breakout strategy with confirmation and volume filter."""

import pandas as pd

from ..base_strategy import BaseStrategy
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.strategy.bb_breakout")


class BollingerBreakout(BaseStrategy):
    """Long-only Bollinger Band breakout with confirmation and volume filter.

    BUY (flat): price closes above the upper band for `confirmation_bars`
        consecutive bars, and (if volume_filter) volume >= 20-bar average x
        volume_threshold. Entries are subject to `cooldown_days` bars since
        the previous signal.
    SELL (long): price returns to the middle band - close <= SMA x 1.01
        (i.e. within 1% above the SMA, or anywhere below it).

    Corrected 2026-10: the previous version also modelled a SHORT leg (a
    lower-band breakdown set position -1 and a later return to the middle
    emitted +1 to "cover"). Every consumer is long-only, so that +1 was
    executed as a LONG ENTRY and could stack onto an existing long. The
    exit window was also symmetric (|close/SMA - 1| <= 1%), so a long that
    gapped straight through the middle band never exited. Exits are no
    longer subject to cooldown (see BaseStrategy._apply_cooldown).
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

        self._reject_unknown_params(
            {
                "bb_period",
                "bb_std_dev",
                "confirmation_bars",
                "volume_filter",
                "volume_threshold",
                "cooldown_days",
            }
        )

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
        cooldown = p["cooldown_days"]
        close = data["Close"]

        # Bollinger Bands (sample std, ddof=1 - pandas default)
        sma = close.rolling(period, min_periods=period).mean()
        rolling_std = close.rolling(period, min_periods=period).std()
        upper_band = sma + (rolling_std * std_dev)

        signals = self._init_signals_frame(data)

        above_upper = (close > upper_band).astype(int)
        consecutive_above = (
            above_upper.rolling(confirmation).sum() >= confirmation
        ).to_numpy()
        exit_zone = (close <= sma * 1.01).to_numpy()

        vol_ok = pd.Series(True, index=data.index)
        if p["volume_filter"] and "Volume" in data.columns:
            vol_avg = data["Volume"].rolling(20).mean()
            vol_ok = data["Volume"] >= (vol_avg * p["volume_threshold"])
        vol_ok = vol_ok.to_numpy()

        close_arr = close.to_numpy()
        upper_arr = upper_band.to_numpy()
        sig_col = signals.columns.get_loc("signal")
        conf_col = signals.columns.get_loc("confidence")
        reason_col = signals.columns.get_loc("reason")

        in_position = False
        last_signal_bar = -cooldown - 1
        for i in range(len(data)):
            if not in_position:
                if i - last_signal_bar <= cooldown:
                    continue
                if consecutive_above[i] and vol_ok[i]:
                    signals.iat[i, sig_col] = 1
                    signals.iat[i, reason_col] = f"{confirmation} closes above upper BB"
                    distance_pct = (close_arr[i] - upper_arr[i]) / upper_arr[i] * 100
                    signals.iat[i, conf_col] = min(distance_pct / 2, 1.0)
                    in_position = True
                    last_signal_bar = i
            elif exit_zone[i]:
                signals.iat[i, sig_col] = -1
                signals.iat[i, reason_col] = "Price returned to middle band"
                signals.iat[i, conf_col] = 0.5
                in_position = False
                last_signal_bar = i

        logger.info(
            "%s generated %d signals on %d bars",
            self.name,
            (signals["signal"] != 0).sum(),
            len(data),
        )
        return signals
