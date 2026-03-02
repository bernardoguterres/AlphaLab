"""Abstract base class for all trading strategies."""

from abc import ABC, abstractmethod
from itertools import product
from typing import Any

import numpy as np
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
            logger.warning(
                "%s: missing columns for backtest: %s", self.name, missing
            )
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

    def optimize_params(
        self,
        data: pd.DataFrame,
        param_grid: dict[str, list],
        metric: str = "total_return",
    ) -> dict:
        """Grid search for best parameters by running backtests.

        Args:
            data: Full OHLCV + features DataFrame.
            param_grid: e.g. {"short_window": [20, 50], "long_window": [100, 200]}
            metric: Key to maximize in the results dict.

        Returns:
            Dict with ``best_params``, ``best_score``, and ``all_results``.
        """
        keys = list(param_grid.keys())
        combos = list(product(*param_grid.values()))
        results = []

        for combo in combos:
            test_params = dict(zip(keys, combo))
            try:
                instance = self.__class__(test_params)
                signals = instance.generate_signals(data)
                # Simple return estimation: sum of returns on signal days
                if "Close" in data.columns and "signal" in signals.columns:
                    aligned = signals["signal"].reindex(data.index, fill_value=0)
                    daily_ret = data["Close"].pct_change()
                    strat_ret = (aligned.shift(1) * daily_ret).sum()
                else:
                    strat_ret = 0.0

                results.append({**test_params, metric: round(strat_ret, 6)})
            except (ValueError, KeyError) as e:
                logger.debug("Skipping params %s: %s", test_params, e)

        if not results:
            return {"best_params": self.params, "best_score": 0, "all_results": []}

        best = max(results, key=lambda r: r.get(metric, 0))
        return {
            "best_params": {k: best[k] for k in keys},
            "best_score": best[metric],
            "all_results": results,
        }
