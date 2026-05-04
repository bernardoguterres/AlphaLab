"""Strategy Export Schema v1.0 - Pydantic Models

Single source of truth for strategy configuration exchange between
AlphaLab (backtesting) and AlphaLive (live execution).

All models use Pydantic v2 with strict validation.
"""

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# Import migration utilities (if migrations package exists)
try:
    from migrations.schema_migrations import migrate_schema
    _MIGRATIONS_AVAILABLE = True
except ImportError:
    _MIGRATIONS_AVAILABLE = False


# ============================================================================
# Strategy Parameters (Per-Strategy)
# ============================================================================


class MACrossoverParams(BaseModel):
    """Moving Average Crossover strategy parameters."""

    short_window: int = Field(ge=2, le=500, description="Short MA period")
    long_window: int = Field(ge=3, le=500, description="Long MA period")
    volume_confirmation: bool = Field(description="Require volume > avg")
    volume_avg_period: int = Field(
        default=20, ge=5, le=100, description="Volume MA period"
    )
    min_separation_pct: float = Field(
        default=0.0, ge=0.0, le=10.0, description="Min % separation before cross"
    )
    cooldown_days: int = Field(
        default=5, ge=0, le=100, description="Min days between signals"
    )

    @model_validator(mode="after")
    def validate_windows(self):
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be < long_window")
        return self


class RSIMeanReversionParams(BaseModel):
    """RSI Mean Reversion strategy parameters."""

    rsi_period: int = Field(ge=2, le=100, description="RSI calculation period")
    oversold: int = Field(ge=1, le=49, description="RSI buy threshold")
    overbought: int = Field(ge=51, le=99, description="RSI sell threshold")
    use_bb_confirmation: bool = Field(description="Require price near BB")
    bb_period: int = Field(
        default=20, ge=5, le=100, description="Bollinger Band period"
    )
    bb_std: float = Field(
        default=2.0, ge=1.0, le=4.0, description="BB standard deviations"
    )
    use_adx_filter: bool = Field(
        default=False, description="Filter choppy markets"
    )
    adx_threshold: int = Field(
        default=25, ge=10, le=50, description="Min ADX for signal"
    )
    stop_loss_atr_mult: float = Field(
        ge=0.5, le=10.0, description="Stop-loss distance (× ATR)"
    )
    max_holding_days: int = Field(
        ge=1, le=365, description="Max position holding period"
    )

    @model_validator(mode="after")
    def validate_rsi_thresholds(self):
        if self.oversold >= self.overbought:
            raise ValueError("oversold must be < overbought")
        return self


class MomentumBreakoutParams(BaseModel):
    """Momentum Breakout strategy parameters."""

    lookback: int = Field(ge=5, le=200, description="Breakout lookback period")
    volume_surge_pct: int = Field(
        ge=100, le=1000, description="Required volume surge (% of avg)"
    )
    rsi_min: int = Field(ge=30, le=80, description="Min RSI for confirmation")
    stop_loss_atr_mult: float = Field(
        ge=0.5, le=10.0, description="Initial stop-loss (× ATR)"
    )
    trailing_stop_atr_mult: float = Field(
        ge=0.5, le=10.0, description="Trailing stop distance (× ATR)"
    )
    cooldown_days: int = Field(
        default=3, ge=0, le=100, description="Min days between signals"
    )


class BollingerBreakoutParams(BaseModel):
    """Bollinger Breakout strategy parameters."""

    bb_period: int = Field(ge=5, le=100, description="Bollinger Band period")
    bb_std_dev: float = Field(ge=0.5, le=4.0, description="BB standard deviations")
    confirmation_bars: int = Field(ge=1, le=5, description="Consecutive closes required")
    volume_filter: bool = Field(description="Enable volume confirmation")
    volume_threshold: float = Field(
        default=1.5, ge=1.0, le=5.0, description="Volume threshold multiplier"
    )
    cooldown_days: int = Field(
        default=3, ge=0, le=100, description="Min days between signals"
    )


class VWAPReversionParams(BaseModel):
    """VWAP Reversion strategy parameters."""

    vwap_period: int = Field(ge=5, le=50, description="Rolling VWAP period")
    deviation_threshold: float = Field(
        ge=0.5, le=5.0, description="Deviation from VWAP (std dev)"
    )
    rsi_period: int = Field(ge=5, le=30, description="RSI calculation period")
    oversold: int = Field(ge=10, le=40, description="RSI oversold threshold")
    overbought: int = Field(ge=60, le=90, description="RSI overbought threshold")
    cooldown_days: int = Field(
        default=3, ge=0, le=100, description="Min days between signals"
    )

    @model_validator(mode="after")
    def validate_rsi_thresholds(self):
        if self.oversold >= self.overbought:
            raise ValueError("oversold must be < overbought")
        return self


# ============================================================================
# Strategy Configuration Block
# ============================================================================


