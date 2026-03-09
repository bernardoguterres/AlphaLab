# AlphaLab Trading Strategies

## Overview

All strategies inherit from `BaseStrategy` and implement:
- `validate_params()` — Verify parameter validity
- `generate_signals(data)` — Produce buy/sell/hold signals
- `required_columns()` — List DataFrame columns needed

Signals are generated at each bar's close and executed on the next bar's open.

---

## 1. Moving Average Crossover

**File:** `strategies/implementations/moving_average_crossover.py`

**Logic:** Buy when a short-period moving average crosses above a long-period moving average (Golden Cross). Sell on the reverse (Death Cross).

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `short_window` | 50 | Short MA period |
| `long_window` | 200 | Long MA period |
| `volume_confirmation` | true | Only signal if volume > 20-day average |
| `volume_avg_period` | 20 | Period for volume average |
| `min_separation_pct` | 1.0 | MAs must be at least 1% apart to signal |
| `cooldown_days` | 5 | Minimum days between signals |

**When to use:**
- Trending markets with sustained directional moves
- Longer timeframes (daily/weekly)
- Stocks with clear trend behavior

**Strengths:** Simple, reliable in strong trends, few false signals with filters.
**Weaknesses:** Lags in fast-moving markets, poor in sideways/choppy conditions.

---

## 2. RSI Mean Reversion

**File:** `strategies/implementations/rsi_mean_reversion.py`

**Logic:** Buy when RSI drops below the oversold threshold (price likely to bounce). Sell when RSI rises above the overbought threshold. Bollinger Band and ADX filters reduce false signals.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rsi_period` | 14 | RSI calculation period |
| `oversold` | 30 | RSI level to trigger buy |
| `overbought` | 70 | RSI level to trigger sell |
| `use_bb_confirmation` | true | Require price to touch Bollinger Band |
| `use_adx_filter` | true | Only trade when ADX indicates trending |
| `adx_threshold` | 25 | Minimum ADX for trend confirmation |
| `cooldown_days` | 3 | Minimum days between signals |

**When to use:**
- Range-bound or mean-reverting stocks
- Markets with regular oscillation patterns
- Combined with other indicators for confirmation

**Strengths:** Catches reversals early, works well in oscillating markets.
**Weaknesses:** Dangerous in strong trends (RSI can stay oversold/overbought for extended periods).

---

## 3. Momentum Breakout

**File:** `strategies/implementations/momentum_breakout.py`

**Logic:** Buy when price breaks above the N-day high with a volume surge (>150% of average) and RSI confirms upward momentum. Sell when price breaks below the N-day low. Uses ATR-based stop losses.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lookback` | 20 | Period for high/low breakout detection |
| `volume_surge_pct` | 150 | Required volume as % of average |
| `volume_avg_period` | 20 | Period for volume average |
| `rsi_min` | 50 | Minimum RSI for buy signal (confirms momentum) |
| `stop_loss_atr_mult` | 2.0 | Stop loss distance in ATR multiples |
| `cooldown_days` | 5 | Minimum days between signals |

**When to use:**
- Volatile stocks with potential for large moves
- Breakout patterns after consolidation
- Markets with strong volume-price relationships

**Strengths:** Captures large moves early, built-in risk management with ATR stops.
**Weaknesses:** Many false breakouts in choppy markets, requires strong volume for confirmation.

---

## 4. Bollinger Band Breakout

**File:** `strategies/implementations/bollinger_breakout.py`

**Logic:** Buy when price closes above the upper Bollinger Band for N consecutive bars with volume confirmation. Sell when price closes below the lower band. Exit positions when price returns to the middle band (SMA). Designed to catch strong directional moves that break out of normal volatility ranges.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bb_period` | 20 | Period for Bollinger Band calculation (SMA) |
| `bb_std_dev` | 2.0 | Standard deviation multiplier for bands |
| `confirmation_bars` | 2 | Consecutive closes outside bands required |
| `volume_filter` | true | Only trade with volume confirmation |
| `volume_threshold` | 1.5 | Required volume as multiple of 20-day average |
| `cooldown_days` | 3 | Minimum days between signals |

**Technical Details:**
- Upper Band = SMA + (Std Dev × Rolling Std)
- Lower Band = SMA - (Std Dev × Rolling Std)
- Middle Band = SMA (exit signal)
- State machine tracks position: no position → long/short → exit
- Volume confirmation requires volume > threshold × 20-day average volume

**When to use:**
- Volatile stocks with strong directional moves
- Markets breaking out of consolidation patterns
- When seeking mean-reversion exits (middle band)

**Strengths:** Catches strong breakouts early, built-in exit strategy at middle band, confirmation bars reduce false signals.
**Weaknesses:** Can generate whipsaws in choppy markets, requires volatility to generate signals.

---

## 5. VWAP Mean Reversion

**File:** `strategies/implementations/vwap_reversion.py`

**Logic:** Buy when price deviates below VWAP by N standard deviations AND RSI is oversold. Sell when price exceeds VWAP by N standard deviations AND RSI is overbought. Exit positions when price returns to VWAP. Uses rolling VWAP calculation based on typical price and volume.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vwap_period` | 20 | Rolling window for VWAP calculation |
| `deviation_threshold` | 2.0 | Number of standard deviations for entry signal |
| `rsi_period` | 14 | RSI calculation period |
| `oversold` | 30 | RSI threshold for buy signals |
| `overbought` | 70 | RSI threshold for sell signals |
| `cooldown_days` | 3 | Minimum days between signals |

**Technical Details:**
- VWAP = Σ(Typical Price × Volume) / Σ(Volume) over rolling window
- Typical Price = (High + Low + Close) / 3
- Deviation Bands = VWAP ± (Threshold × Std Dev of price from VWAP)
- State machine: no position → long/short → exit at VWAP
- Requires both price deviation AND RSI confirmation for entry

**When to use:**
- Liquid stocks with high trading volume
- Mean-reverting markets with clear VWAP support/resistance
- Intraday or daily timeframes where volume is significant

**Strengths:** VWAP is widely watched by institutional traders, volume-weighted calculation reduces noise, dual confirmation (price + RSI) reduces false signals.
**Weaknesses:** Less effective in low-volume stocks, requires sufficient data for VWAP calculation, lagging indicator in fast-moving markets.

---

## Adding a New Strategy

1. Create `backend/src/strategies/implementations/your_strategy.py`
2. Inherit from `BaseStrategy`:

```python
from ..base_strategy import BaseStrategy

class YourStrategy(BaseStrategy):
    name = "Your_Strategy"

    def validate_params(self):
        self.params.setdefault("period", 14)
        # Validate...

    def required_columns(self) -> list[str]:
        return ["Close", "RSI"]  # columns your strategy needs

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0       # 1=buy, -1=sell, 0=hold
        signals["confidence"] = 0.0  # 0-1
        signals["reason"] = ""
        # Your logic here...
        return signals
```

3. Register in `implementations/__init__.py`
4. Add to `STRATEGY_MAP` in `api/routes.py`
5. Add default params to `config.yaml`
6. Write tests and update this doc

## Strategy Comparison Tips

- Use `/api/compare` to run multiple strategies on the same data
- Look at Sharpe ratio for risk-adjusted returns, not just total return
- Check max drawdown — a high-return strategy with 50% drawdown may not be practical
- Run Monte Carlo to see the range of possible outcomes
- Use walk-forward validation to test for overfitting
