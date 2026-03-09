# Strategy Export Schema v1.0

**Single Source of Truth** for strategy configuration exchange between AlphaLab (backtesting) and AlphaLive (live execution).

## Table of Contents
- [Overview](#overview)
- [Schema Version](#schema-version)
- [Full Schema](#full-schema)
- [Field Reference](#field-reference)
- [Per-Strategy Parameters](#per-strategy-parameters)
- [Safety Limits (New in v1.0)](#safety-limits-new-in-v10)
- [Validation Rules](#validation-rules)
- [Examples](#examples)
- [Versioning Policy](#versioning-policy)
- [Adding New Strategies](#adding-new-strategies)

---

## Overview

This schema defines the JSON contract for exporting battle-tested strategies from AlphaLab to AlphaLive for live execution. It ensures:

1. **Type safety** — Pydantic (backend) and TypeScript (frontend) enforce validation
2. **Traceability** — Metadata links live strategies to backtest results
3. **Risk control** — Standardized risk parameters prevent over-leveraging
4. **Safety** — Configurable stopping conditions protect against runaway signals

## Schema Version

**Current Version:** `1.0`

Version changes:
- **1.0** (2026-03-08) — Initial release with 5 strategies, safety_limits block

---

## Full Schema

```json
{
  "schema_version": "1.0",
  "strategy": {
    "name": "ma_crossover | rsi_mean_reversion | momentum_breakout | bollinger_breakout | vwap_reversion",
    "parameters": { /* strategy-specific params */ },
    "description": "Human-readable summary (optional)"
  },
  "ticker": "AAPL",
  "timeframe": "1Day | 1Hour | 15Min",
  "risk": {
    "stop_loss_pct": 2.0,
    "take_profit_pct": 5.0,
    "max_position_size_pct": 10.0,
    "max_daily_loss_pct": 3.0,
    "max_open_positions": 5,
    "portfolio_max_positions": 10,
    "trailing_stop_enabled": false,
    "trailing_stop_pct": 3.0,
    "commission_per_trade": 0.0
  },
  "execution": {
    "order_type": "market | limit",
    "limit_offset_pct": 0.1,
    "cooldown_bars": 1
  },
  "safety_limits": {
    "max_trades_per_day": 20,
    "max_api_calls_per_hour": 500,
    "signal_generation_timeout_seconds": 5.0,
    "broker_degraded_mode_threshold_failures": 3
  },
  "metadata": {
    "exported_from": "AlphaLab",
    "exported_at": "2026-03-05T12:00:00Z",
    "alphalab_version": "0.2.0",
    "backtest_id": "bt_abc123",
    "backtest_period": {
      "start": "2020-01-01",
      "end": "2024-12-31"
    },
    "performance": {
      "sharpe_ratio": 1.45,
      "sortino_ratio": 1.82,
      "total_return_pct": 32.5,
      "max_drawdown_pct": -12.3,
      "win_rate_pct": 58.2,
      "profit_factor": 1.75,
      "total_trades": 47,
      "calmar_ratio": 2.64
    }
  }
}
```

---

## Field Reference

### Root Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | `string` | ✅ Yes | Schema version (currently "1.0") |
| `strategy` | `object` | ✅ Yes | Strategy configuration block |
| `ticker` | `string` | ✅ Yes | Primary ticker symbol (e.g., "AAPL", "SPY") |
| `timeframe` | `string` | ✅ Yes | One of: "1Day", "1Hour", "15Min" |
| `risk` | `object` | ✅ Yes | Risk management parameters |
| `execution` | `object` | ✅ Yes | Order execution settings |
| `safety_limits` | `object` | ⚪ Optional | Stopping conditions (defaults applied if missing) |
| `metadata` | `object` | ✅ Yes | Backtest provenance and performance |

### Strategy Block

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `name` | `string` | ✅ Yes | "ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion" | Strategy identifier |
| `parameters` | `object` | ✅ Yes | See [Per-Strategy Parameters](#per-strategy-parameters) | Strategy-specific config |
| `description` | `string` | ⚪ Optional | Any string | Human-readable summary (max 500 chars) |

### Risk Block

All percentages are in **absolute percent** (e.g., 2.0 = 2%, not 0.02).

| Field | Type | Required | Range | Default | Description |
|-------|------|----------|-------|---------|-------------|
| `stop_loss_pct` | `float` | ✅ Yes | 0.1 - 50.0 | — | Max loss per position (% of entry price) |
| `take_profit_pct` | `float` | ✅ Yes | 0.1 - 200.0 | — | Profit target per position (% of entry price) |
| `max_position_size_pct` | `float` | ✅ Yes | 1.0 - 100.0 | — | Max % of portfolio per position |
| `max_daily_loss_pct` | `float` | ✅ Yes | 0.1 - 50.0 | — | Max portfolio loss per day (halts trading if exceeded) |
| `max_open_positions` | `int` | ✅ Yes | 1 - 50 | — | Max concurrent positions per ticker |
| `portfolio_max_positions` | `int` | ✅ Yes | 1 - 100 | — | Max total concurrent positions across all tickers |
| `trailing_stop_enabled` | `bool` | ✅ Yes | true/false | — | Enable trailing stop-loss |
| `trailing_stop_pct` | `float` | ⚪ Conditional | 0.1 - 50.0 | — | Trailing stop distance (required if enabled=true) |
| `commission_per_trade` | `float` | ✅ Yes | 0.0 - 100.0 | — | Broker commission per trade (USD) |

### Execution Block

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `order_type` | `string` | ✅ Yes | "market", "limit" | Order execution type |
| `limit_offset_pct` | `float` | ⚪ Conditional | 0.0 - 5.0 | Required if order_type="limit". Offset from current price (%) |
| `cooldown_bars` | `int` | ✅ Yes | 0 - 100 | Minimum bars between signals for same ticker |

### Safety Limits Block

**NEW in v1.0** — Optional block with sensible defaults. Prevents runaway strategies.

| Field | Type | Required | Range | Default | Description |
|-------|------|----------|-------|---------|-------------|
| `max_trades_per_day` | `int` | ⚪ Optional | 1 - 1000 | 20 | Max trades per day. Exceeded → auto-pause + CRITICAL alert |
| `max_api_calls_per_hour` | `int` | ⚪ Optional | 10 - 10000 | 500 | Max broker API calls/hour. 80% → WARNING, 100% → auto-pause |
| `signal_generation_timeout_seconds` | `float` | ⚪ Optional | 0.1 - 60.0 | 5.0 | Max time for strategy signal generation. Exceeded → skip signal + WARNING |
| `broker_degraded_mode_threshold_failures` | `int` | ⚪ Optional | 1 - 10 | 3 | Consecutive broker API failures before degraded mode (cached positions, no new entries) |

**Backward Compatibility:** If `safety_limits` block is missing, defaults are applied automatically.

### Metadata Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `exported_from` | `string` | ✅ Yes | Always "AlphaLab" |
| `exported_at` | `string` | ✅ Yes | ISO 8601 timestamp (UTC) |
| `alphalab_version` | `string` | ✅ Yes | AlphaLab version (e.g., "0.2.0") |
| `backtest_id` | `string` | ✅ Yes | Unique backtest identifier |
| `backtest_period.start` | `string` | ✅ Yes | Backtest start date (YYYY-MM-DD) |
| `backtest_period.end` | `string` | ✅ Yes | Backtest end date (YYYY-MM-DD) |
| `performance.*` | `float` | ✅ Yes | Backtest metrics (see table below) |

#### Performance Metrics

All required fields in `metadata.performance`:

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `sharpe_ratio` | `float` | -10.0 to 10.0 | Risk-adjusted return (annualized) |
| `sortino_ratio` | `float` | -10.0 to 10.0 | Downside risk-adjusted return |
| `total_return_pct` | `float` | -100.0 to 10000.0 | Total backtest return (%) |
| `max_drawdown_pct` | `float` | -100.0 to 0.0 | Maximum drawdown (negative value) |
| `win_rate_pct` | `float` | 0.0 to 100.0 | Percentage of winning trades |
| `profit_factor` | `float` | 0.0 to 100.0 | Gross profit / gross loss |
| `total_trades` | `int` | 0 to 100000 | Total number of trades |
| `calmar_ratio` | `float` | -10.0 to 10.0 | CAGR / max drawdown |

---

## Per-Strategy Parameters

### 1. MA Crossover (`ma_crossover`)

**Status:** ✅ Implemented

Classic moving average crossover with volume confirmation.

```json
{
  "short_window": 50,
  "long_window": 200,
  "volume_confirmation": true,
  "volume_avg_period": 20,
  "min_separation_pct": 0.0,
  "cooldown_days": 5
}
```

| Parameter | Type | Required | Range | Default | Description |
|-----------|------|----------|-------|---------|-------------|
| `short_window` | `int` | ✅ Yes | 2 - 500 | 50 | Short MA period (bars) |
| `long_window` | `int` | ✅ Yes | 3 - 500 | 200 | Long MA period (bars). Must be > short_window |
| `volume_confirmation` | `bool` | ✅ Yes | true/false | true | Require volume > avg for signal |
| `volume_avg_period` | `int` | ⚪ Optional | 5 - 100 | 20 | Volume moving average period |
| `min_separation_pct` | `float` | ⚪ Optional | 0.0 - 10.0 | 0.0 | Min % separation before cross (anti-whipsaw) |
| `cooldown_days` | `int` | ⚪ Optional | 0 - 100 | 5 | Min days between signals |

---

### 2. RSI Mean Reversion (`rsi_mean_reversion`)

**Status:** ✅ Implemented

State-aware mean reversion with Bollinger Band confirmation and stop-loss.

```json
{
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "use_bb_confirmation": true,
  "bb_period": 20,
  "bb_std": 2.0,
  "use_adx_filter": false,
  "adx_threshold": 25,
  "stop_loss_atr_mult": 2.5,
  "max_holding_days": 40
}
```

| Parameter | Type | Required | Range | Default | Description |
|-----------|------|----------|-------|---------|-------------|
| `rsi_period` | `int` | ✅ Yes | 2 - 100 | 14 | RSI calculation period |
| `oversold` | `int` | ✅ Yes | 1 - 49 | 30 | RSI buy threshold |
| `overbought` | `int` | ✅ Yes | 51 - 99 | 70 | RSI sell threshold |
| `use_bb_confirmation` | `bool` | ✅ Yes | true/false | true | Require price near BB for entry |
| `bb_period` | `int` | ⚪ Optional | 5 - 100 | 20 | Bollinger Band period |
| `bb_std` | `float` | ⚪ Optional | 1.0 - 4.0 | 2.0 | Bollinger Band standard deviations |
| `use_adx_filter` | `bool` | ⚪ Optional | true/false | false | Filter low-ADX (choppy) markets |
| `adx_threshold` | `int` | ⚪ Optional | 10 - 50 | 25 | Min ADX for signal (if filter enabled) |
| `stop_loss_atr_mult` | `float` | ✅ Yes | 0.5 - 10.0 | 2.5 | Stop-loss distance (× ATR) |
| `max_holding_days` | `int` | ✅ Yes | 1 - 365 | 40 | Max position holding period |

---

### 3. Momentum Breakout (`momentum_breakout`)

**Status:** ✅ Implemented

Breakout strategy with trailing stop and volume surge confirmation.

```json
{
  "lookback": 20,
  "volume_surge_pct": 150,
  "rsi_min": 50,
  "stop_loss_atr_mult": 2.0,
  "trailing_stop_atr_mult": 3.0,
  "cooldown_days": 3
}
```

| Parameter | Type | Required | Range | Default | Description |
|-----------|------|----------|-------|---------|-------------|
| `lookback` | `int` | ✅ Yes | 5 - 200 | 20 | Breakout lookback period (bars) |
| `volume_surge_pct` | `int` | ✅ Yes | 100 - 1000 | 150 | Required volume surge (% of avg) |
| `rsi_min` | `int` | ✅ Yes | 30 - 80 | 50 | Min RSI for breakout confirmation |
| `stop_loss_atr_mult` | `float` | ✅ Yes | 0.5 - 10.0 | 2.0 | Initial stop-loss (× ATR) |
| `trailing_stop_atr_mult` | `float` | ✅ Yes | 0.5 - 10.0 | 3.0 | Trailing stop distance (× ATR) |
| `cooldown_days` | `int` | ⚪ Optional | 0 - 100 | 3 | Min days between signals |

---

### 4. Bollinger Breakout (`bollinger_breakout`)

**Status:** 🔄 Planned (not yet implemented in AlphaLab)

Trades breakouts above/below Bollinger Bands with volume confirmation.

```json
{
  "bb_period": 20,
  "bb_std": 2.0,
  "volume_surge_pct": 150,
  "rsi_min": 50,
  "rsi_max": 80,
  "stop_loss_atr_mult": 2.0,
  "take_profit_atr_mult": 4.0,
  "cooldown_days": 3
}
```

| Parameter | Type | Required | Range | Default | Description |
|-----------|------|----------|-------|---------|-------------|
| `bb_period` | `int` | ✅ Yes | 5 - 100 | 20 | Bollinger Band period |
| `bb_std` | `float` | ✅ Yes | 1.0 - 4.0 | 2.0 | Standard deviations for bands |
| `volume_surge_pct` | `int` | ✅ Yes | 100 - 1000 | 150 | Volume surge threshold (%) |
| `rsi_min` | `int` | ✅ Yes | 30 - 70 | 50 | Min RSI for long breakout |
| `rsi_max` | `int` | ✅ Yes | 50 - 90 | 80 | Max RSI for long breakout |
| `stop_loss_atr_mult` | `float` | ✅ Yes | 0.5 - 10.0 | 2.0 | Stop-loss distance (× ATR) |
| `take_profit_atr_mult` | `float` | ✅ Yes | 1.0 - 20.0 | 4.0 | Take profit target (× ATR) |
| `cooldown_days` | `int` | ⚪ Optional | 0 - 100 | 3 | Min days between signals |

---

### 5. VWAP Reversion (`vwap_reversion`)

**Status:** 🔄 Planned (not yet implemented in AlphaLab)

Mean reversion based on deviations from VWAP (Volume Weighted Average Price).

```json
{
  "vwap_period": "daily",
  "deviation_threshold": 1.5,
  "volume_min_pct": 80,
  "rsi_oversold": 30,
  "rsi_overbought": 70,
  "stop_loss_pct": 2.0,
  "take_profit_pct": 3.0,
  "max_holding_hours": 24
}
```

| Parameter | Type | Required | Range | Default | Description |
|-----------|------|----------|-------|---------|-------------|
| `vwap_period` | `string` | ✅ Yes | "daily", "weekly", "intraday" | "daily" | VWAP reset period |
| `deviation_threshold` | `float` | ✅ Yes | 0.5 - 5.0 | 1.5 | Min deviation from VWAP (std dev) |
| `volume_min_pct` | `int` | ✅ Yes | 50 - 200 | 80 | Min volume (% of avg) for signal |
| `rsi_oversold` | `int` | ✅ Yes | 10 - 40 | 30 | RSI oversold threshold |
| `rsi_overbought` | `int` | ✅ Yes | 60 - 90 | 70 | RSI overbought threshold |
| `stop_loss_pct` | `float` | ✅ Yes | 0.5 - 10.0 | 2.0 | Stop-loss (% of entry) |
| `take_profit_pct` | `float` | ✅ Yes | 0.5 - 20.0 | 3.0 | Take profit (% of entry) |
| `max_holding_hours` | `int` | ✅ Yes | 1 - 168 | 24 | Max position holding time (hours) |

---

## Safety Limits (New in v1.0)

The `safety_limits` block provides **per-strategy customization** of stopping conditions that protect against:

1. **Signal bugs** — Runaway loops generating thousands of trades
2. **API rate limits** — Broker throttling/bans from excessive calls
3. **Performance degradation** — Slow signal generation blocking main loop
4. **Broker outages** — Extended API failures

### Behavior

| Limit | Trigger Condition | Action Taken |
|-------|-------------------|--------------|
| `max_trades_per_day` | Trades today ≥ limit | CRITICAL alert + Telegram notification + auto-pause trading |
| `max_api_calls_per_hour` | Calls ≥ 80% limit | WARNING logged<br>Calls ≥ 100% limit → auto-pause + CRITICAL alert |
| `signal_generation_timeout_seconds` | `generate_signal()` runtime > limit | Skip signal + WARNING log (no pause) |
| `broker_degraded_mode_threshold_failures` | Consecutive API failures ≥ limit | Enter degraded mode (cached positions, no new entries) + WARNING |

### Example: Aggressive Scalper

```json
"safety_limits": {
  "max_trades_per_day": 100,
  "max_api_calls_per_hour": 1000,
  "signal_generation_timeout_seconds": 2.0,
  "broker_degraded_mode_threshold_failures": 5
}
```

### Example: Conservative Swing Trader

```json
"safety_limits": {
  "max_trades_per_day": 5,
  "max_api_calls_per_hour": 200,
  "signal_generation_timeout_seconds": 10.0,
  "broker_degraded_mode_threshold_failures": 2
}
```

### Defaults (if block missing)

```json
"safety_limits": {
  "max_trades_per_day": 20,
  "max_api_calls_per_hour": 500,
  "signal_generation_timeout_seconds": 5.0,
  "broker_degraded_mode_threshold_failures": 3
}
```

---

## Validation Rules

### Cross-Field Validation

1. **Strategy parameters** — Must match strategy type (validated by Pydantic union discriminator)
2. **Trailing stop** — If `trailing_stop_enabled=true`, `trailing_stop_pct` is required
3. **Limit orders** — If `order_type="limit"`, `limit_offset_pct` is required
4. **MA windows** — `short_window < long_window` (for ma_crossover)
5. **RSI thresholds** — `oversold < overbought` (for rsi_mean_reversion)
6. **Timeframe compatibility** — VWAP strategies require intraday timeframes (1Hour or 15Min)

### Data Integrity

- All percentages are **positive absolute values** (e.g., 2.0 = 2%, not 0.02)
- `max_drawdown_pct` is **negative** (e.g., -12.3 for 12.3% drawdown)
- Dates are **YYYY-MM-DD** format
- Timestamps are **ISO 8601 UTC** (e.g., "2026-03-05T12:00:00Z")

---

## Examples

### Example 1: MA Crossover (Conservative)

```json
{
  "schema_version": "1.0",
  "strategy": {
    "name": "ma_crossover",
    "parameters": {
      "short_window": 50,
      "long_window": 200,
      "volume_confirmation": true,
      "cooldown_days": 5
    },
    "description": "Golden Cross / Death Cross strategy for SPY"
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
    "trailing_stop_enabled": false,
    "trailing_stop_pct": 0.0,
    "commission_per_trade": 0.0
  },
  "execution": {
    "order_type": "market",
    "limit_offset_pct": 0.0,
    "cooldown_bars": 5
  },
  "safety_limits": {
    "max_trades_per_day": 3,
    "max_api_calls_per_hour": 200
  },
  "metadata": {
    "exported_from": "AlphaLab",
    "exported_at": "2026-03-08T14:30:00Z",
    "alphalab_version": "0.2.0",
    "backtest_id": "bt_spy_ma_20260308",
    "backtest_period": {
      "start": "2020-01-01",
      "end": "2024-12-31"
    },
    "performance": {
      "sharpe_ratio": 1.23,
      "sortino_ratio": 1.65,
      "total_return_pct": 28.4,
      "max_drawdown_pct": -11.2,
      "win_rate_pct": 54.5,
      "profit_factor": 1.52,
      "total_trades": 22,
      "calmar_ratio": 2.54
    }
  }
}
```

### Example 2: RSI Mean Reversion (Aggressive)

```json
{
  "schema_version": "1.0",
  "strategy": {
    "name": "rsi_mean_reversion",
    "parameters": {
      "rsi_period": 14,
      "oversold": 25,
      "overbought": 75,
      "use_bb_confirmation": true,
      "bb_period": 20,
      "bb_std": 2.5,
      "use_adx_filter": true,
      "adx_threshold": 30,
      "stop_loss_atr_mult": 2.0,
      "max_holding_days": 20
    },
    "description": "Tight RSI mean reversion for TSLA"
  },
  "ticker": "TSLA",
  "timeframe": "1Hour",
  "risk": {
    "stop_loss_pct": 2.5,
    "take_profit_pct": 5.0,
    "max_position_size_pct": 15.0,
    "max_daily_loss_pct": 4.0,
    "max_open_positions": 3,
    "portfolio_max_positions": 10,
    "trailing_stop_enabled": true,
    "trailing_stop_pct": 2.0,
    "commission_per_trade": 0.0
  },
  "execution": {
    "order_type": "limit",
    "limit_offset_pct": 0.2,
    "cooldown_bars": 1
  },
  "safety_limits": {
    "max_trades_per_day": 50,
    "max_api_calls_per_hour": 800,
    "signal_generation_timeout_seconds": 3.0,
    "broker_degraded_mode_threshold_failures": 5
  },
  "metadata": {
    "exported_from": "AlphaLab",
    "exported_at": "2026-03-08T14:35:00Z",
    "alphalab_version": "0.2.0",
    "backtest_id": "bt_tsla_rsi_20260308",
    "backtest_period": {
      "start": "2023-01-01",
      "end": "2024-12-31"
    },
    "performance": {
      "sharpe_ratio": 1.87,
      "sortino_ratio": 2.34,
      "total_return_pct": 41.2,
      "max_drawdown_pct": -15.6,
      "win_rate_pct": 62.3,
      "profit_factor": 2.18,
      "total_trades": 89,
      "calmar_ratio": 2.64
    }
  }
}
```

---

## Versioning Policy

### Schema Version Format

`MAJOR.MINOR` (e.g., "1.0", "1.1", "2.0")

### Version Bump Rules

- **MAJOR** — Breaking changes (remove required field, change field type, incompatible validation)
  - Example: Remove `ticker` field, change `timeframe` from string to enum
  - AlphaLive **must reject** schemas with incompatible major version

- **MINOR** — Backward-compatible additions (new optional fields, new strategies, new enum values)
  - Example: Add `safety_limits` block (v1.0 → v1.1), add new strategy "vwap_reversion"
  - AlphaLive **should accept** older minor versions (ignore unknown fields)

### Compatibility Matrix

| AlphaLab Version | Schema Version | AlphaLive Compatibility |
|------------------|----------------|-------------------------|
| 0.2.0 | 1.0 | ✅ Full support |
| 0.3.0 | 1.1 | ✅ Backward compatible (ignores new fields) |
| 1.0.0 | 2.0 | ❌ Breaking changes (AlphaLive upgrade required) |

---

## Adding New Strategies

To add a new strategy to this schema:

### 1. Implement in AlphaLab

- Create strategy class in `backend/src/strategies/implementations/`
- Add default params to `backend/config.yaml`
- Write tests in `backend/tests/test_strategies.py`
- Register in strategy map

### 2. Update Schema Files

**docs/STRATEGY_SCHEMA.md** (this file):
- Add to valid values in `strategy.name` field
- Add parameter table under [Per-Strategy Parameters](#per-strategy-parameters)
- Include status badge (✅ Implemented or 🔄 Planned)

**backend/strategy_schema.py**:
```python
class MyNewStrategyParams(BaseModel):
    param1: int = Field(ge=1, le=100)
    param2: float = Field(ge=0.1, le=10.0)

StrategyParamsUnion = Annotated[
    Union[
        MACrossoverParams,
        RSIMeanReversionParams,
        MomentumBreakoutParams,
        BollingerBreakoutParams,
        VWAPReversionParams,
        MyNewStrategyParams,  # Add here
    ],
    Field(discriminator="strategy_name"),
]
```

**frontend/src/types/strategy_schema.ts**:
```typescript
export type StrategyName =
  | "ma_crossover"
  | "rsi_mean_reversion"
  | "momentum_breakout"
  | "bollinger_breakout"
  | "vwap_reversion"
  | "my_new_strategy";  // Add here

export interface MyNewStrategyParams {
  param1: number;
  param2: number;
}
```

### 3. Update Version

If adding new strategy with new optional fields:
- Bump **MINOR** version (e.g., 1.0 → 1.1)
- Update compatibility matrix
- Add changelog entry

---

## Changelog

### v1.0 (2026-03-08)
- Initial release
- 5 strategies: ma_crossover, rsi_mean_reversion, momentum_breakout, bollinger_breakout, vwap_reversion
- safety_limits block for configurable stopping conditions
- Full Pydantic v2 and TypeScript type definitions

---

## Support

For questions or issues:
- **AlphaLab Issues:** https://github.com/yourusername/alphalab/issues
- **Schema Discussions:** https://github.com/yourusername/alphalab/discussions

**Last Updated:** 2026-03-08
