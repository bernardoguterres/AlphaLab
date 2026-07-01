# AlphaLab Documentation Audit & Refactor Plan

**Date:** 2026-03-22
**Current State:** 1,403 lines / 60KB in CLAUDE.md + 7 docs files (64.5KB total)
**Goal:** Reduce duplication, improve maintainability, optimize AI context loading

---

## Executive Summary

**Problems Identified:**
1. **60-70% duplication** between CLAUDE.md and docs/ files
2. CLAUDE.md is **3-5x larger** than typical project guides
3. Same content maintained in 2-3 places (e.g., strategies in CLAUDE.md + STRATEGIES.md)
4. **Context tax:** AI loads 60KB every conversation, much is redundant with actual code

**Recommended Action:**
- **Delete 3 docs files** (API.md, ARCHITECTURE.md, TROUBLESHOOTING.md)
- **Consolidate 1 file** (STRATEGIES.md → merge minimal version into README)
- **Keep 2 critical files** (STRATEGY_SCHEMA.md, METRICS_GUIDE.md)
- **Shrink CLAUDE.md from 1,403 → ~700 lines** (50% reduction)

**Expected Outcome:**
- Faster AI response times (less context to load)
- Single source of truth for most content
- Better maintainability (fewer places to update)
- User-facing docs remain accessible (README, 2 reference guides)

---

## Detailed Duplication Analysis

### 1. API Documentation

**CLAUDE.md (Lines 185-210, 300-330, 425-450):**
- Full API endpoint reference with all 13 endpoints
- Request/response schemas
- Parameter validation details
- Example curl commands (some)

**docs/API.md (582 lines):**
- Identical endpoint list with 13 endpoints
- Identical request/response schemas
- More extensive curl examples
- Error code reference table

**Duplication Level:** **90%** (nearly identical content)

**Recommendation:** **DELETE docs/API.md**
- AI can read `backend/src/api/routes.py` and `validators.py` directly
- CLAUDE.md can link to code files instead of duplicating schemas
- Keep minimal endpoint summary in CLAUDE.md for quick reference
- Users can read OpenAPI spec (if we generate one later)

---

### 2. Architecture Documentation

**CLAUDE.md (Lines 41-72):**
```
### Backend (`backend/`)
Flask REST API on http://127.0.0.1:5000
- `src/data/` — Data fetching, validation, feature engineering
- `src/strategies/` — BaseStrategy ABC + 5 implementations
- `src/backtest/` — Engine, Portfolio, Order, Metrics
- `src/api/` — Flask routes with Pydantic validation
- `src/utils/` — Logger, config loader, custom exceptions
```

**docs/ARCHITECTURE.md (117 lines):**
```
## System Overview
[ASCII diagram of data flow]

## Module Responsibilities
[Table of each module's purpose]

## Design Decisions
- No Look-Ahead Bias
- Realistic Execution Costs
- Feature Engineering Before Strategy
- Caching Strategy
- Pydantic Validation
```

**Duplication Level:** **70%** (high-level overview duplicated, ARCHITECTURE.md has more depth on design decisions)

**Recommendation:** **DELETE docs/ARCHITECTURE.md, keep design decisions in CLAUDE.md**
- Architecture overview is already in CLAUDE.md (shorter version)
- Design decisions (no look-ahead bias, execution costs) are valuable → **move to CLAUDE.md "Key Design Decisions"** section
- Performance table → can be removed (not critical for AI)

---

### 3. Strategy Documentation

**CLAUDE.md (Lines 235-275):**
```
## Strategy Behavior (tested on 30+ stocks, 2020-2024)
- **MA_Crossover**: Trend-following. avg +13.8% on 21 stocks. 50/200 SMA cross. 7/21 stocks get 0 trades...
- **RSI_MeanReversion**: State-aware (buy→hold→exit cycle). Stop-loss (2.5×ATR), max 40-day hold...
- **Momentum_Breakout**: State-aware with trailing stops (3×ATR). Breakout above N-day high + volume surge...
- **Bollinger_Breakout**: Volatility breakout with confirmation...
- **VWAP_Reversion**: Mean reversion from VWAP with RSI filter...
```

