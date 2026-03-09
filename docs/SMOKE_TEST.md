# AlphaLab Manual Smoke Test Checklist

**Purpose:** Manual UI testing checklist to verify all frontend features work correctly.

**Prerequisites:**
- Backend running on http://127.0.0.1:5000
- Frontend running on http://localhost:8080
- Fresh browser session (clear cache if needed)

---

## Dashboard Page

- [ ] Dashboard loads without errors
- [ ] Backend status indicator shows "Backend Online" (green dot)
- [ ] Recent backtests table displays (or shows "No backtests yet")
- [ ] Quick stats cards show placeholder or real data
- [ ] Cached tickers count displays
- [ ] Export icon appears in Actions column for past backtests
- [ ] Click export icon → JSON file downloads with correct filename

---

## Backtest Page - Single Backtest Tab

### Basic Configuration
- [ ] Single Backtest tab is active by default
- [ ] Ticker input accepts text (try "AAPL")
- [ ] Date range pickers work
- [ ] Interval selector shows 1d, 1h, 5m options
- [ ] Strategy selector shows all 5 strategies as radio cards

### Strategy Parameter Inputs
- [ ] Select MA Crossover → Short/Long window inputs appear
- [ ] Select RSI Mean Reversion → RSI period, oversold, overbought inputs appear
- [ ] Select Momentum Breakout → Lookback, volume surge inputs appear
- [ ] Select Bollinger Breakout → BB period, std dev, confirmation bars inputs appear
- [ ] Select VWAP Reversion → VWAP period, deviation threshold, RSI inputs appear

### Risk Settings Panel
- [ ] Risk Settings accordion expands/collapses
- [ ] Stop Loss % slider works (0.1-50 range)
- [ ] Take Profit % slider works (0.5-100 range)
- [ ] Max Position Size % slider works (1-100 range)
- [ ] Max Daily Loss % slider works (0.5-20 range)
- [ ] Max Open Positions slider works (1-50 range)
- [ ] Trailing Stop toggle works
- [ ] Trailing Stop % input appears when toggle is ON
- [ ] Commission per Trade input accepts numbers (0-50 range)

### Advanced Settings
- [ ] Initial Capital input works
- [ ] Position Sizing selector shows options
- [ ] Monte Carlo runs input accepts numbers

### Run Backtest & Results
- [ ] Click "Run Backtest" → Loading spinner appears
- [ ] Results summary card displays after completion
- [ ] Equity Curve tab shows line chart with benchmark
- [ ] Drawdown tab shows red filled area chart
- [ ] Monthly Returns tab shows heatmap grid (green/red cells)
- [ ] Trade Log tab shows sortable table
- [ ] Detailed Metrics tabs display (Returns, Risk, Drawdown, etc.)
- [ ] Export to AlphaLive button appears
- [ ] Click Export → JSON file downloads with correct filename

---

## Backtest Page - Batch Backtest Tab

- [ ] Batch Backtest tab switches view
- [ ] Multi-select ticker input works
- [ ] Quick select buttons add tickers (Tech, Finance, etc.)
- [ ] Strategy selector shows all 5 strategies
- [ ] Click "Run Batch Backtest" → Progress indicator shows
- [ ] Progress shows "Testing AAPL... (1/3)" format
- [ ] Batch Summary card displays after completion
- [ ] Results table shows all tested tickers
- [ ] Results sorted by Sharpe ratio (descending)
- [ ] Table columns: ticker, return %, Sharpe, max DD, win rate, trades
- [ ] Failed tickers show error messages if any
- [ ] Export Top 5 button appears if >5 results
- [ ] Click Export Top 5 → JSON file downloads

---

## Compare Page

### Strategy Comparison
- [ ] Compare page loads
- [ ] Ticker input works
- [ ] Date range pickers work
- [ ] Strategy checkboxes allow 2-3 selections
- [ ] Click "Compare Strategies" → Loading spinner
- [ ] Best Strategy Summary card displays winner on each metric
- [ ] Overall recommendation shows (based on Sharpe)
- [ ] Disclaimer text displays

### Visualizations
- [ ] Overlay Equity Curve shows all strategies on one chart
- [ ] Chart normalized to % returns (all start at 0%)
- [ ] Buy-and-hold benchmark shows (dashed gray line)
- [ ] Legend shows color-coded strategies (colorblind-friendly palette)
- [ ] Correlation Matrix heatmap displays
- [ ] Matrix shows pairwise correlations (-1 to +1)
- [ ] Color scale: red (negative) → gray (0) → blue (positive)
- [ ] Comparison table shows side-by-side metrics
- [ ] Radar chart displays (if implemented)

