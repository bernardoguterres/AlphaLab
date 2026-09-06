# AlphaLab

A full-stack strategy research platform for systematic trading: it backtests with next-bar
execution and explicit transaction costs, selects parameters via held-out walk-forward validation,
and returns schema-validated JSON compatible with a separate downstream execution engine,
**AlphaLive**.

## Status and evidence boundary

**Portfolio release / engineering prototype.** The backtest engine, cost modelling, and
walk-forward machinery are implemented and exercised by an automated test suite (423 backend
tests) and real-data research scripts run outside CI. This README makes no claim of discovered
trading alpha: the daily-strategy walk-forward script covers three of nine strategies with
uncommitted output, and the Greenblatt screener has a committed result for one of six regime
windows, where the ranking didn't beat diversification (see [Results](#results)). Both are kept as
honest evidence about the validation machinery, not a broad, already-proven performance claim.

## Engineering highlights

- **Causality-safe execution** - a signal generated at bar N's close only fills at bar N+1's open,
  enforced architecturally and verified at runtime.
- **Leakage-safe walk-forward optimization** - each fold picks parameters from training data only,
  then that frozen choice is scored once on the untouched test window.
- **Realistic costs** - percentage-of-notional slippage and commission (default `0.0`),
  position-size limits, and a max-drawdown halt, applied through the portfolio layer - see
  [Causality-safe backtesting and costs](#causality-safe-backtesting-and-costs) for what isn't
  simulated.
- **Schema-validated export** - Pydantic validates export structure and each strategy's parameter
  model; a conditional cross-repo test compares schema fields when AlphaLive is available, reducing
  but not eliminating contract-drift risk.
- **Real cross-repo compatibility evidence** - AlphaLive's pytest-collected multi-ticker
  signal-parity tests, including a documented xfail for one ATR-related case, rather than this
  README asserting parity on its own.

## Research-to-export architecture

React (TypeScript, Vite) talks to a Flask REST API, which fetches and caches Yahoo Finance data,
then validates and feature-engineers it. From there, data either runs through a strategy and the
next-bar backtest engine into a stored in-memory result, or through the walk-forward optimizer,
producing held-out fold scores rather than a stored result. A stored backtest result can become
AlphaLive-compatible JSON via `/api/strategies/export`, which validates the export structure and
parameter model with Pydantic before returning it.

```mermaid
flowchart TB
    UI["React UI"] --> API["Flask API"]
    API --> FETCH["Yahoo Finance fetch/cache"]
    FETCH --> FEAT["Validation and feature engineering"]
    FEAT --> STRAT["Strategy calculation"]
    STRAT --> BT["Next-bar backtest engine"]
    BT --> PORT["Portfolio accounting"]
    PORT --> MET["Performance metrics"]
    MET --> STORE["In-memory result store"]
    FEAT --> OPT["Walk-forward optimizer"]
    OPT --> SEL["Train-only fold selection"]
    SEL --> SCORE["Held-out fold scores"]
    STORE --> EXP["Pydantic export validation"]
    EXP --> JSON["AlphaLive-compatible JSON"]
    JSON --> LIVE["AlphaLive (external, downstream)"]
```

AlphaLive is external and separately maintained: the endpoint returns compatible JSON, it doesn't
transfer or install anything into AlphaLive, and the walk-forward branch is research, not an export
input. Three repos make up the system: **AlphaLab** (research and export), **AlphaLive** (loads a
compatible export, generates signals, applies risk controls, includes an Alpaca broker adapter and
paper-trading configuration), and **AlphaSignal** (a RAG/sentiment service AlphaLive consumes as an
optional pre-execution gate).

## Causality-safe backtesting and costs

The backtest engine is event-driven: a strategy generates a signal at bar N's close, the engine
queues it as pending, and it fills at bar N+1's open. This is enforced architecturally, and was
verified at runtime - signals were generated on data truncated at a fixed timestamp, then again
after appending future bars, and the historical signal was confirmed unchanged. That's one targeted
test, not proof no leakage exists anywhere, but it's runtime evidence, not a design claim alone.

Costs are applied in the portfolio layer, and two commission settings shouldn't be confused. The
engine simulates `backend/config.yaml`'s `backtest.commission` - a percentage-of-notional rate per
fill, currently `0.0` - plus slippage and position-size limits. `risk_settings.commission_per_trade`
is different: a flat USD fee, accepted and exported but deliberately not wired in, since the
portfolio has no flat-fee model. It, `max_daily_loss_pct`, and `max_open_positions` flow through to
the AlphaLive export but aren't simulated here - the engine is single-ticker/single-position, with
no multi-position cap, "rest of day" concept, or flat-fee model to enforce; they take effect once
running in AlphaLive. The `max_drawdown_pct` halt is likewise only re-checked after an order fill,
not on every mark-to-market update - see [Known limitations](#known-limitations).

## Leakage-safe walk-forward optimization

Grid search alone overfits: picking parameters that scored best on the test set and reporting that
score is circular. AlphaLab's optimizer instead evaluates the full grid on each fold's training
window, freezes whichever combination won on training data only, and scores that frozen choice
once against the fold's held-out test window. Test-fold performance never influences which
combination is chosen, and successive folds advance through time.

```mermaid
flowchart TB
    subgraph F1["Fold 1"]
        direction LR
        T1["Training window"] --> G1["Evaluate parameter grid"] --> W1["Choose and freeze training winner"] --> X1["Untouched test window"] --> S1["One OOS score"]
    end
    subgraph F2["Fold 2 (later in time)"]
        direction LR
        T2["Training window"] --> G2["Evaluate parameter grid"] --> W2["Choose and freeze training winner"] --> X2["Untouched test window"] --> S2["One OOS score"]
    end
    F1 -.time advances.-> F2
```

The final "best" parameter set an optimizer run returns - and the full-data backtest often quoted
alongside it - is chosen the same train-only way, but over the *entire* dataset rather than a
fold's training slice. That figure is an in-sample reference result, not additional out-of-sample
evidence on top of the fold scores.

## Results

The shipped strategies are established, textbook systematic approaches - moving-average crossovers,
RSI mean reversion, Bollinger breakouts - rather than novel alpha models.

`scripts/walk_forward_validation.py` exercises AlphaLab's walk-forward machinery on three strategies
(`rsi_simple`, `bollinger_rsi_combo`, `trend_adaptive_rsi`) across two rolling SPY windows (train
2019-2021 / test 2022, and train 2020-2022 / test 2023). It doesn't run in CI, its output isn't
committed, and it doesn't cover `ma_crossover`, `momentum_breakout`, or `bollinger_breakout`. The
repository demonstrates the methodology and an executable research path for those three strategies
and two windows, not a committed result supporting a broader all-strategy conclusion. AlphaLab
makes no claim that any shipped strategy has discovered persistent market alpha.

The Greenblatt Magic Formula screener/weekly strategy has a narrower committed evidence base.
`scripts/greenblatt_research.py` supports six regime windows, but only one is committed:
[`scripts/greenblatt_research_result.json`](scripts/greenblatt_research_result.json), the 2022 Bear
window, where the ranked strategy scored Sharpe `-1.1581` against an equal-weight benchmark of the
same universe at `-0.3927` - it did not beat diversification here. `docs/MATH_EXPLAINER.md`
describes a broader result (losing in 4 of 6 windows); that's narrative, not something this
repository lets a reader reproduce, since only the window above is committed. Any figure here also
carries the caveat already noted: `FundamentalScreener` applies today's fundamentals to historical
prices, over a hand-picked, present-day universe.

## AlphaLive export contract and parity evidence

Not every backtestable strategy is deployable. `POST /api/strategies/export` rejects `rsi_simple`
(research-only) and `vwap_reversion` (needs an intraday timeframe AlphaLab can't fetch) with a 422
and explanation, rather than a config AlphaLive would only reject later. Both remain backtestable;
neither is exportable, leaving **seven of the nine** strategies directly exportable.

Contract and cross-engine evidence exist at three levels, which shouldn't be conflated:

- **Export-time validation.** Pydantic validates the export structure and each strategy's
  parameter model before returning JSON.
- **Conditional schema-field parity.** `backend/tests/test_schema_contract.py` compares AlphaLab's
  and AlphaLive's Pydantic field sets when AlphaLive is checked out as a sibling directory. CI
  attempts that checkout with `continue-on-error: true`, skipping the module (not failing the
  build) if it's unavailable - so this doesn't run on every CI build.
- **Cross-engine signal diagnostics (AlphaLive repo).**
  [`test_signal_parity.py`](https://github.com/bernardoguterres/AlphaLive/blob/main/tests/test_signal_parity.py)
  is a standalone diagnostic script, not pytest/CI-collected.
  [`test_multi_ticker_parity.py`](https://github.com/bernardoguterres/AlphaLive/blob/main/tests/test_multi_ticker_parity.py)
  is pytest-collected with strict assertions and a documented `xfail` for an RSI/MSFT case tied to
  the two repos' independently implemented ATR calculations.
  [`test_schema_contract.py`](https://github.com/bernardoguterres/AlphaLive/blob/main/tests/test_schema_contract.py)
  mirrors the check above from AlphaLive's own suite.

These checks provide useful compatibility evidence, not a measured repository-wide parity
percentage. The RSI, ATR and parameter-alias cases they exercise remain covered by the linked
tests, but the available evidence does not support a single aggregate parity claim.

## Interface and supported strategies

The React UI covers backtest configuration/results (single, batch, parameter-optimize), strategy
comparison, cached-data management, and settings - a client for the Flask API, nothing more.

Nine strategies are implemented and backtestable, spanning trend-following, mean-reversion,
breakout, and value-factor approaches. Defaults are AlphaLab's own; AlphaLive may apply its own
defaults for fields an export omits.

| # | Strategy | Type | Key params | Deployable |
|---|---|---|---|---|
| 1 | `ma_crossover` | Trend-following | `short_window` (50), `long_window` (200), `volume_confirmation`, `cooldown_days` | Yes |
| 2 | `rsi_mean_reversion` | Mean reversion, stateful (stop-loss, cooldown, BB/ADX confirmation) | `rsi_period` (14), `oversold` (30), `overbought` (70) | Yes |
| 3 | `momentum_breakout` | Breakout | `lookback` (20), `volume_surge_pct` (150), `rsi_min` (50) | Yes |
| 4 | `bollinger_breakout` | Volatility breakout | `bb_period` (20), `bb_std_dev` (2.0), `confirmation_bars` (2) | Yes |
| 5 | `vwap_reversion` | VWAP mean reversion | `vwap_period` (20), `deviation_threshold` (2.0) | No - needs an intraday timeframe AlphaLab can't fetch |
| 6 | `bollinger_rsi_combo` | Dual-confirmation mean reversion | `bb_period` (20), `rsi_oversold` (45), `rsi_overbought` (55) | Yes |
| 7 | `trend_adaptive_rsi` | Regime-adaptive RSI | `trend_sma` (50), separate up/down/range thresholds | Yes |
| 8 | `greenblatt_weekly` | Value factor, weekly bars | `fast_sma` (10w), `slow_sma` (50w), `min_hold_bars` (52w), `trailing_stop_pct` (0.20, a fraction of 20%) | Yes - see [Results](#results) for the point-in-time caveat |
| 9 | `rsi_simple` | Simple RSI mean reversion, no state machine | `period` (14), `oversold` (40), `overbought` (60) | No - research-only |

`greenblatt_weekly`'s `trailing_stop_pct` is AlphaLab's internal name; export translates it to the
contract's `trailing_stop_fraction`. `FundamentalScreener` (`POST /api/screener/greenblatt`) ranks
a universe by the true Greenblatt formula (earnings yield + return on capital) ahead of
`greenblatt_weekly`; see the caveats above before treating its output as validated.

**Selected API endpoints:** `/api/health`, `/api/data/fetch`, `/api/data/available`,
`/api/strategies/backtest`, `/api/strategies/optimize`, `/api/strategies/export`,
`/api/metrics/<id>`, `/api/compare`, `/api/screener/greenblatt` - schemas in
`backend/alphalab/api/blueprints/` and `docs/STRATEGY_SCHEMA.md`.

## Quick Start

**Prerequisites:** Python 3.10+, Node.js 18+ and npm. (The codebase uses `dict | None` union syntax
without `from __future__ import annotations`, which Python 3.9 can't parse.)

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py                          # http://127.0.0.1:5050

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                            # http://localhost:8080
```

Run a backtest:

```bash
curl -X POST http://127.0.0.1:5050/api/strategies/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL", "strategy": "rsi_mean_reversion",
    "start_date": "2020-01-01", "end_date": "2024-12-31",
    "params": {"rsi_period": 14, "oversold": 30, "overbought": 70}
  }'
```

Run walk-forward validation with the same shape against `/api/strategies/optimize`, adding
`"param_grid": {...}, "walk_forward": true, "n_folds": 3` - see
[Leakage-safe walk-forward optimization](#leakage-safe-walk-forward-optimization).

Export a deployable strategy (note the `backtest_id` from a prior backtest call):

```bash
curl -X POST http://127.0.0.1:5050/api/strategies/export \
  -H "Content-Type: application/json" \
  -d '{"backtest_id": "<backtest_id from above>"}'
```

`rsi_simple` and `vwap_reversion` return a 422 with an explanation instead of an export - see
[AlphaLive export contract and parity evidence](#alphalive-export-contract-and-parity-evidence).

## Verification

Run from the repository root, using subshells so each command's `cd` doesn't leak into the next:

```bash
(cd backend && source venv/bin/activate && pytest tests/ -v)   # 423 tests
(cd frontend && npm run test)                                   # 42 tests (Vitest)
(cd frontend && npm run lint)                                    # ESLint (convention, not CI-enforced)
```

Test count is a coverage indicator, not the headline result - the walk-forward methodology and
export-contract evidence above are. CI (`.github/workflows/ci.yml`) runs `black --check` and
`pytest`, plus a conditional AlphaLive checkout for the schema-contract test (see
[export contract and parity evidence](#alphalive-export-contract-and-parity-evidence)); no backend
lint step or frontend CI lint gate exists today.

## Deployment configuration

Both `backend/` and `frontend/` have a `Dockerfile` intended for Railway (backend via gunicorn
through `wsgi.py`, frontend as a static Vite build served by nginx, with `nginx.conf.template`
handling the SPA fallback and Railway's dynamic `$PORT`). `config.py` reads `PORT`, `HOST`, `DEBUG`,
and `ALLOWED_ORIGINS` env vars to override `backend/config.yaml`. These files are present and
internally consistent by static inspection, but the repository contains no committed container
smoke-test evidence or externally reachable deployment. Treat them as deployment configuration,
not as a runtime-verified service.

## Known limitations

- **No point-in-time fundamentals** - `FundamentalScreener` uses today's financials against
  historical prices, over a hand-picked present-day universe.
- **Cross-engine parity is diagnostic, not a measured percentage** - see
  [export contract and parity evidence](#alphalive-export-contract-and-parity-evidence).
- **`max_daily_loss_pct`, `max_open_positions`, and `commission_per_trade` aren't simulated here** -
  accepted and exported, taking effect only once running in AlphaLive.
- **The drawdown halt isn't a continuous, per-bar circuit breaker** - it runs only inside
  `execute_order()`, after a fill, so a price-driven drawdown can go undetected until the next order.
- **Only one of six Greenblatt regime windows has a committed result.**
- **Only three daily strategies have a walk-forward script (two SPY windows), and its output isn't
  committed**; `ma_crossover`, `momentum_breakout`, `bollinger_breakout` have none. No strategy here
  should be treated as ready for live capital.
- **No live deployment has run.**

## Documentation, license and disclaimer

- [`docs/STRATEGY_SCHEMA.md`](docs/STRATEGY_SCHEMA.md) - export-contract schema. Its "8 of the 9
  are deployable" line is stale: the export route rejects both `rsi_simple` and `vwap_reversion`
  (seven exportable, not eight); the export route and its strategy checks are authoritative for
  that count.
- `docs/MATH_EXPLAINER.md` repeats the broader Greenblatt claim (4 of 6 windows lost to
  diversification) as narrative, not backed by a committed six-window result - only the 2022 Bear
  window is committed (see [Results](#results)), so this README doesn't restate it as verified.

**Risk disclaimer:** these strategies are experimental research examples, not investment advice.
Performance figures are historical backtest results, not a forecast. Paper trading (via AlphaLive)
is the recommended way to evaluate any strategy before real capital.

**License:** all rights reserved, proprietary work - no license is granted for use, copying, or
redistribution. Not accepting external contributions; `backend/tests/` and
`frontend/src/**/*.test.ts(x)` are the best starting point for evaluating the code.
