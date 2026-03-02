"""Custom exceptions for AlphaLab."""


class AlphaLabException(Exception):
    """Base exception for all AlphaLab errors."""


class DataFetchError(AlphaLabException):
    """Data fetching failed after retries."""


class InvalidTickerError(DataFetchError):
    """Ticker symbol not found or delisted."""


class InsufficientDataError(DataFetchError):
    """Not enough data points returned."""


class DataValidationError(AlphaLabException):
    """Data failed quality validation."""


class InvalidStrategyError(AlphaLabException):
    """Invalid strategy name or configuration."""


class BacktestError(AlphaLabException):
    """Backtest execution failed."""


class PortfolioError(AlphaLabException):
    """Portfolio operation failed (insufficient funds, position limits, etc.)."""