class GreenblattWeeklyParams(BaseModel):
    """Greenblatt Weekly strategy parameters. Designed for weekly bars."""

    fast_sma: int = Field(default=10, ge=2, le=50, description="Fast SMA period (weeks)")
    slow_sma: int = Field(default=50, ge=5, le=200, description="Slow SMA period (weeks)")
    rsi_period: int = Field(default=14, ge=2, le=50, description="RSI period (weeks)")
    rsi_oversold: int = Field(default=35, ge=10, le=49, description="RSI entry threshold")
    rsi_overbought: int = Field(default=65, ge=51, le=90, description="RSI exit threshold")
    min_hold_bars: int = Field(default=12, ge=1, le=104, description="Minimum hold in bars (weeks)")
    stop_loss_atr_mult: float = Field(default=2.0, ge=0.5, le=10.0, description="Stop-loss distance (× weekly ATR)")

    @model_validator(mode="after")
    def validate_sma_and_rsi(self):
        if self.fast_sma >= self.slow_sma:
            raise ValueError("fast_sma must be < slow_sma")
        if self.rsi_oversold >= self.rsi_overbought:
            raise ValueError("rsi_oversold must be < rsi_overbought")
        return self


StrategyName = Literal[
    "ma_crossover",
    "rsi_mean_reversion",
    "momentum_breakout",
    "bollinger_breakout",
    "vwap_reversion",
    "greenblatt_weekly",
]

StrategyParamsUnion = Union[
    MACrossoverParams,
    RSIMeanReversionParams,
    MomentumBreakoutParams,
    BollingerBreakoutParams,
    VWAPReversionParams,
    GreenblattWeeklyParams,
]


class StrategyConfig(BaseModel):
    """Strategy configuration block."""

    name: StrategyName = Field(description="Strategy identifier")
    parameters: StrategyParamsUnion = Field(
        description="Strategy-specific parameters"
    )
    description: str | None = Field(
        default=None, max_length=500, description="Human-readable summary"
    )


# ============================================================================
# Risk, Execution, Safety Limits
# ============================================================================


class RiskConfig(BaseModel):
    """Risk management parameters. All percentages are absolute (e.g., 2.0 = 2%)."""

    stop_loss_pct: float = Field(
        ge=0.1, le=50.0, description="Max loss per position (%)"
    )
    take_profit_pct: float = Field(
        ge=0.1, le=200.0, description="Profit target per position (%)"
    )
    max_position_size_pct: float = Field(
        ge=1.0, le=100.0, description="Max % of portfolio per position"
    )
    max_daily_loss_pct: float = Field(
        ge=0.1, le=50.0, description="Max portfolio loss per day (%)"
    )
    max_open_positions: int = Field(
        ge=1, le=50, description="Max concurrent positions per ticker"
    )
    portfolio_max_positions: int = Field(
        ge=1, le=100, description="Max total concurrent positions"
    )
    trailing_stop_enabled: bool = Field(description="Enable trailing stop-loss")
    trailing_stop_pct: float = Field(
        ge=0.0, le=50.0, description="Trailing stop distance (%)"
    )
    commission_per_trade: float = Field(
        ge=0.0, le=100.0, description="Broker commission per trade (USD)"
    )

    @model_validator(mode="after")
    def validate_trailing_stop(self):
        if self.trailing_stop_enabled and self.trailing_stop_pct < 0.1:
            raise ValueError("trailing_stop_pct must be >= 0.1 if trailing_stop_enabled=True")
        return self


class ExecutionConfig(BaseModel):
    """Order execution settings."""

    order_type: Literal["market", "limit"] = Field(description="Order execution type")
    limit_offset_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="Offset from current price (%) for limit orders",
    )
    cooldown_bars: int = Field(
        ge=0, le=100, description="Min bars between signals for same ticker"
    )

    @model_validator(mode="after")
    def validate_limit_offset(self):
        if self.order_type == "limit" and self.limit_offset_pct <= 0.0:
            raise ValueError("limit_offset_pct required if order_type='limit'")
        return self


class SafetyLimitsConfig(BaseModel):
    """Safety limits for stopping conditions. All fields optional with sensible defaults."""

    max_trades_per_day: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Max trades per day (exceeded → auto-pause)",
    )
    max_api_calls_per_hour: int = Field(
        default=500,
        ge=10,
        le=10000,
        description="Max broker API calls/hour (80% → WARNING, 100% → pause)",
    )
    signal_generation_timeout_seconds: float = Field(
        default=5.0,
        ge=0.1,
        le=60.0,
        description="Max time for signal generation (exceeded → skip signal)",
    )
    broker_degraded_mode_threshold_failures: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Consecutive API failures before degraded mode",
    )


# ============================================================================
# Metadata
# ============================================================================


class BacktestPeriod(BaseModel):
    """Backtest date range."""

    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)")


