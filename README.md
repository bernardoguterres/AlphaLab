# AlphaLab

Desktop application for backtesting algorithmic trading strategies with production-grade execution simulation.

## Why AlphaLab?

Most backtesting tools either oversimplify execution (ignoring slippage, commissions, and position limits) or require expensive subscriptions. AlphaLab provides institutional-quality backtesting with realistic execution modeling, 30+ performance metrics, and Monte Carlo analysis — all running locally on your machine with free Yahoo Finance data.

## Features

- **Market Data Pipeline** — Fetch, validate, and cache stock data from Yahoo Finance with automatic retry and quality scoring
- **50+ Technical Indicators** — SMA, EMA, MACD, RSI, Bollinger Bands, ATR, OBV, Fibonacci levels, and more
- **3 Built-in Strategies** — Moving Average Crossover, RSI Mean Reversion, Momentum Breakout
- **Realistic Backtesting** — Next-bar execution (no look-ahead bias), configurable slippage and commissions, position limits
- **30+ Performance Metrics** — Sharpe, Sortino, Calmar, max drawdown, VaR, win rate, profit factor, benchmark comparison
- **Monte Carlo Simulation** — Randomized entry timing to assess outcome distributions
- **Walk-Forward Validation** — Rolling train/test splits to detect overfitting
- **REST API** — Flask endpoints with Pydantic validation for frontend integration

## Tech Stack

- **Backend**: Python, Flask, pandas, numpy, scipy, yfinance, stockstats, Pydantic
- **Frontend**: React, TypeScript, Vite, shadcn/ui, Tailwind CSS, Recharts, Zustand
- **Desktop**: Tauri (Rust) - Native macOS/Windows/Linux app with <10MB footprint

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+ & npm

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

The API starts at `http://127.0.0.1:5000`.

### Frontend Setup

**Option 1: Web Version**
```bash
cd frontend
npm install
npm run dev
```
The UI starts at `http://localhost:8080`.

**Option 2: Desktop App (Tauri)**

Prerequisites (one-time):
```bash
# macOS only: Accept Xcode license (if not already done)
sudo xcodebuild -license

# Install Rust (all platforms)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

Run:
```bash
cd frontend
npm install                 # First time only
npm run tauri:dev          # Launch desktop app (first run: 2-3 min)
npm run tauri:build        # Build installer (.dmg/.msi/.deb)
```

**Installing the .dmg (macOS):**
After running `npm run tauri:build`, find the installer at:
```
frontend/src-tauri/target/release/bundle/dmg/AlphaLab_*.dmg
```
Double-click to install, then drag AlphaLab.app to your Applications folder.

### Full Application

Run backend + frontend in separate terminals:

```bash
# Terminal 1 - Backend (REQUIRED for both web and desktop)
cd backend && source venv/bin/activate && python run.py

# Terminal 2 - Frontend (choose one):
cd frontend && npm run dev           # Web → http://localhost:8080
# OR
cd frontend && npm run tauri:dev     # Desktop → native app window
```

### Run Tests

```bash
# Backend tests (81 tests)
cd backend
source venv/bin/activate
pytest tests/ -v

# Frontend tests
cd frontend
npm run test
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/data/fetch` | Fetch and cache stock data |
| GET | `/api/data/available` | List cached tickers |
| POST | `/api/strategies/backtest` | Run a backtest |
| POST | `/api/strategies/optimize` | Grid search for best parameters |
| GET | `/api/metrics/<id>` | Retrieve backtest results |
| POST | `/api/compare` | Compare multiple strategies |

See [docs/API.md](docs/API.md) for full endpoint documentation with request/response schemas and curl examples.

### Example: Run a Backtest

```bash
curl -X POST http://127.0.0.1:5000/api/strategies/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "strategy": "ma_crossover",
    "start_date": "2020-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 100000
  }'
