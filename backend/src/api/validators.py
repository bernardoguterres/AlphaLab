"""Pydantic request/response models for API validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class FetchDataRequest(BaseModel):
    tickers: list[str]
    start_date: str
    end_date: str
    interval: str = "1d"

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, v):
        if len(v) == 0:
            raise ValueError("Must provide at least one ticker")
        if len(v) > 20:
            raise ValueError("Maximum 20 tickers per request")
        cleaned = []
        for t in v:
            t = t.upper().strip()
            if not t.isalpha() or len(t) > 5:
                raise ValueError(f"Invalid ticker: {t}")
            cleaned.append(t)
        return cleaned

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v):
        if v not in ("1d", "1wk", "1mo"):
            raise ValueError("Interval must be one of: 1d, 1wk, 1mo")
        return v


class RiskSettings(BaseModel):
    """Risk management parameters for backtest."""
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 5.0
    max_position_size_pct: float = 10.0
    max_daily_loss_pct: float = 3.0
    max_open_positions: int = 5
    trailing_stop_enabled: bool = False
    trailing_stop_pct: float = 3.0
    commission_per_trade: float = 0.0

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_loss(cls, v):
        if not 0.1 <= v <= 50.0:
            raise ValueError("Stop loss must be between 0.1% and 50%")
        return v

    @field_validator("take_profit_pct")
    @classmethod
    def validate_take_profit(cls, v):
        if not 0.5 <= v <= 100.0:
            raise ValueError("Take profit must be between 0.5% and 100%")
        return v

    @field_validator("max_position_size_pct")
    @classmethod
    def validate_max_position(cls, v):
        if not 1.0 <= v <= 100.0:
            raise ValueError("Max position size must be between 1% and 100%")
        return v

    @field_validator("max_daily_loss_pct")
    @classmethod
    def validate_max_daily_loss(cls, v):
        if not 0.5 <= v <= 20.0:
            raise ValueError("Max daily loss must be between 0.5% and 20%")
        return v

    @field_validator("max_open_positions")
    @classmethod
    def validate_max_open(cls, v):
        if not 1 <= v <= 50:
            raise ValueError("Max open positions must be between 1 and 50")
        return v

    @field_validator("trailing_stop_pct")
    @classmethod
    def validate_trailing(cls, v):
        if v < 0.1 or v > 50.0:
            raise ValueError("Trailing stop must be between 0.1% and 50%")
        return v

    @field_validator("commission_per_trade")
    @classmethod
    def validate_commission(cls, v):
        if not 0.0 <= v <= 50.0:
            raise ValueError("Commission must be between $0 and $50")
        return v


class BacktestRequest(BaseModel):
    ticker: str
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float = 100_000
    params: Optional[dict] = None
    position_sizing: str = "equal_weight"
    monte_carlo_runs: int = 0
    risk_settings: Optional[RiskSettings] = None

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v):
        allowed = ("ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion")
        if v not in allowed:
            raise ValueError(f"Strategy must be one of: {', '.join(allowed)}")
        return v

    @field_validator("initial_capital")
    @classmethod
    def validate_capital(cls, v):
        if v < 1000:
            raise ValueError("Initial capital must be >= 1000")
        return v

    @field_validator("position_sizing")
    @classmethod
    def validate_sizing(cls, v):
        if v not in ("equal_weight", "risk_parity", "volatility_weighted"):
            raise ValueError("Invalid position sizing method")
        return v


class OptimizeRequest(BaseModel):
    ticker: str
    strategy: str
    start_date: str
    end_date: str
    param_grid: dict
    initial_capital: float = 100_000
    optimization_target: str = "sharpe_ratio"
    walk_forward: bool = False
    n_folds: int = 5

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v):
        allowed = ("ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion")
        if v not in allowed:
            raise ValueError(f"Strategy must be one of: {', '.join(allowed)}")
        return v

    @field_validator("optimization_target")
    @classmethod
    def validate_target(cls, v):
        allowed = ("sharpe_ratio", "total_return_pct", "max_drawdown_pct", "win_rate")
        if v not in allowed:
            raise ValueError(f"Optimization target must be one of: {', '.join(allowed)}")
        return v

    @field_validator("n_folds")
    @classmethod
    def validate_folds(cls, v):
        if not 2 <= v <= 10:
            raise ValueError("n_folds must be between 2 and 10")
        return v


class HeatmapRequest(BaseModel):
    """Request for parameter heatmap visualization."""
    ticker: str
    strategy: str
    start_date: str
    end_date: str
    param1_name: str
    param1_min: float
    param1_max: float
    param1_step: float
    param2_name: str
    param2_min: float
    param2_max: float
    param2_step: float
    fixed_params: Optional[dict] = None
    initial_capital: float = 100_000

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v):
        allowed = ("ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion")
        if v not in allowed:
            raise ValueError(f"Strategy must be one of: {', '.join(allowed)}")
        return v


class CompareRequest(BaseModel):
    ticker: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 100_000

    @field_validator("strategies")
    @classmethod
    def validate_strategies(cls, v):
        if len(v) < 2:
            raise ValueError("Need at least 2 strategies to compare")
        return v


class ExportStrategyRequest(BaseModel):
    """Request to export a strategy config for AlphaLive."""
    backtest_id: str


class BatchBacktestRequest(BaseModel):
    """Request to run batch backtests across multiple tickers."""
    tickers: list[str]
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float = 100_000
    params: Optional[dict] = None
    position_sizing: str = "equal_weight"
    risk_settings: Optional[RiskSettings] = None

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, v):
        if len(v) == 0:
            raise ValueError("Must provide at least one ticker")
        if len(v) > 20:
            raise ValueError("Maximum 20 tickers per batch request")
        # Clean and validate tickers
        cleaned = []
        for t in v:
            t = t.upper().strip()
            if not t:
                continue
            cleaned.append(t)
        if len(cleaned) == 0:
            raise ValueError("Must provide at least one valid ticker")
        return cleaned

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v):
        allowed = ("ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion")
        if v not in allowed:
            raise ValueError(f"Strategy must be one of: {', '.join(allowed)}")
        return v

    @field_validator("position_sizing")
    @classmethod
    def validate_sizing(cls, v):
        if v not in ("equal_weight", "risk_parity", "volatility_weighted"):
            raise ValueError("Invalid position sizing method")
        return v



class PortfolioStrategy(BaseModel):
    """Single strategy in portfolio optimization."""
    backtest_id: str
    ticker: str
    strategy: str


class PortfolioConstraints(BaseModel):
    """Portfolio optimization constraints."""
    max_weight_per_strategy: float = 0.4
    min_weight_per_strategy: float = 0.05
    target_return: Optional[float] = None

    @field_validator("max_weight_per_strategy")
    @classmethod
    def validate_max_weight(cls, v):
        if not 0.0 < v <= 1.0:
            raise ValueError("max_weight_per_strategy must be between 0 and 1")
        return v

    @field_validator("min_weight_per_strategy")
    @classmethod
    def validate_min_weight(cls, v):
        if not 0.0 <= v < 1.0:
            raise ValueError("min_weight_per_strategy must be between 0 and 1")
        return v


class PortfolioOptimizeRequest(BaseModel):
    """Request to optimize portfolio weights."""
    strategies: list[PortfolioStrategy]
    method: str = "max_sharpe"
    constraints: Optional[PortfolioConstraints] = None

    @field_validator("strategies")
    @classmethod
    def validate_strategies(cls, v):
        if len(v) < 1:
            raise ValueError("Must provide at least 1 strategy")
        if len(v) > 20:
            raise ValueError("Maximum 20 strategies per portfolio")
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v):
        allowed = ("max_sharpe", "min_variance", "equal_weight", "risk_parity")
        if v not in allowed:
            raise ValueError(f"Method must be one of: {', '.join(allowed)}")
        return v