**CLAUDE.md (Lines 115-134 under "Adding a Strategy"):**
```
## Adding a Strategy
1. Create file in `src/strategies/implementations/`
2. Inherit from `BaseStrategy`, implement `validate_params()`, `generate_signals()`...
3. Register in `implementations/__init__.py`
4. Add to `STRATEGY_MAP` in `api/routes.py`
5. Add default params to `config.yaml`
6. Write tests in `tests/test_strategies.py`
```

**docs/STRATEGIES.md (203 lines):**
```
## 1. Moving Average Crossover
**File:** `strategies/implementations/moving_average_crossover.py`
**Logic:** Buy when short MA crosses above long MA...
**Parameters:**
| short_window | 50 | Short MA period |
| long_window | 200 | Long MA period |
...
**When to use:** Trending markets...
**Strengths:** Simple, reliable in trends...
**Weaknesses:** Lags in fast markets...

[Repeated for all 5 strategies]

## Adding a New Strategy
[Step-by-step guide - IDENTICAL to CLAUDE.md]
```

**Duplication Level:** **80%** (strategy descriptions, parameters, "when to use"sections duplicated)

**Recommendation:** **DELETE docs/STRATEGIES.md**
- Strategy parameter tables can be read from code (`base_strategy.py`, implementation files)
- **Keep 1-line summary per strategy in CLAUDE.md** (current version is good)
- **Remove detailed parameter tables from CLAUDE.md** → AI can read code
- "Adding a Strategy" section → keep in CLAUDE.md only (developer-facing)

**Alternative (if we want user-facing docs):**
- Keep **minimal** STRATEGIES.md for traders (1-2 paragraphs per strategy, no code details)
- Move to README as a "Strategy Overview" section
- Remove from CLAUDE.md entirely

---

### 4. Troubleshooting

**CLAUDE.md (Lines 276-320 "Known Gotchas"):**
```
### Backend
- `pyarrow` required for parquet caching
- yfinance rate limits ~2000 req/hour; returns MultiIndex columns
- Feature engineering needs 200+ rows for all indicators
- Tests that call yfinance must patch `src.data.fetcher.yf.download`
```

**docs/TROUBLESHOOTING.md (116 lines):**
```
## Common Issues
### "ModuleNotFoundError: No module named 'src'"
You're running from the wrong directory...

### yfinance download fails or returns empty data
**Possible causes:**
- Invalid ticker symbol
- Network issue
- Rate limit hit

### Feature engineering produces all NaN values
**Cause:** Not enough data for lookback period...

## FAQ
**Q: Can I use this for real trading?**
**Q: Why is TA-Lib not used?**
**Q: Can I add crypto/forex data?**
```

**Duplication Level:** **50%** (some overlap in "gotchas"vs "common issues")