```

## Available Strategies

| Strategy | Description | Key Parameters |
|----------|-------------|----------------|
| `ma_crossover` | Buy/sell on moving average crossovers (Golden/Death Cross) | `short_window`, `long_window`, `cooldown_days` |
| `rsi_mean_reversion` | Buy oversold, sell overbought with BB/ADX confirmation | `oversold`, `overbought`, `adx_threshold` |
| `momentum_breakout` | Enter on price breakout with volume surge | `lookback`, `volume_surge_pct`, `stop_loss_atr_mult` |

See [docs/STRATEGIES.md](docs/STRATEGIES.md) for detailed strategy documentation.

## Project Structure

```
AlphaLab/
├── backend/                    # Flask REST API (Python)
│   ├── src/
│   │   ├── data/              # Fetching, validation, feature engineering
│   │   ├── strategies/        # BaseStrategy + 3 implementations
│   │   ├── backtest/          # Engine, portfolio, metrics, orders
│   │   ├── api/               # Flask routes + Pydantic validators
│   │   └── utils/             # Logger, config, exceptions
│   ├── tests/                 # 81 pytest tests
│   ├── config.yaml
│   ├── requirements.txt
│   └── run.py
├── frontend/                   # React UI (TypeScript + Vite + Tauri)
│   ├── src/
│   │   ├── pages/             # Dashboard, Backtest, Compare, DataManager
│   │   ├── components/        # UI components (charts, forms, metrics)
│   │   ├── services/          # API client (axios)
│   │   ├── stores/            # Zustand state management
│   │   ├── types/             # TypeScript types
│   │   └── utils/             # Formatters, validators
│   ├── src-tauri/             # Tauri desktop app config
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── docs/                       # Technical documentation
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── STRATEGIES.md
│   ├── METRICS_GUIDE.md
│   └── TROUBLESHOOTING.md
├── README.md                   # This file
├── SETUP.md                    # Setup instructions
├── TAURI_SETUP.md              # Desktop app rebuild guide
├── CONTRIBUTING.md             # Contribution guidelines
├── CLAUDE.md                   # Development guide
├── LICENSE
└── .gitignore
```

## Documentation

**Getting Started:**
- [SETUP.md](SETUP.md) — Installation and setup instructions
- [TAURI_SETUP.md](TAURI_SETUP.md) — Desktop app rebuild guide
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute to the project
- [CLAUDE.md](CLAUDE.md) — Complete development guide (for AI assistants)

**Technical Docs:**
- [API Reference](docs/API.md) — All endpoints with schemas and examples
- [Architecture](docs/ARCHITECTURE.md) — System design and data flow
- [Strategies](docs/STRATEGIES.md) — Strategy details and how to add new ones
- [Metrics Guide](docs/METRICS_GUIDE.md) — What each metric means
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues and FAQ

## Configuration

All settings are in `backend/config.yaml` — initial capital, slippage, commission rates, strategy defaults, API port, and logging.

## Roadmap

- [x] React + TypeScript frontend with interactive charts (Recharts)
- [x] Dashboard with backtest history and quick stats
- [x] Strategy comparison page (side-by-side analysis)
- [x] Tauri desktop packaging (.dmg for macOS, .msi for Windows, .deb for Linux)
- [ ] Additional strategies (Pairs Trading, Bollinger Band Breakout)
- [ ] Multi-asset portfolio optimization
- [ ] PDF report export
- [ ] Real-time data via WebSocket
- [ ] Machine learning strategy framework

---

## Contributing

We welcome contributions! Here's how to get started:

### Development Workflow

1. **Fork the repository**
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/alphalab.git
   cd alphalab
   ```
3. **Set up the development environment:**
   - Follow [SETUP.md](SETUP.md) for backend and frontend setup

### Backend Development

```bash
cd backend
source venv/bin/activate
python run.py
```

**Making changes:**
1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests: `pytest tests/ -v`
4. Ensure all 81 tests pass

**Code style:**
- Follow PEP 8
- Use Black formatter (100-char lines)
- Add Google-style docstrings to public methods
- Type hints where appropriate