### Portfolio Optimization
- [ ] "Optimize Portfolio" button appears after comparison
- [ ] Click button → Portfolio page opens with strategies pre-loaded
- [ ] Optimization method selector works (Max Sharpe, Min Variance, etc.)
- [ ] Constraint sliders work (max weight, min weight)
- [ ] Click "Optimize" → Results display
- [ ] Portfolio Metrics card shows expected return, risk, Sharpe
- [ ] Optimal Weights table shows allocation percentages
- [ ] Pie chart shows visual weight distribution
- [ ] Efficient Frontier chart displays (scatter plot)
- [ ] Green star marks optimal portfolio on frontier

---

## Data Manager Page

- [ ] Data Manager page loads
- [ ] Cached tickers table displays
- [ ] Table shows ticker, rows, start/end dates, quality score
- [ ] Fetch data form works (ticker input, date pickers)
- [ ] Click "Fetch Data" → Loading spinner
- [ ] New ticker appears in table after fetch
- [ ] Quality score shows color-coded indicator

---

## Settings Page

### Telegram Settings
- [ ] Telegram section displays
- [ ] Bot token status shows "Configured" or "Not set"
- [ ] Enable notifications toggle works
- [ ] Alert toggles work (trades, daily summary, errors, drawdown, signals)
- [ ] Drawdown threshold slider works (0.1-50% range)
- [ ] Current value displays next to slider
- [ ] Test Connection button appears
- [ ] Click Test Connection → Success or error toast displays

### Alpaca Settings
- [ ] Alpaca section displays
- [ ] API key status shows "Configured" or "Not set"
- [ ] Secret key status shows "Configured" or "Not set"
- [ ] Paper trading toggle works
- [ ] Warning badge appears when paper trading is OFF
- [ ] Test Connection button appears
- [ ] Click Test Connection → Account details display (status, buying power)

### Help Panel
- [ ] Help accordion expands/collapses
- [ ] Telegram bot setup instructions display (@BotFather steps)
- [ ] Chat ID instructions display (@userinfobot)
- [ ] Alpaca account creation steps display
- [ ] .env file configuration example shows
- [ ] Security notes display
- [ ] External links work (Telegram docs, Alpaca docs)

---

## Navigation & Header

- [ ] Header displays on all pages
- [ ] AlphaLab logo and Activity icon show
- [ ] Nav items: Dashboard, Backtest, Compare, Data, Portfolio, Settings
- [ ] Active page highlighted (primary color background)
- [ ] Backend status indicator shows in top-right
- [ ] Status updates when backend goes offline/online

---

## General UI/UX

- [ ] Dark theme applied consistently
- [ ] All buttons respond to hover (color change)
- [ ] Loading spinners show during API calls
- [ ] Error toasts display for failed requests
- [ ] Success toasts display for successful actions
- [ ] All charts are responsive (resize window)
- [ ] No console errors in browser DevTools
- [ ] All forms validate inputs (show error messages)
- [ ] Date pickers prevent invalid date ranges

---

## Performance Checks

- [ ] Initial page load < 2 seconds
- [ ] Navigation between pages is instant
- [ ] Backtest completes in < 5 seconds (for 1 ticker, 1000 days)
- [ ] Batch backtest shows progress (not frozen UI)
- [ ] Charts render smoothly (no lag when hovering)
- [ ] Large trade tables scroll smoothly

---

## Edge Cases

- [ ] Run backtest with no risk settings changed → Uses defaults
- [ ] Run backtest with stop-loss > take-profit → Shows warning
- [ ] Run batch with 20 tickers → All complete successfully
- [ ] Compare 3 strategies with identical params → Results differ slightly
- [ ] Optimize portfolio with 2 strategies → Weights sum to 1.0
- [ ] Save settings with missing API keys → Only saves non-sensitive data
- [ ] Load page with backend offline → Shows "Backend Offline" indicator
- [ ] Fetch data with invalid date range → Error message displays

---

## Test Data Recommendations

**Tickers to test:**
- Large cap: AAPL, MSFT, GOOGL
- Volatile: TSLA, GME
- Stable: JNJ, PG
- ETF: SPY, QQQ

**Date ranges to test:**
- Short: 2023-01-01 to 2023-12-31 (1 year)
- Medium: 2020-01-01 to 2024-12-31 (5 years)
- Long: 2015-01-01 to 2024-12-31 (10 years)

**Strategies to test:**
- Trending market: MA Crossover, Momentum Breakout
- Choppy market: RSI Mean Reversion, Bollinger Breakout
- High volume: VWAP Reversion

---

## Notes

- If a test fails, note the error message and browser console output
- Some strategies may produce 0 trades for certain tickers (this is valid)
- Backend logs are in `backend/logs/alphalab.log`
- Frontend state is in localStorage (key: `alphalab_backtest_history`)
- Clear localStorage to reset backtest history: `localStorage.clear()`

---

**Test Date:** _______________
**Tester:** _______________
**Passed:** _____ / 100+
**Failed:** _____ (list below)

**Failures:**
1.
2.
3.