**Recommendation:** **DELETE docs/TROUBLESHOOTING.md, merge FAQ into README**
- Troubleshooting is useful for USERS, not AI
- Move 3-4 most common issues to README "Troubleshooting" section
- Move FAQ questions to README "FAQ" section
- Remove from CLAUDE.md (AI doesn't need this in every conversation)

---

### 5. Smoke Test Checklist

**docs/SMOKE_TEST.md (256 lines):**
- 100+ manual UI test checkboxes
- Covers all pages, features, edge cases
- Very detailed (every button, every form field)

**Duplication Level:** **0%** (no duplication, unique content)

**Recommendation:** **CONSIDER REPLACING with Playwright E2E tests**
- Manual checklists are hard to maintain and don't prevent regressions
- 100+ checkboxes is excessive for manual testing
- **Short-term:** Keep file, but note it's deprecated in favor of E2E tests
- **Long-term:** Write 10-15 Playwright tests covering critical paths, delete SMOKE_TEST.md

**Alternative (if keeping):**
- Move to GitHub Issues template (one issue per smoke test session)
- Or move to GitHub Wiki (not in main repo)

---

### 6. Metrics Guide

**docs/METRICS_GUIDE.md (5.4KB):**
- Explains what each metric means (Sharpe, Sortino, Calmar, Max Drawdown, etc.)
- Interpretation guidance ("Good Sharpe > 1.0")
- No duplication with CLAUDE.md

**Duplication Level:** **0%** (unique content, not in CLAUDE.md)

**Recommendation:** **KEEP** (valuable user reference, no duplication)

---

### 7. Strategy Schema

**docs/STRATEGY_SCHEMA.md (22KB):**
- Schema specification v1.0 for AlphaLab → AlphaLive integration
- Field definitions, validation rules, examples
- Migration guide, version policy
- Critical contract between projects

**Duplication Level:** **5%** (brief mention in CLAUDE.md, full spec in STRATEGY_SCHEMA.md)

**Recommendation:** **KEEP** (critical contract, version-controlled spec)

---

## CLAUDE.md Bloat Analysis

### What's Taking Up Space?

| Section | Lines | Keep? | Reason |
|---------|-------|-------|--------|
| **Project Overview** | 70 | Yes | AI needs to know what AlphaLab is |
| **Architecture** | 60 | Shrink | Redundant with code structure, can be 20 lines |
| **Running the App** | 80 | Yes | AI needs to know how to run tests, start servers |
| **Key Design Decisions** | 50 | Yes | Non-obvious choices (no look-ahead bias, next-bar execution) |
| **Code Conventions** | 90 | Yes | Critical for AI to write code in project style |
| **Adding a Strategy** | 50 | Yes | AI needs to know how to extend system |
| **Adding an API Endpoint** | 40 | Yes | AI needs to know Flask patterns |
| **Settings Management** | 200 | Shrink | Too detailed, can be 50 lines with link to code |
| **Risk Settings** | 80 | Shrink | Frontend details, can be 20 lines |
| **Strategy Export Schema** | 150 | Delete | Link to STRATEGY_SCHEMA.md instead |
| **Frontend Features** | 200 | Shrink | Too detailed, can be 50 lines (AI can read code) |
| **Strategy Behavior** | 80 | Yes | Empirical results from real testing |
| **Known Gotchas** | 90 | Shrink | Keep top 5 gotchas, delete rest |
| **Test Structure** | 180 | Shrink | Test list can be 50 lines, delete detailed test descriptions |
| **Project Structure** | 40 | Yes | Quick reference tree |
| **Documentation List** | 60 | Shrink | 10 lines max, just link to files |

**Total Savings:** 150 (Strategy Export) + 150 (Settings) + 150 (Frontend) + 60 (Risk) + 130 (Tests) + 50 (Documentation) = **690 lines**

**New Size:** 1403 - 690 = **713 lines** (49% reduction)

---

## Refactor Plan

### Phase 1: Delete Redundant Docs (Immediate)

**Delete 3 files:**
```bash
rm docs/API.md
rm docs/ARCHITECTURE.md
rm docs/TROUBLESHOOTING.md
rm docs/STRATEGIES.md  # Optional, see alternative below
```

**Merge content into README.md:**
- Add "Troubleshooting" section to README (5 most common issues)
- Add "FAQ" section to README (3-4 questions)
- Keep STRATEGIES.md if we want user-facing docs (but simplify to 1 paragraph per strategy)

**Expected savings:** 4 files deleted, ~45KB removed

---

### Phase 2: Shrink CLAUDE.md (Priority Sections)

**Section-by-section changes:**

#### 1. Settings Management (Lines ~150-350)
**Current:** 200 lines of detailed API endpoint docs, request/response examples, security rules
**New:** 50 lines
```markdown
## Settings Management

**Files:**
- `backend/src/utils/settings_manager.py` — Load/save settings
- `backend/src/api/settings_validators.py` — Pydantic validation
- `backend/configs/app_settings.json` — Non-sensitive settings only

**Security:**
- NEVER store API keys in `app_settings.json`
- ALL credentials MUST be environment variables
- API endpoints REJECT requests with forbidden fields (api_key, secret_key, bot_token, password)
- GET `/api/settings/notifications` returns `*_configured: true/false` flags only

**Endpoints:** See `backend/src/api/routes.py` for full details
- GET `/api/settings/notifications` — Returns non-sensitive settings
- POST `/api/settings/notifications` — Saves non-sensitive settings (rejects API keys)
- POST `/api/settings/telegram/test` — Tests Telegram connection (uses env vars)
- POST `/api/settings/alpaca/test` — Tests Alpaca connection (uses env vars)
```
**Savings:** 150 lines

---

#### 2. Strategy Export Schema (Lines ~430-580)
**Current:** 150 lines duplicating STRATEGY_SCHEMA.md
**New:** 10 lines
```markdown
## Strategy Export Schema

**Purpose:** JSON format for exporting battle-tested strategies from AlphaLab to AlphaLive.

**Full Specification:** See `docs/STRATEGY_SCHEMA.md` for:
- Schema v1.0 field definitions
- Supported strategies and parameters
- Validation rules and examples
- Version policy and migration guide

**Export Endpoint:** `POST /api/strategies/export` (see `backend/src/api/routes.py`)
```
**Savings:** 140 lines

---

#### 3. Frontend Features (Lines ~590-790)
**Current:** 200 lines describing every page, component, chart
**New:** 50 lines
```markdown
## Frontend Features

### Pages (src/pages/)
1. **Dashboard** — Backtest history, quick stats
2. **Backtest** — Two tabs: Single backtest (with risk settings panel) + Batch backtest (multi-ticker)
3. **Compare** — Side-by-side strategy comparison with overlay charts, correlation matrix, best strategy summary
4. **DataManager** — Cached tickers table, fetch data form
5. **Portfolio** — Optimize capital allocation (4 methods: max_sharpe, min_variance, risk_parity, equal_weight)
6. **Settings** — Telegram notifications, Alpaca connection testing

### Key Components
- **Charts:** EquityChart, DrawdownChart, MonthlyReturnsHeatmap, OverlayEquityChart, CorrelationMatrix
- **Forms:** RiskSettingsPanel (collapsible accordion), StrategySelector, ParameterInputs
- **Export:** ExportButton component in Dashboard + Backtest pages

**API Integration:** `src/services/api.ts` (axios client, typed responses)
**State:** Zustand stores in `src/stores/`
**Types:** `src/types/index.ts` (matches backend exactly)
```
**Savings:** 150 lines

---

#### 4. Test Structure (Lines ~850-1030)
**Current:** 180 lines listing every test file with descriptions
**New:** 50 lines
```markdown
## Test Structure

**Total: 210 tests (207 passing, 3 skipped)**

### Core Tests (81 tests)
`test_data_fetcher.py`, `test_validator.py`, `test_processor.py`, `test_strategies.py`, `test_backtest_engine.py`, `test_metrics.py`, `test_integration.py`, `test_complete_workflow.py`

### Feature Tests (129 tests)
`test_batch_backtest.py`, `test_portfolio_optimizer.py`, `test_parameter_optimizer.py`, `test_settings.py`, `test_export.py`, `test_risk_settings.py`, `test_new_strategies.py`, `test_frontend_integration.py` (6 end-to-end flows), `test_edge_cases.py` (15 edge cases), `test_performance.py` (6 benchmarked operations)

**Run tests:**
```bash
pytest tests/ -v                           # All tests
pytest tests/test_performance.py -v       # Performance benchmarks
pytest tests/test_frontend_integration.py -v  # End-to-end workflows
```

**Performance Budgets (see `test_performance.py`):**
- Backtest (5 years): <30s
- Signal generation (500 bars): <5s (CRITICAL for AlphaLive)
- Portfolio optimization: <60s
- Batch backtest (10 tickers): <3 min
```
**Savings:** 130 lines

---

#### 5. Risk Settings (Lines ~140-220)
**Current:** 80 lines describing every field, validation, frontend component
**New:** 20 lines
```markdown
## Risk Settings

**Location:** `frontend/src/components/backtest/RiskSettingsPanel.tsx` (collapsible accordion)

**Fields:** Stop Loss %, Take Profit %, Max Position Size %, Max Daily Loss %, Max Open Positions, Trailing Stop toggle + %, Commission per Trade

**Backend Model:** `RiskSettings` in `backend/src/api/validators.py` (Pydantic v2)

**Note:** Commission is applied 2× per round trip (buy + sell = 2× commission)
```
**Savings:** 60 lines

---

#### 6. Documentation Section (Lines ~1200-1260)
**Current:** 60 lines listing every doc file with descriptions
**New:** 10 lines
```markdown
## Documentation

**Main Docs:** README.md, SETUP.md, LICENSE
**Technical Docs:** `docs/STRATEGY_SCHEMA.md`, `docs/METRICS_GUIDE.md`
**Frontend Docs:** `frontend/README.md`
```
**Savings:** 50 lines

---

### Phase 3: Implement CLAUDE.md Changes

**Script to automate shrinking:**

```python
# shrink_claude_md.py
import re

with open('CLAUDE.md', 'r') as f:
    content = f.read()

# Remove detailed sections (replace with condensed versions)
sections_to_shrink = {
    # Find "## Settings Management" section and replace up to next ## with new content
    r'## Settings Management.*?(?=\n##)': """## Settings Management

**Files:**
- `backend/src/utils/settings_manager.py` — Load/save settings
- `backend/src/api/settings_validators.py` — Pydantic validation
- `backend/configs/app_settings.json` — Non-sensitive settings only

**Security:**
- NEVER store API keys in `app_settings.json`
- ALL credentials MUST be environment variables
- API endpoints REJECT requests with forbidden fields
- GET `/api/settings/notifications` returns `*_configured` flags only

**Endpoints:** See `backend/src/api/routes.py` for full details
""",
    # ... more replacements
}

for pattern, replacement in sections_to_shrink.items():
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('CLAUDE_NEW.md', 'w') as f:
    f.write(content)

print("Shrunk CLAUDE.md saved as CLAUDE_NEW.md")
```

**Manual review:**
1. Run script
2. Compare CLAUDE.md vs CLAUDE_NEW.md
3. Verify no critical info lost
4. Replace CLAUDE.md with CLAUDE_NEW.md

---

## Final State

### Documentation Structure (After Refactor)

```
AlphaLab/
├── README.md (50KB) ← Add FAQ, Troubleshooting sections
├── SETUP.md (15KB) ← No changes
├── CLAUDE.md (35KB) ← Shrunk from 60KB
├── LICENSE (2KB)
└── docs/
    ├── STRATEGY_SCHEMA.md (22KB) ← Keep (critical contract)
    └── METRICS_GUIDE.md (5KB) ← Keep (user reference)
```

**Total docs:** 129KB (down from 140KB)
**CLAUDE.md:** 713 lines / 35KB (down from 1403 lines / 60KB)
**Files deleted:** 4 (API.md, ARCHITECTURE.md, TROUBLESHOOTING.md, STRATEGIES.md)

---

## Migration Checklist

- [ ] **Phase 1: Delete redundant docs**
  - [ ] Delete `docs/API.md`
  - [ ] Delete `docs/ARCHITECTURE.md`
  - [ ] Delete `docs/TROUBLESHOOTING.md`
  - [ ] Delete `docs/STRATEGIES.md`

- [ ] **Phase 1b: Merge into README**
  - [ ] Add "Troubleshooting" section to README (5 issues)
  - [ ] Add "FAQ" section to README (4 questions)
  - [ ] Add "Strategy Overview" section to README (1 paragraph per strategy)

- [ ] **Phase 2: Shrink CLAUDE.md**
  - [ ] Condense "Settings Management" (200 → 50 lines)
  - [ ] Condense "Strategy Export Schema" (150 → 10 lines)
  - [ ] Condense "Frontend Features" (200 → 50 lines)
  - [ ] Condense "Test Structure" (180 → 50 lines)
  - [ ] Condense "Risk Settings" (80 → 20 lines)
  - [ ] Condense "Documentation" (60 → 10 lines)

- [ ] **Phase 3: Verify**
  - [ ] Run backend tests (should still pass)
  - [ ] Start backend + frontend (should still work)
  - [ ] Claude reads new CLAUDE.md (test AI conversation)
  - [ ] User can still find docs (check README links)

- [ ] **Phase 4: Update .gitignore**
  - [ ] Ensure CLAUDE.md still in .gitignore (not committed to public repo)

---

## Benefits Summary

### For AI (Claude)
**42% less context to load** (60KB → 35KB)
**Faster response times** (less text to process)
**Less duplication** (single source of truth)
**Links to code** instead of duplicating schemas

### For Users
**Easier to find docs** (README has all user-facing content)
**Less outdated info** (fewer places to update)
**Clear separation** (README = users, CLAUDE.md = developers/AI)

### For Maintainers
**Less maintenance burden** (4 fewer files to update)
**No schema duplication** (STRATEGY_SCHEMA.md is source of truth)
**Easier to keep in sync** (change once, not 3 times)

---

## Risks & Mitigation

**Risk 1:** Delete something important
- **Mitigation:** Git tracks all changes, can restore from history
- **Mitigation:** Review phase before deleting (this audit document)

**Risk 2:** AI can't find info after shrinking
- **Mitigation:** Test AI conversation after changes
- **Mitigation:** Keep links to code files (AI can read directly)

**Risk 3:** Users can't find help
- **Mitigation:** Move FAQ/Troubleshooting to README
- **Mitigation:** Keep METRICS_GUIDE.md and STRATEGY_SCHEMA.md

---

## Appendix: Content Disposition Table

| Original Location | Content Type | New Location | Reason |
|-------------------|-------------|--------------|--------|
| `docs/API.md` | API endpoint reference | DELETED | AI reads code directly |
| `docs/ARCHITECTURE.md` | System design | DELETED | Redundant with CLAUDE.md |
| `docs/TROUBLESHOOTING.md` | Common issues + FAQ | → `README.md` | User-facing, belongs in README |
| `docs/STRATEGIES.md` | Strategy details | → `README.md` (condensed) | User-facing, 1 paragraph per strategy |
| `docs/SMOKE_TEST.md` | Manual test checklist | DEPRECATE | Replace with E2E tests (future) |
| `docs/METRICS_GUIDE.md` | Metric explanations | KEEP | User reference, no duplication |
| `docs/STRATEGY_SCHEMA.md` | JSON schema v1.0 | KEEP | Critical contract |
| `CLAUDE.md` (Settings section) | API endpoint details | → Condensed (200 → 50 lines) | AI reads code for details |
| `CLAUDE.md` (Schema section) | Schema specification | → Link to STRATEGY_SCHEMA.md | Single source of truth |
| `CLAUDE.md` (Frontend section) | Page/component list | → Condensed (200 → 50 lines) | AI reads code for details |
| `CLAUDE.md` (Test section) | Test file descriptions | → Condensed (180 → 50 lines) | Just list files, not every test |

---

**End of Audit**