### Frontend Development

```bash
cd frontend
npm run dev          # Web version
npm run tauri:dev    # Desktop version
```

**Making changes:**
1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run linter: `npm run lint`
4. Run tests: `npm run test`
5. Test in both web and desktop modes

**Code style:**
- TypeScript strict mode
- ESLint + Prettier
- Use functional components and hooks
- Tailwind for styling (no inline styles)

### Adding a New Strategy

1. **Create strategy file:**
   ```
   backend/src/strategies/implementations/your_strategy.py
   ```

2. **Inherit from BaseStrategy:**
   ```python
   from ..base_strategy import BaseStrategy

   class YourStrategy(BaseStrategy):
       def validate_params(self, params: dict) -> dict:
           # Validate parameters
           pass

       def generate_signals(self, data: pd.DataFrame, params: dict) -> pd.DataFrame:
           # Generate buy/sell signals
           pass

       def required_columns(self) -> list:
           # Return required indicator columns
           pass
   ```

3. **Register in `implementations/__init__.py`**
4. **Add to `STRATEGY_MAP` in `api/routes.py`**
5. **Add tests in `tests/test_strategies.py`**
6. **Document in `docs/STRATEGIES.md`**

### Pull Request Process

1. **Update documentation** - Update relevant markdown files
2. **Add tests** - New features need test coverage
3. **Run all tests** - Ensure nothing breaks
4. **Commit with clear messages:**
   ```
   feat: Add Bollinger Band breakout strategy
   fix: Correct slippage calculation in portfolio
   docs: Update API documentation for new endpoint
   ```

5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request** - Provide clear description of changes

### Commit Message Guidelines

We follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding or updating tests
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Maintenance tasks

**Examples:**
```
feat: Add walk-forward validation to backtest engine
fix: Handle missing data in RSI calculation
docs: Add examples to METRICS_GUIDE.md
test: Add unit tests for DataValidator
```

### Code Review Checklist

Before submitting, ensure:

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No sensitive data (API keys, credentials)
- [ ] Changes work in both web and desktop modes (if frontend)
- [ ] Performance impact considered (if applicable)

### Reporting Issues

**Bug reports should include:**
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python/Node version)
- Relevant logs or error messages

**Feature requests should include:**
- Use case / motivation
- Proposed solution
- Any alternatives considered

---

## Project Status

**Current Version:** 0.1.0
**Status:** ✅ Production Ready

### What's Included

#### Backend
- ✅ Flask REST API (127.0.0.1:5000)
- ✅ 81 passing tests
- ✅ 7 API endpoints with Pydantic validation
- ✅ 3 trading strategies (MA Crossover, RSI Mean Reversion, Momentum Breakout)
- ✅ 50+ technical indicators
- ✅ 30+ performance metrics
- ✅ Data caching with parquet
- ✅ Python virtual environment configured

#### Frontend
- ✅ React + TypeScript + Vite
- ✅ 4 pages: Dashboard, Backtest, Compare, DataManager
- ✅ shadcn/ui components
- ✅ Recharts visualizations
- ✅ Zustand state management
- ✅ React Query for API calls
- ✅ Tailwind CSS styling

#### Desktop App (Tauri)
- ✅ Tauri configured and working
- ✅ macOS .dmg installer (5.5MB)
- ✅ Correct app icons installed (1024x1024 source)
- ✅ App ID: com.alphalab.app
- ✅ Window: 1400x900 (min 1200x700)
- ✅ Build scripts: `tauri:dev`, `tauri:build`

### Project Stats

- **Backend Code:** Python, Flask
- **Frontend Code:** TypeScript, React
- **Total Tests:** 81 (all passing)
- **API Endpoints:** 7
- **Strategies:** 3
- **Indicators:** 50+
- **Metrics:** 30+
- **Desktop Installer:** 5.5MB

---

## License

MIT — see [LICENSE](LICENSE)
