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
  - [Optimize Strategy](#optimize-strategy)
  - [Get Metrics](#get-metrics)
  - [Compare Strategies](#compare-strategies)

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
| `strategy` | string | Yes | `ma_crossover`, `rsi_mean_reversion`, or `momentum_breakout` |
| `start_date` | string | Yes | YYYY-MM-DD |
| `end_date` | string | Yes | YYYY-MM-DD |
| `initial_capital` | float | No | Starting cash (default: 100000, min: 1000) |
| `params` | object | No | Strategy-specific parameters (uses defaults if omitted) |
| `position_sizing` | string | No | `equal_weight`, `risk_parity`, or `volatility_weighted` |
| `monte_carlo_runs` | int | No | Number of Monte Carlo simulations (0 = disabled) |

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
  "strategies": ["ma_crossover", "rsi_mean_reversion", "momentum_breakout"],
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

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid ticker, date range, or strategy) |
| 404 | Resource not found (backtest ID doesn't exist) |
| 422 | Validation error (Pydantic) or data quality too low |
| 500 | Internal server error |
