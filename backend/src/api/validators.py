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


class BacktestRequest(BaseModel):
    ticker: str
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float = 100_000
    params: Optional[dict] = None
    position_sizing: str = "equal_weight"
    monte_carlo_runs: int = 0

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v):
        allowed = ("ma_crossover", "rsi_mean_reversion", "momentum_breakout")
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
