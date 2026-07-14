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

1. **Type safety** - Pydantic (backend) and TypeScript (frontend) enforce validation
2. **Traceability** - Metadata links live strategies to backtest results
3. **Risk control** - Standardized risk parameters prevent over-leveraging
4. **Safety** - Configurable stopping conditions protect against runaway signals

## Schema Version

**Current Version:** `1.0` (unchanged since initial release - new strategies have been added as backward-compatible additions to the `strategy.name` enum, not schema version bumps)

Version changes:
- **1.0** (2026-03-08) - Initial release with 5 strategies, safety_limits block
- 3 more strategies added since (bollinger_rsi_combo, trend_adaptive_rsi, greenblatt_weekly) - see [Per-Strategy Parameters](#per-strategy-parameters), updated 2026-07

---

## Full Schema

```json
{
  "schema_version": "1.0",
  "strategy": {
    "name": "ma_crossover | rsi_mean_reversion | rsi_simple | momentum_breakout | bollinger_breakout | vwap_reversion | bollinger_rsi_combo | trend_adaptive_rsi | greenblatt_weekly",
    "parameters": { /* strategy-specific params, untyped dict - see note in Adding New Strategies */ },
    "description": "Human-readable summary (optional)"
  },
  "ticker": "AAPL",
  "timeframe": "1Day | 1Hour | 15Min | 1Week",
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
| `schema_version` | `string` | Yes | Schema version (currently "1.0") |
| `strategy` | `object` | Yes | Strategy configuration block |
| `ticker` | `string` | Yes | Primary ticker symbol (e.g., "AAPL", "SPY") |
| `timeframe` | `string` | Yes | One of: "1Day", "1Hour", "15Min", "1Week"|
| `risk` | `object` | Yes | Risk management parameters |
| `execution` | `object` | Yes | Order execution settings |
| `safety_limits` | `object` | Optional | Stopping conditions (defaults applied if missing) |
| `metadata` | `object` | Yes | Backtest provenance and performance |

### Strategy Block

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `name` | `string` | Yes | "ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion", "bollinger_rsi_combo", "trend_adaptive_rsi", "greenblatt_weekly" | Strategy identifier |
| `parameters` | `object` | Yes | See [Per-Strategy Parameters](#per-strategy-parameters) | Strategy-specific config |
| `description` | `string` | Optional | Any string | Human-readable summary (max 500 chars) |

### Risk Block

All percentages are in **absolute percent** (e.g., 2.0 = 2%, not 0.02).

| Field | Type | Required | Range | Default | Description |
|-------|------|----------|-------|---------|-------------|
| `stop_loss_pct` | `float` | Yes | 0.1 - 50.0 | - | Max loss per position (% of entry price) |
| `take_profit_pct` | `float` | Yes | 0.5 - 100.0 | - | Profit target per position (% of entry price) |
| `max_position_size_pct` | `float` | Yes | 1.0 - 100.0 | - | Max % of portfolio per position |
| `max_daily_loss_pct` | `float` | Yes | 0.5 - 20.0 | - | Max portfolio loss per day (halts trading if exceeded) |
| `max_open_positions` | `int` | Yes | 1 - 50 | - | Max concurrent positions per ticker |
| `portfolio_max_positions` | `int` | Yes | 1 - 100 | - | Max total concurrent positions across all tickers |
| `trailing_stop_enabled` | `bool` | Yes | true/false | - | Enable trailing stop-loss |
| `trailing_stop_pct` | `float` | Conditional | 0.5 - 20.0 | - | Trailing stop distance (required if enabled=true) |
| `commission_per_trade` | `float` | Yes | 0.0 - 50.0 | - | Broker commission per trade (USD) |

### Execution Block

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `order_type` | `string` | Yes | "market", "limit"| Order execution type |
| `limit_offset_pct` | `float` | Conditional | 0.0 - 5.0 | Required if order_type="limit". Offset from current price (%) |
| `cooldown_bars` | `int` | Yes | 0 - 100 | Minimum bars between signals for same ticker |

### Safety Limits Block

**NEW in v1.0** - Optional block with sensible defaults. Prevents runaway strategies.

| Field | Type | Required | Range | Default | Description |
|-------|------|----------|-------|---------|-------------|
| `max_trades_per_day` | `int` | Optional | 1 - 1000 | 20 | Max trades per day. Exceeded → auto-pause + CRITICAL alert |
| `max_api_calls_per_hour` | `int` | Optional | 10 - 10000 | 500 | Max broker API calls/hour. 80% → WARNING, 100% → auto-pause |
| `signal_generation_timeout_seconds` | `float` | Optional | 0.1 - 60.0 | 5.0 | Max time for strategy signal generation. Exceeded → skip signal + WARNING |
| `broker_degraded_mode_threshold_failures` | `int` | Optional | 1 - 10 | 3 | Consecutive broker API failures before degraded mode (cached positions, no new entries) |

**Backward Compatibility:** If `safety_limits` block is missing, defaults are applied automatically.

### Metadata Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `exported_from` | `string` | Yes | Always "AlphaLab"|
| `exported_at` | `string` | Yes | ISO 8601 timestamp (UTC) |
| `alphalab_version` | `string` | Yes | AlphaLab version (e.g., "0.2.0") |
| `backtest_id` | `string` | Yes | Unique backtest identifier |
| `backtest_period.start` | `string` | Yes | Backtest start date (YYYY-MM-DD) |
| `backtest_period.end` | `string` | Yes | Backtest end date (YYYY-MM-DD) |
| `performance.*` | `float` | Yes | Backtest metrics (see table below) |

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

All 9 strategies below are implemented and tested in AlphaLab (backtesting). 8 of the 9 are also verified for signal parity with AlphaLive (live signal generation) - `rsi_simple` is the exception, registered 2026-07-14 (audit bug 3.8) as a reachable AlphaLab strategy, but AlphaLive does not currently register a matching `rsi_simple` strategy name, so it cannot yet be deployed end-to-end. AlphaLab's internal strategy classes take their own untyped params dict (see note in [Adding New Strategies](#adding-new-strategies)), with defaults applied via `setdefault()` in each strategy's `validate_params()`. **The JSON shown in this section is the exported/wire format** - what actually appears in `strategy.parameters` after `POST /api/strategies/export`, which is not always identical to AlphaLab's internal field names. Every `parameters` block also carries a `strategy_type` field matching `strategy.name` (a discriminator added 2026-07-14 - see [Versioning Policy](#versioning-policy)); omitted from the examples below for brevity but present in every real export.

**Export field-name translation (2026-07-14):** four strategies have internal AlphaLab field names that differ from what AlphaLive actually reads; `_build_export_json`'s export-mapping layer (`backend/src/api/helpers.py`) renames them automatically - you never need to do this by hand when exporting through the API, but if you hand-craft a config JSON for AlphaLive, use the exported names below, not AlphaLab's internal ones (`short_window`/`long_window`, `volume_surge_pct`/`volume_avg_period`, `bb_period`/`bb_std_dev`, greenblatt's own `trailing_stop_pct`).

### 1. MA Crossover (`ma_crossover`)

Classic moving average crossover with volume confirmation.

```json
{
  "fast_period": 50,
  "slow_period": 200,
  "volume_confirmation": true,
  "volume_avg_period": 20,
  "min_separation_pct": 0.0,
  "cooldown_days": 5
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fast_period` | 50 | Short MA period (bars); must be < `slow_period`. AlphaLab's internal class calls this `short_window` - renamed at export to match AlphaLive's `signal_engine.py`. |
| `slow_period` | 200 | Long MA period (bars). Internal name: `long_window`. |
| `volume_confirmation` | true | Require volume > avg for signal |
| `volume_avg_period` | 20 | Volume moving average period |
| `min_separation_pct` | 0.0 | Min % separation before cross (anti-whipsaw) |
| `cooldown_days` | 5 | Min days between signals |

---

### 2. RSI Mean Reversion (`rsi_mean_reversion`)

State-aware mean reversion with optional Bollinger Band/ADX confirmation and ATR-based stop-loss.

```json
{
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "use_bb_confirmation": true,
  "use_adx_filter": false,
  "adx_threshold": 25,
  "cooldown_days": 3,
  "stop_loss_atr_mult": 2.5,
  "max_holding_days": 40
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rsi_period` | 14 | RSI calculation period |
| `oversold` | 30 | RSI buy threshold |
| `overbought` | 70 | RSI sell threshold |
| `use_bb_confirmation` | true | Require price near BB for entry (reads precomputed BB columns) |
| `use_adx_filter` | false | Filter low-ADX (choppy) markets |
| `adx_threshold` | 25 | Min ADX for signal (if filter enabled) |
| `cooldown_days` | 3 | Min days between signals |
| `stop_loss_atr_mult` | 2.5 | Stop-loss distance (x ATR) |
| `max_holding_days` | 40 | Max position holding period |

---

### 3. RSI Simple (`rsi_simple`)

Ultra-simple RSI mean reversion for frequent trading - no BB/ADX confirmation, no state
machine. Registered 2026-07-14 (audit bug 3.8) - previously fully implemented and
tested but unreachable through the export pipeline. Note: AlphaLive does not currently
register a matching `rsi_simple` strategy name of its own, so exports of this strategy
cannot yet be deployed to AlphaLive - see the class docstring
(`backend/src/strategies/implementations/rsi_simple.py`) for the separate, cross-repo
parity question this connects to.

```json
{
  "period": 14,
  "oversold": 40,
  "overbought": 60
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `period` | 14 | RSI calculation period |
| `oversold` | 40 | RSI buy threshold (relaxed vs. rsi_mean_reversion's 30, for more frequent signals) |
| `overbought` | 60 | RSI sell threshold (relaxed vs. rsi_mean_reversion's 70) |

---

### 4. Momentum Breakout (`momentum_breakout`)

Breakout strategy with trailing stop and volume surge confirmation.

```json
{
  "lookback": 20,
  "surge_pct": 1.5,
  "volume_ma_period": 20,
  "rsi_min": 50,
  "stop_loss_atr_mult": 2.0,
  "trailing_stop_atr_mult": 3.0,
  "cooldown_days": 3
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lookback` | 20 | Breakout lookback period (bars) |
| `surge_pct` | 1.5 | Required volume surge, as a ratio of avg volume (e.g. 1.5 = 1.5x). AlphaLab's internal class calls this `volume_surge_pct` and expresses it as a percentage (150 = 150%) - the export-mapping layer divides by 100 and renames it. |
| `volume_ma_period` | 20 | Volume moving average period. Internal name: `volume_avg_period`. |
| `rsi_min` | 50 | Min RSI for breakout confirmation |
| `stop_loss_atr_mult` | 2.0 | Initial stop-loss (x ATR) |
| `trailing_stop_atr_mult` | 3.0 | Trailing stop distance (x ATR) |
| `cooldown_days` | 3 | Min days between signals |

---

### 5. Bollinger Breakout (`bollinger_breakout`)

Trades N-consecutive-close breakouts above/below Bollinger Bands with optional volume confirmation.

```json
{
  "period": 20,
  "std_dev": 2.0,
  "confirmation_bars": 2,
  "volume_filter": true,
  "volume_threshold": 1.5,
  "cooldown_days": 3
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `period` | 20 | Bollinger Band period. AlphaLab's internal class calls this `bb_period` - renamed at export to match AlphaLive's `signal_engine.py`/`indicators.py`. |
| `std_dev` | 2.0 | Standard deviations for bands. Internal name: `bb_std_dev`. |
| `confirmation_bars` | 2 | Consecutive closes above/below band required to confirm breakout |
| `volume_filter` | true | Require volume confirmation |
| `volume_threshold` | 1.5 | Volume must exceed this multiple of its rolling average |
| `cooldown_days` | 3 | Min days between signals |

---

### 6. VWAP Reversion (`vwap_reversion`)

Mean reversion from a rolling VWAP with RSI confirmation.

```json
{
  "vwap_period": 20,
  "deviation_threshold": 2.0,
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "cooldown_days": 3
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vwap_period` | 20 | Rolling window (bars) for the VWAP calculation - not a "daily/weekly" string, an integer bar count |
| `deviation_threshold` | 2.0 | Required deviation from VWAP (std dev) to trigger entry |
| `rsi_period` | 14 | RSI calculation period |
| `oversold` | 30 | RSI oversold confirmation threshold |
| `overbought` | 70 | RSI overbought confirmation threshold |
| `cooldown_days` | 3 | Min days between signals |

---

### 7. Bollinger RSI Combo (`bollinger_rsi_combo`)

Entry on BB lower-band touch AND RSI oversold together; exit at BB middle or RSI overbought.

```json
{
  "bb_period": 20,
  "bb_std": 2.0,
  "rsi_period": 14,
  "rsi_oversold": 45,
  "rsi_overbought": 55,
  "exit_at_middle": true
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bb_period` | 20 | Bollinger Band period |
| `bb_std` | 2.0 | Bollinger Band standard deviations |
| `rsi_period` | 14 | RSI calculation period |
| `rsi_oversold` | 45 | RSI buy threshold - deliberately relaxed vs. pure RSI mean reversion, since BB touch is the primary signal |
| `rsi_overbought` | 55 | RSI sell threshold - deliberately tighter, exits faster |
| `exit_at_middle` | true | Exit when price reaches BB middle band |

---

### 8. Trend Adaptive RSI (`trend_adaptive_rsi`)

RSI thresholds that adapt to the prevailing trend regime (uptrend/downtrend/range), detected via a slow SMA.

```json
{
  "rsi_period": 14,
  "trend_sma": 50,
  "trend_lookback": 5,
  "uptrend_buy": 45,
  "uptrend_sell": 65,
  "downtrend_buy": 35,
  "downtrend_sell": 55,
  "range_buy": 35,
  "range_sell": 65
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rsi_period` | 14 | RSI calculation period |
| `trend_sma` | 50 | SMA period used for trend regime detection |
| `trend_lookback` | 5 | Bars required to confirm trend direction |
| `uptrend_buy` / `uptrend_sell` | 45 / 65 | RSI thresholds while in an uptrend regime |
| `downtrend_buy` / `downtrend_sell` | 35 / 55 | RSI thresholds while in a downtrend regime |
| `range_buy` / `range_sell` | 35 / 65 | RSI thresholds while ranging (no clear trend) |

---

### 9. Greenblatt Weekly (`greenblatt_weekly`)

Value-factor strategy on weekly bars: Greenblatt Magic Formula screening for candidate selection, then a 10w/50w golden-cross or RSI-oversold entry with a long minimum hold and trailing-stop-only exit by default. Use after `FundamentalScreener` (see `AlphaLab/CLAUDE.md` § Value Factor / Weekly Strategies).

```json
{
  "fast_sma": 10,
  "slow_sma": 50,
  "rsi_period": 14,
  "rsi_oversold": 35,
  "rsi_overbought": 65,
  "min_hold_bars": 52,
  "trailing_stop_fraction": 0.20,
  "exit_rsi_overbought": false,
  "exit_sma_cross": false
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fast_sma` | 10 | Fast SMA period (weeks). Must be one of FeatureEngineer's precomputed windows: 10/20/50/100/200 |
| `slow_sma` | 50 | Slow SMA period (weeks) - 50 weeks approx. 1 year. Same constraint as `fast_sma` |
| `rsi_period` | 14 | RSI calculation period |
| `rsi_oversold` | 35 | Weekly RSI entry threshold |
| `rsi_overbought` | 65 | Weekly RSI exit threshold (only used if `exit_rsi_overbought=true`) |
| `min_hold_bars` | 52 | Minimum hold in weeks (approx. 1 year) - bypassed only by the trailing stop |
| `trailing_stop_fraction` | 0.20 | Trailing stop distance from peak price, as a 0-1 fraction (0.20 = 20%) - the default, always-active exit. Deliberately not named `trailing_stop_pct` (2026-07-14 rename) - that name is `risk.trailing_stop_pct` below, an absolute percentage (e.g. 3.0 = 3%). Same name with incompatible units in the same document was a real ambiguity bug. |
| `exit_rsi_overbought` | false | Opt-in early exit on RSI overbought - disabled by default |
| `exit_sma_cross` | false | Opt-in early exit on SMA death-cross - disabled by default |

---

## Safety Limits (New in v1.0)

The `safety_limits` block provides **per-strategy customization** of stopping conditions that protect against:

1. **Signal bugs** - Runaway loops generating thousands of trades
2. **API rate limits** - Broker throttling/bans from excessive calls
3. **Performance degradation** - Slow signal generation blocking main loop
4. **Broker outages** - Extended API failures

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

1. **Strategy parameters** - Must match strategy type (validated by Pydantic union discriminator)
2. **Trailing stop** - If `trailing_stop_enabled=true`, `trailing_stop_pct` is required
3. **Limit orders** - If `order_type="limit"`, `limit_offset_pct` is required
4. **MA windows** - `short_window < long_window` (for ma_crossover)
5. **RSI thresholds** - `oversold < overbought` (for rsi_mean_reversion)
6. **Timeframe compatibility** - VWAP strategies require intraday timeframes (1Hour or 15Min)

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
      "strategy_type": "ma_crossover",
      "fast_period": 50,
      "slow_period": 200,
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

- **MAJOR** - Breaking changes (remove required field, change field type, incompatible validation)
  - Example: Remove `ticker` field, change `timeframe` from string to enum
  - AlphaLive **must reject** schemas with incompatible major version

- **MINOR** - Backward-compatible additions (new optional fields, new strategies, new enum values)
  - Example: Add `safety_limits` block (v1.0 → v1.1), add new strategy "vwap_reversion"
  - AlphaLive **should accept** older minor versions (ignore unknown fields)

### Compatibility Matrix

Schema version has stayed `1.0` since initial release - the 3 additional strategies (bollinger_rsi_combo, trend_adaptive_rsi, greenblatt_weekly) were added as backward-compatible enum additions per the MINOR rule above, not version bumps. There is no real-world compatibility matrix to track yet since this hasn't had a breaking (MAJOR) change.

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

**backend/strategy_schema.py** - already has all 8 current strategies' Pydantic param classes and the discriminated union (`StrategyParamsUnion`); a new strategy follows the same pattern:
```python
class MyNewStrategyParams(BaseModel):
    param1: int = Field(ge=1, le=100)
    param2: float = Field(ge=0.1, le=10.0)

StrategyParamsUnion = Union[
    MACrossoverParams,
    RSIMeanReversionParams,
    MomentumBreakoutParams,
    BollingerBreakoutParams,
    VWAPReversionParams,
    GreenblattWeeklyParams,
    BollingerRSIComboParams,
    TrendAdaptiveRSIParams,
    MyNewStrategyParams,  # Add here
]
```

**frontend/src/types/strategy_schema.ts** - NOTE (found 2026-07): this file is currently stale, only listing the original 5 strategies, and appears to never actually be imported anywhere in the frontend app. The live UI instead uses its own separate, equally-stale `StrategyType` in `frontend/src/types/index.ts` (also only 5 strategies). Both need fixing to add the 3 missing strategies - this is a real code gap, not just a doc gap; flagged separately, not fixed as part of this doc pass.
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
- Full Pydantic v2 type definitions

### Since v1.0 (no schema version bump - backward-compatible additions)
- Added 3 strategies: greenblatt_weekly, bollinger_rsi_combo, trend_adaptive_rsi
- Corrected `bollinger_breakout` and `vwap_reversion` parameter shapes to match what was actually implemented (both were previously documented with placeholder/aspirational params that didn't match the real code)
- Corrected `risk.take_profit_pct`, `risk.max_daily_loss_pct`, `risk.trailing_stop_pct`, and `risk.commission_per_trade` ranges to match the real Pydantic validators in `alphalive/strategy_schema.py`

---

## Support

For questions or issues:
- **AlphaLab Issues:** https://github.com/bernardoguterres/AlphaLab/issues
- **Schema Discussions:** https://github.com/bernardoguterres/AlphaLab/discussions

**Last Updated:** 2026-07-09