class PerformanceMetrics(BaseModel):
    """Backtest performance metrics."""

    sharpe_ratio: float = Field(ge=-10.0, le=10.0, description="Risk-adjusted return")
    sortino_ratio: float = Field(ge=-10.0, le=10.0, description="Downside risk-adjusted return")
    total_return_pct: float = Field(
        ge=-100.0, le=10000.0, description="Total backtest return (%)"
    )
    max_drawdown_pct: float = Field(
        ge=-100.0, le=0.0, description="Maximum drawdown (negative value)"
    )
    win_rate_pct: float = Field(ge=0.0, le=100.0, description="% of winning trades")
    profit_factor: float = Field(
        ge=0.0, le=100.0, description="Gross profit / gross loss"
    )
    total_trades: int = Field(ge=0, le=100000, description="Total number of trades")
    calmar_ratio: float = Field(
        ge=-10.0, le=10.0, description="CAGR / max drawdown"
    )


class MetadataConfig(BaseModel):
    """Backtest provenance and performance."""

    exported_from: Literal["AlphaLab"] = Field(description="Export source")
    exported_at: datetime = Field(description="Export timestamp (ISO 8601 UTC)")
    alphalab_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$", description="AlphaLab version (e.g., 0.2.0)"
    )
    backtest_id: str = Field(description="Unique backtest identifier")
    backtest_period: BacktestPeriod
    performance: PerformanceMetrics


# ============================================================================
# Root Schema
# ============================================================================


class StrategyExportSchema(BaseModel):
    """Root schema for strategy export (AlphaLab → AlphaLive).

    This is the single source of truth for the JSON format.
    Version 1.0 (2026-03-08).
    """

    schema_version: Literal["1.0"] = Field(description="Schema version")
    strategy: StrategyConfig
    ticker: str = Field(
        min_length=1, max_length=10, description="Primary ticker symbol"
    )
    timeframe: Literal["1Day", "1Hour", "15Min"] = Field(description="Trading timeframe")
    risk: RiskConfig
    execution: ExecutionConfig
    safety_limits: SafetyLimitsConfig = Field(
        default_factory=SafetyLimitsConfig,
        description="Optional safety limits (defaults applied if missing)",
    )
    metadata: MetadataConfig

    @model_validator(mode="after")
    def validate_timeframe_compatibility(self):
        """VWAP strategies require intraday timeframes."""
        if (
            self.strategy.name == "vwap_reversion"
            and self.timeframe == "1Day"
        ):
            raise ValueError("VWAP strategies require intraday timeframe (1Hour or 15Min)")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "1.0",
                    "strategy": {
                        "name": "ma_crossover",
                        "parameters": {
                            "short_window": 50,
                            "long_window": 200,
                            "volume_confirmation": True,
                            "cooldown_days": 5,
                        },
                        "description": "Golden Cross strategy for SPY",
                    },
                    "ticker": "SPY",
                    "timeframe": "1Day",
                    "risk": {
                        "stop_loss_pct": 3.0,
                        "take_profit_pct": 10.0,
                        "max_position_size_pct": 25.0,
                        "max_daily_loss_pct": 5.0,
                        "max_open_positions": 1,
                        "portfolio_max_positions": 5,
                        "trailing_stop_enabled": False,
                        "trailing_stop_pct": 0.0,
                        "commission_per_trade": 0.0,
                    },
                    "execution": {
                        "order_type": "market",
                        "limit_offset_pct": 0.0,
                        "cooldown_bars": 5,
                    },
                    "safety_limits": {
                        "max_trades_per_day": 20,
                        "max_api_calls_per_hour": 500,
                        "signal_generation_timeout_seconds": 5.0,
                        "broker_degraded_mode_threshold_failures": 3,
                    },
                    "metadata": {
                        "exported_from": "AlphaLab",
                        "exported_at": "2026-03-08T14:30:00Z",
                        "alphalab_version": "0.2.0",
                        "backtest_id": "bt_spy_ma_20260308",
                        "backtest_period": {
                            "start": "2020-01-01",
                            "end": "2024-12-31",
                        },
                        "performance": {
                            "sharpe_ratio": 1.23,
                            "sortino_ratio": 1.65,
                            "total_return_pct": 28.4,
                            "max_drawdown_pct": -11.2,
                            "win_rate_pct": 54.5,
                            "profit_factor": 1.52,
                            "total_trades": 22,
                            "calmar_ratio": 2.54,
                        },
                    },
                }
            ]
        }
    }


# ============================================================================
# Utility Functions
# ============================================================================


def validate_strategy_export(data: dict, auto_migrate: bool = True) -> StrategyExportSchema:
    """Validate and parse strategy export JSON with optional migration.

    Args:
        data: Dictionary from JSON deserialization
        auto_migrate: If True, apply schema migrations before validation (default: True)

    Returns:
        Validated StrategyExportSchema instance

    Raises:
        pydantic.ValidationError: If validation fails
        ValueError: If schema version is unsupported
    """
    # Apply migrations if enabled and available
    if auto_migrate and _MIGRATIONS_AVAILABLE:
        data = migrate_schema(data)

    return StrategyExportSchema.model_validate(data)


def export_strategy_to_json(schema: StrategyExportSchema) -> str:
    """Export StrategyExportSchema to JSON string.

    Args:
        schema: Validated schema instance

    Returns:
        JSON string (indented, sorted keys)
    """
    return schema.model_dump_json(indent=2, exclude_none=True)
