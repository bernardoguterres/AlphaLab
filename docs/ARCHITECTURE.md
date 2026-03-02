# AlphaLab Architecture

## System Overview

```
User
 │
 ├──► Frontend (Tauri + React)
 │       │
 │       ▼
 │    Flask REST API (/api/*)
 │       │
 │       ├──► Data Pipeline
 │       │      DataFetcher → DataValidator → FeatureEngineer
 │       │      (yfinance)    (quality)       (50+ indicators)
 │       │           │
 │       │           ▼
 │       │      CacheManager (parquet files)
 │       │
 │       ├──► Strategy Engine
 │       │      BaseStrategy → generate_signals()
 │       │      ├── MA Crossover
 │       │      ├── RSI Mean Reversion
 │       │      └── Momentum Breakout
 │       │
 │       ├──► Backtest Engine
 │       │      Portfolio ← Orders (market/limit/stop)
 │       │      │
 │       │      ├── Walk-Forward Validation
 │       │      └── Monte Carlo Simulation
 │       │
 │       └──► Metrics Calculator
 │              Returns, Risk, Drawdown, Trade Stats,
 │              Consistency, Benchmark Comparison
 │
 └──► Results (JSON)
```

## Module Responsibilities

### Data Layer (`src/data/`)

| Module | Purpose |
|--------|---------|
| `fetcher.py` | Download market data from Yahoo Finance with retries, validation, and caching |
| `validator.py` | Clean and validate OHLCV data — outlier detection, gap filling, confidence scoring |
| `processor.py` | Compute 50+ technical indicators and statistical features |
| `cache_manager.py` | File-based parquet storage with expiry to avoid redundant API calls |

**Data flow:** Raw download → Validation/Cleaning → Feature Engineering → Ready for strategies

### Strategy Layer (`src/strategies/`)

| Module | Purpose |
|--------|---------|
| `base_strategy.py` | Abstract interface: `validate_params()`, `generate_signals()`, `required_columns()` |
| `implementations/` | Concrete strategies that produce buy/sell/hold signals with confidence scores |

**Signal format:** Each bar gets `signal` (1/-1/0), `confidence` (0-1), and `reason` (text).

### Backtest Layer (`src/backtest/`)

| Module | Purpose |
|--------|---------|
| `engine.py` | Bar-by-bar simulation; signals on bar N execute on bar N+1's open |
| `portfolio.py` | Cash/position tracking, order execution with costs, risk management |
| `order.py` | Order model (market, limit, stop-loss, trailing stop) |
| `metrics.py` | 30+ performance metrics: Sharpe, Sortino, drawdown, trade stats, etc. |

**Execution model:**
1. Strategy generates signal at close of bar N
2. Engine queues signal as "pending"
3. On bar N+1, pending signal executes at open price
4. Slippage and commission are applied
5. Portfolio state updates, equity recorded

### API Layer (`src/api/`)

| Module | Purpose |
|--------|---------|
| `routes.py` | Flask endpoints, middleware (timing, error handling, request IDs) |
| `validators.py` | Pydantic models for request validation |

### Utils (`src/utils/`)

| Module | Purpose |
|--------|---------|
| `logger.py` | Rotating file + console logger setup |
| `config.py` | YAML config loader with singleton caching |

## Design Decisions

### No Look-Ahead Bias
The engine strictly separates signal generation (uses data up to current bar) from execution (next bar's open). This is the most common source of backtesting bugs and is enforced architecturally.

### Realistic Execution Costs
Every order includes slippage (configurable %, default 0.05%) and commission. Position sizing respects maximum allocation per stock and cash reserve requirements. A drawdown halt stops all trading if portfolio drops beyond a threshold.

### Feature Engineering Before Strategy
Indicators are pre-computed in a single pass by `FeatureEngineer`, producing a wide DataFrame. Strategies then reference columns by name rather than computing indicators themselves. This ensures consistency and avoids redundant computation.

### Caching Strategy
Raw market data is cached as parquet files with a configurable expiry (default 24h). Features are regenerated on demand since they're fast to compute (~1-2s per stock). This balances freshness with API rate limits.

### Pydantic Validation
All API inputs are validated before any processing. This catches bad tickers, invalid dates, and malformed requests at the boundary rather than deep in business logic.

## Performance Characteristics

| Operation | Typical Time |
|-----------|-------------|
| Data fetch (1 stock, 5 years) | 2-5s (first time), <100ms (cached) |
| Feature engineering (1 stock) | 0.5-2s |
| Backtest (1 stock, 1 strategy) | 1-3s |
| Full API response | 5-10s (uncached), 2-4s (cached) |
| Memory (10 stocks loaded) | ~200-400MB |
