"""Experimental strategies for offline evaluation with the backtest engine."""

from .base_strategy import BaseStrategy


class DonchianBreakout(BaseStrategy):
    """Enter above the prior 55-bar high and exit below the prior 20-bar low."""

    name = "Research Donchian 55/20"

    def validate_params(self):
        self._reject_unknown_params(set())

    def required_columns(self):
        return ["High", "Low", "Close"]

    def generate_signals(self, data):
        close = data["Close"]
        entries = close > data["High"].shift(1).rolling(55).max()
        exits = close < data["Low"].shift(1).rolling(20).min()
        return _position_changes(
            self, data, entries, exits, "55-bar breakout", "20-bar breakdown"
        )


class TrendPullback(BaseStrategy):
    """Buy a 3% five-bar decline above the 100-bar average."""

    name = "Research Trend Pullback"

    def validate_params(self):
        self._reject_unknown_params(set())

    def required_columns(self):
        return ["Close"]

    def generate_signals(self, data):
        close = data["Close"]
        trend = close.rolling(100).mean()
        entries = (close > trend) & (close.pct_change(5) <= -0.03)
        exits = (close >= close.rolling(10).mean()) | (close < trend)
        return _position_changes(
            self,
            data,
            entries & ~exits,
            exits,
            "Trend pullback",
            "Recovery or trend break",
        )


def _position_changes(strategy, data, entries, exits, entry_reason, exit_reason):
    signals = strategy._init_signals_frame(data)
    long = False
    for timestamp, entry, exit in zip(data.index, entries, exits):
        if not long and entry:
            signals.loc[timestamp] = (1, 1.0, entry_reason)
            long = True
        elif long and exit:
            signals.loc[timestamp] = (-1, 1.0, exit_reason)
            long = False
    return signals
