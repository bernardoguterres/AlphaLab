# AlphaLab API Documentation

Base URL: `http://127.0.0.1:5000`

All responses follow the format:
```json
{
  "status": "ok" | "error",
  "data": { ... },
  "message": "error description (on failure)"
}
```

Response headers include `X-Request-Id` and `X-Response-Time-Ms` on every request.

---

## Table of Contents

- [Health Check](#health-check)
- [Data Endpoints](#data-endpoints)
  - [Fetch Data](#fetch-data)
  - [Available Data](#available-data)
- [Strategy Endpoints](#strategy-endpoints)
  - [Run Backtest](#run-backtest)
  - [Batch Backtest](#batch-backtest)
  - [Optimize Strategy](#optimize-strategy)
  - [Get Metrics](#get-metrics)
  - [Compare Strategies](#compare-strategies)
  - [Export Strategy](#export-strategy)
- [Portfolio Endpoints](#portfolio-endpoints)
  - [Optimize Portfolio](#optimize-portfolio)
- [Settings Endpoints](#settings-endpoints)
  - [Get Notification Settings](#get-notification-settings)
  - [Update Notification Settings](#update-notification-settings)
  - [Test Telegram Connection](#test-telegram-connection)
  - [Test Alpaca Connection](#test-alpaca-connection)

---

## Health Check

### `GET /api/health`

Returns API status and version.

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## Data Endpoints

### Fetch Data

#### `POST /api/data/fetch`

Download and cache stock data for one or more tickers.

**Request Body:**
```json
{
  "tickers": ["AAPL", "MSFT"],
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "interval": "1d"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tickers` | string[] | Yes | 1-20 uppercase ticker symbols |
| `start_date` | string | Yes | YYYY-MM-DD format |
| `end_date` | string | Yes | YYYY-MM-DD format |
| `interval` | string | No | `1d` (default), `1wk`, or `1mo` |

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "AAPL": {
      "records": 1258,
      "quality_score": 0.98,
      "start_date": "2020-01-02",
      "end_date": "2024-12-31"
    }
  },
  "errors": []
}
```

**Errors:** 422 (validation), 400 (invalid ticker)

**curl:**
```bash
curl -X POST http://127.0.0.1:5000/api/data/fetch \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL"], "start_date": "2020-01-01", "end_date": "2024-12-31"}'
```

---

### Available Data

#### `GET /api/data/available`

List all cached tickers with date ranges and record counts.

**Response (200):**
```json
{
  "status": "ok",
  "data": [
    {
      "ticker": "AAPL",
      "interval": "1d",
      "start": "2020-01-01",
      "end": "2024-12-31",
      "records": 1258,
      "timestamp": 1708900000.0,
      "key": "abc123"
    }
  ]
}
```

---

## Strategy Endpoints

### Run Backtest

#### `POST /api/strategies/backtest`

Execute a backtest with a specified strategy.

**Request Body:**
```json
{
  "ticker": "AAPL",
  "strategy": "ma_crossover",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 100000,
  "params": {
    "short_window": 50,
    "long_window": 200
  },
  "position_sizing": "equal_weight",
  "monte_carlo_runs": 0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | Yes | Stock ticker |
| `strategy` | string | Yes | `ma_crossover`, `rsi_mean_reversion`, `momentum_breakout`, `bollinger_breakout`, or `vwap_reversion` |
| `start_date` | string | Yes | YYYY-MM-DD |
| `end_date` | string | Yes | YYYY-MM-DD |
| `initial_capital` | float | No | Starting cash (default: 100000, min: 1000) |
| `params` | object | No | Strategy-specific parameters (uses defaults if omitted) |
| `position_sizing` | string | No | `equal_weight`, `risk_parity`, or `volatility_weighted` |
| `monte_carlo_runs` | int | No | Number of Monte Carlo simulations (0 = disabled) |
| `risk_settings` | object | No | Risk management settings (stop-loss, take-profit, position limits, etc.) |

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "backtest_id": "a1b2c3d4",
    "strategy": "MA_Crossover",
    "initial_capital": 100000,
    "final_value": 112500.00,
    "total_return_pct": 12.50,
    "total_trades": 8,
    "equity_curve": [{"date": "2020-01-02", "value": 100000.00}, ...],
    "trades": [...],
    "metrics": {
      "returns": {...},
      "risk": {...},
      "drawdown": {...},
      "trades": {...},
      "consistency": {...},
      "vs_benchmark": {...}
    },
    "monte_carlo": null
  }
}
```

**Errors:** 400 (invalid ticker/strategy), 422 (data quality too low)

---

### Batch Backtest

#### `POST /api/strategies/batch-backtest`

Test one strategy across multiple tickers (up to 20).

**Request Body:**
```json
{
  "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN"],
  "strategy": "ma_crossover",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 100000,
  "params": {
    "short_window": 50,
    "long_window": 200
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tickers` | string[] | Yes | 1-20 ticker symbols |
| `strategy` | string | Yes | Strategy name |
| `start_date` | string | Yes | YYYY-MM-DD |
| `end_date` | string | Yes | YYYY-MM-DD |
| `initial_capital` | float | No | Starting cash (default: 100000) |
| `params` | object | No | Strategy parameters |
| `risk_settings` | object | No | Risk management settings |

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "results": [
      {
        "ticker": "AAPL",
        "total_return_pct": 15.2,
        "sharpe_ratio": 1.8,
        "max_drawdown_pct": -12.5,
        "total_trades": 10,
        "win_rate_pct": 60.0,
        "backtest_id": "abc123"
      }
    ],
    "summary": {
      "total_tested": 4,
      "profitable_count": 3,
      "avg_sharpe": 1.5,
      "best_ticker": "AAPL",
      "worst_ticker": "AMZN",
      "total_runtime_seconds": 8.5
    },
    "failed": []
  }
}
```

**Note:** Results are sorted by Sharpe ratio (descending). Sequential execution with 0.5s delay between uncached data fetches.

---

### Optimize Strategy

#### `POST /api/strategies/optimize`

Grid search for best strategy parameters.

**Request Body:**
```json
{
  "ticker": "AAPL",
  "strategy": "ma_crossover",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "param_grid": {
    "short_window": [20, 50, 100],
    "long_window": [100, 150, 200]
  }
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "best_params": {"short_window": 50, "long_window": 200},
    "best_score": 0.145,
    "all_results": [...]
  }
}
```

---

### Get Metrics

#### `GET /api/metrics/<backtest_id>`

Retrieve cached backtest results by ID.

**Response (200):** Full backtest result object (same as backtest response `data`).

**Errors:** 404 (backtest not found)

---

### Compare Strategies

#### `POST /api/compare`

Run multiple strategies side-by-side on the same data.

**Request Body:**
```json
{
  "ticker": "AAPL",
  "strategies": ["ma_crossover", "rsi_mean_reversion", "momentum_breakout", "bollinger_breakout", "vwap_reversion"],
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 100000
}
```

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "ma_crossover": {
      "total_return_pct": 12.50,
      "metrics": {...}
    },
    "rsi_mean_reversion": {
      "total_return_pct": 8.30,
      "metrics": {...}
    },
    "momentum_breakout": {
      "total_return_pct": 15.10,
      "metrics": {...}
    }
  }
}
```

---

### Export Strategy

#### `POST /api/strategies/export`

Export a backtest strategy configuration as JSON for use in AlphaLive (live trading).

**Request Body:**
```json
{
  "backtest_id": "a1b2c3d4"
}
```

**Response (200):**

Downloads a JSON file named `{strategy}_{ticker}_{YYYYMMDD}.json` following the [Strategy Export Schema v1.0](STRATEGY_SCHEMA.md).

```json
{
  "schema_version": "1.0",
  "strategy": {
    "name": "ma_crossover",
    "parameters": {...}
  },
  "ticker": "AAPL",
  "timeframe": "1Day",
  "risk": {...},
  "execution": {...},
  "safety_limits": {...},
  "metadata": {...}
}
```

**Errors:** 404 (backtest not found), 500 (schema validation failed)

---

## Portfolio Endpoints

### Optimize Portfolio

#### `POST /api/portfolio/optimize`

Optimize capital allocation across multiple strategies using Modern Portfolio Theory.

**Request Body:**
```json
{
  "strategies": [
    {
      "name": "ma_crossover",
      "backtest_id": "abc123",
      "equity_curve": [...]
    },
    {
      "name": "rsi_mean_reversion",
      "backtest_id": "def456",
      "equity_curve": [...]
    }
  ],
  "method": "max_sharpe",
  "max_weight": 0.5,
  "min_weight": 0.05,
  "risk_free_rate": 0.02
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `strategies` | array | Yes | 2+ strategies with equity curves |
| `method` | string | Yes | `max_sharpe`, `min_variance`, `risk_parity`, or `equal_weight` |
| `max_weight` | float | No | Max allocation per strategy (0.1-1.0, default: 0.5) |
| `min_weight` | float | No | Min allocation per strategy (0.0-0.5, default: 0.05) |
| `risk_free_rate` | float | No | Risk-free rate for Sharpe calculation (default: 0.02) |

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "optimal_weights": [0.35, 0.30, 0.20, 0.15],
    "expected_return": 0.145,
    "expected_risk": 0.082,
    "sharpe_ratio": 1.52,
    "method": "max_sharpe",
    "efficient_frontier": [
      {"risk": 0.05, "return": 0.08},
      {"risk": 0.10, "return": 0.15}
    ]
  }
}
```

**Errors:** 400 (insufficient strategies, invalid method), 422 (validation error)

---

## Settings Endpoints

### Get Notification Settings

#### `GET /api/settings/notifications`

Retrieve current notification settings (non-sensitive only).

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "telegram": {
      "enabled": false,
      "alert_trades": true,
      "alert_daily_summary": true,
      "alert_errors": true,
      "alert_drawdown": true,
      "alert_signals": false,
      "drawdown_threshold_pct": 5.0,
      "bot_token_configured": false,
      "chat_id_configured": false
    },
    "alpaca": {
      "paper_trading": true,
      "api_key_configured": false,
      "secret_key_configured": false
    }
  }
}
```

**Note:** Actual API keys/tokens are NEVER returned, only boolean `*_configured` flags.

---

### Update Notification Settings

#### `POST /api/settings/notifications`

Update notification settings (non-sensitive only).

**Request Body:**
```json
{
  "telegram": {
    "enabled": true,
    "alert_trades": true,
    "alert_daily_summary": true,
    "alert_errors": true,
    "alert_drawdown": true,
    "alert_signals": false,
    "drawdown_threshold_pct": 5.0
  },
  "alpaca": {
    "paper_trading": true
  }
}
```

**Response (200):**
```json
{
  "status": "ok",
  "message": "Settings updated successfully"
}
```

**Security:** This endpoint REJECTS requests containing API keys, tokens, or secrets. All credentials must be set via environment variables.

**Errors:** 400 (forbidden field detected), 422 (validation error)

---

### Test Telegram Connection

#### `POST /api/settings/telegram/test`

Send a test message to verify Telegram bot configuration.

**Request Body:** None

**Response (200):**
```json
{
  "status": "ok",
  "message": "Test message sent successfully to Telegram"
}
```

**Errors:** 400 (credentials not configured), 500 (Telegram API error)

**Note:** Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from environment variables.

---

### Test Alpaca Connection

#### `POST /api/settings/alpaca/test`

Verify Alpaca API connection and retrieve account details.

**Request Body:** None

**Response (200):**
```json
{
  "status": "ok",
  "data": {
    "account_status": "ACTIVE",
    "buying_power": 98765.43,
    "cash": 100000.00,
    "paper_trading": true
  }
}
```

**Errors:** 400 (credentials not configured), 500 (Alpaca API error)

**Note:** Reads `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` from environment variables.

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid ticker, date range, or strategy) |
| 404 | Resource not found (backtest ID doesn't exist) |
| 422 | Validation error (Pydantic) or data quality too low |
| 500 | Internal server error |
