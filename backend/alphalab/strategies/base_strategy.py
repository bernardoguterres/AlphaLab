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

    @staticmethod
    def _init_signals_frame(data: pd.DataFrame) -> pd.DataFrame:
        """Build the empty signals DataFrame every strategy starts from."""
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""
        return signals

    @staticmethod
    def _apply_cooldown(signals: pd.DataFrame, cooldown: int) -> pd.DataFrame:
        """Suppress ENTRY signals (+1) that fall within `cooldown` bars of the
        previous emitted signal. Exit signals (-1) are never suppressed.

        Both engines are long-only. Suppressing an exit (the pre-2026-10
        behaviour, which cooled down every signal) left the backtest engine
        holding a position the strategy believed it had closed - e.g. an MA
        death cross 3 bars after a golden cross was dropped, the position
        was held until the next death cross, and the intervening golden
        cross bought a second, stacked position.
        """
        if cooldown <= 0:
            return signals
        last_signal_idx = -cooldown - 1
        sig_col = signals.columns.get_loc("signal")
        reason_col = signals.columns.get_loc("reason")
        for i in range(len(signals)):
            value = signals.iat[i, sig_col]
            if value == 0:
                continue
            if value > 0 and i - last_signal_idx <= cooldown:
                signals.iat[i, sig_col] = 0
                signals.iat[i, reason_col] = ""
                continue
            last_signal_idx = i
        return signals

    def _reject_unknown_params(self, known: set[str]):
        """Raise ValueError if ``self.params`` has any key outside ``known``.

        Call at the end of ``validate_params()``, after every
        ``setdefault()`` call, so a caller-supplied param name this strategy
        doesn't recognize (a typo, a retired field, a param meant for a
        different strategy) fails loudly at construction time instead of
        being silently accepted into ``self.params`` and then just never
        read by ``generate_signals()``.
        """
        unknown = set(self.params) - known
        if unknown:
            raise ValueError(
                f"{self.name}: unknown parameter(s) {sorted(unknown)} - "
                f"valid parameters are {sorted(known)}"
            )

    def backtest_ready_check(self, data: pd.DataFrame) -> bool:
        """Verify *data* has the columns this strategy requires."""
        missing = set(self.required_columns()) - set(data.columns)
        if missing:
            logger.warning("%s: missing columns for backtest: %s", self.name, missing)
            return False
        return True
