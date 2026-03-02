# Troubleshooting

## Common Issues

### "ModuleNotFoundError: No module named 'src'"

You're running from the wrong directory or the virtualenv isn't activated.

```bash
cd backend
source venv/bin/activate
python run.py
```

### yfinance download fails or returns empty data

**Possible causes:**
- Invalid ticker symbol — check it exists on Yahoo Finance
- Network issue — check your internet connection
- Rate limit hit — yfinance allows ~2000 requests/hour; wait and retry
- Date range too old — some tickers don't have data before their IPO

**Fix:** The DataFetcher retries 3 times with exponential backoff. If it still fails, check the ticker on `finance.yahoo.com` manually.

### Feature engineering produces all NaN values

**Cause:** Not enough data for the lookback period. A 200-day SMA needs at least 200 data points.

**Fix:** Fetch at least 1 year of daily data (252+ rows). For all indicators to be populated, fetch 2+ years.

### Backtest returns 0 trades

**Possible causes:**
- Strategy signals were generated but execution failed (insufficient funds, position limits)
- Data doesn't have the required feature columns
- Date range is too short for the strategy's parameters

**Debug:** Check `backend/logs/alphalab.log` for warnings about rejected orders or missing columns.

### API returns 500 Internal Server Error

**Debug:**
1. Check `backend/logs/alphalab.log` for the stack trace
2. Enable debug logging in `config.yaml`: set `logging.level` to `DEBUG`
3. Run Flask in debug mode: set `app.debug` to `true` in `config.yaml`

### Data quality score too low (< 0.9)

The DataValidator rejected the data. Common causes:
- Many missing trading days (stock was halted or delisted)
- Extreme price movements flagged as outliers (could be legitimate, e.g., biotech stocks)
- Corrupt data from Yahoo Finance

**Fix:** Try a different date range or check if the stock had unusual events during that period.

### Negative Sharpe ratio

Not a bug — the strategy lost money on a risk-adjusted basis. Check:
- Is the total return negative?
- Is volatility very high relative to returns?
- Try different strategy parameters or a different stock

### Memory usage is high

Each stock with 5 years of daily data and 50+ features uses ~5-10MB. For 20 stocks, expect ~100-200MB.

**Reduce memory:**
- Process fewer stocks at once
- Use shorter date ranges
- Clear the cache periodically

## Enabling Debug Logging

Edit `backend/config.yaml`:

```yaml
logging:
  level: "DEBUG"
```

Restart the server. Debug logs include every data fetch, signal generation, and order execution.

## Resetting Cache

Delete all cached data:

```bash
rm -rf backend/data/cache/*
```

Or use the cache manager to clear expired entries — this happens automatically on fetch.

## Running a Single Test

```bash
cd backend
source venv/bin/activate
pytest tests/test_metrics.py -v                    # One file
pytest tests/test_strategies.py -k "test_cooldown"  # One test
pytest tests/ -v --tb=long                          # Verbose errors
```

## FAQ

**Q: Can I use this for real trading?**
A: AlphaLab is designed for backtesting and research. Real trading has additional complexities (order book dynamics, real-time data, broker APIs) not modeled here. Results should be treated as educational.

**Q: Why is TA-Lib not used?**
A: The Python `ta-lib` package requires a system-level C library that's difficult to install on some platforms. AlphaLab uses manual implementations and `stockstats` instead. Results are equivalent for the indicators implemented.

**Q: Can I add crypto/forex data?**
A: yfinance supports some crypto (e.g., `BTC-USD`) and forex pairs. The system hasn't been tested extensively with these, but the data pipeline should work. Feature engineering may need adjustment for 24/7 markets.

**Q: How do I add a custom strategy?**
A: See `docs/STRATEGIES.md` for step-by-step instructions. Create a new file in `strategies/implementations/`, inherit from `BaseStrategy`, and implement the required methods.
