"""Abstract base class for all trading strategies."""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.strategy")


class BaseStrategy(ABC):
    """Interface all strategies must implement.

    Subclasses must define ``validate_params`` and ``generate_signals``.
    """

    name: str = "BaseStrategy"

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = params or {}
        self.validate_params()

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def validate_params(self):
        """Raise ``ValueError`` if params are invalid."""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame with columns: signal (1/-1/0), confidence, reason."""

    @abstractmethod
    def required_columns(self) -> list[str]:
        """Return list of DataFrame columns this strategy needs."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def backtest_ready_check(self, data: pd.DataFrame) -> bool:
        """Verify *data* has the columns this strategy requires."""
        missing = set(self.required_columns()) - set(data.columns)
        if missing:
            logger.warning("%s: missing columns for backtest: %s", self.name, missing)
            return False
        return True

    @staticmethod
    def calculate_signal_quality(signals: pd.DataFrame) -> dict:
        """Evaluate signal quality — flag overtrading or sparse signals."""
        if signals.empty or "signal" not in signals.columns:
            return {"trades": 0, "quality": "no_signals"}

        trades = (signals["signal"] != 0).sum()
        total = len(signals)
        trade_pct = trades / total if total else 0

        # Overtrading: more than 20% of bars
        if trade_pct > 0.20:
            quality = "overtrading"
        elif trade_pct < 0.005:
            quality = "too_few"
        else:
            quality = "good"

        # Average holding period
        in_trade = signals["signal"].ne(0)
        runs = in_trade.ne(in_trade.shift()).cumsum()
        avg_hold = in_trade.groupby(runs).sum().mean() if in_trade.any() else 0

        return {
            "total_signals": int(trades),
            "signal_pct": round(trade_pct, 4),
            "avg_holding_bars": round(float(avg_hold), 1),
            "quality": quality,
        }

