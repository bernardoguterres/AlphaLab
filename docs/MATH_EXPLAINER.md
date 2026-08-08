# AlphaLab — The Math

What every strategy, indicator, and metric in this repo actually computes, in plain terms with the real formulas. Written so you can explain any part of this system in an interview without re-deriving it on the spot. Cross-referenced against the actual source (`alphalab/data/processor.py`, `alphalab/backtest/metrics.py`, `alphalab/screener/fundamental_screener.py`, `alphalab/backtest/deflated_sharpe.py`, `alphalab/backtest/faber_overlay.py`) — this describes what the code does, not textbook idealizations of it.

---

## 1. Technical Indicators

All computed once per backtest by `FeatureEngineer`, then every strategy reads from these pre-computed columns rather than recomputing indicators itself.

### SMA (Simple Moving Average)
$$SMA_n(t) = \frac{1}{n}\sum_{i=0}^{n-1} \text{Close}(t-i)$$
Plain average of the last *n* closes. Computed for n = 10, 20, 50, 100, 200. The classic trend-direction gauge — price above a rising SMA suggests an uptrend.

### RSI (Relative Strength Index, 14-period)
$$RSI = 100 - \frac{100}{1 + RS}, \quad RS = \frac{\text{avg gain}}{\text{avg loss}}$$
Gains and losses are smoothed with an exponential moving average (Wilder's smoothing, `alpha = 1/14`), not a simple average — this is the standard RSI definition, and it matters: EMA-smoothed RSI reacts faster to recent moves than a naive rolling-average version. Bounded 0-100. Below 30 is conventionally "oversold," above 70 "overbought" — though each strategy here tunes its own thresholds rather than using the textbook 30/70.

### Bollinger Bands (20-period, 2 standard deviations)
$$\text{Middle} = SMA_{20}, \quad \text{Upper} = SMA_{20} + 2\sigma_{20}, \quad \text{Lower} = SMA_{20} - 2\sigma_{20}$$
$\sigma_{20}$ is the rolling 20-period standard deviation of closing price. Under a normal-distribution assumption, price should stay within the bands ~95% of the time — a touch of either band is a statistical "this move is unusually large" signal, not a guarantee of reversal.

### ATR (Average True Range, 14-period)
$$TR(t) = \max\big(\text{High}-\text{Low},\ |\text{High}-\text{Close}_{t-1}|,\ |\text{Low}-\text{Close}_{t-1}|\big)$$
$$ATR = \text{EMA}_{14}(TR)$$
True Range captures a bar's real volatility including gaps (not just High−Low). ATR is the smoothed average of that — used here to size stop-losses and trailing stops in units of "how much this stock actually moves," rather than a fixed percentage that's too tight for a volatile stock and too loose for a calm one.

### ADX (Average Directional Index, 14-period)
$$+DI = 100\cdot\frac{\text{EMA}_{14}(+DM)}{ATR}, \quad -DI = 100\cdot\frac{\text{EMA}_{14}(-DM)}{ATR}$$
$$DX = 100\cdot\frac{|+DI - -DI|}{+DI + -DI}, \quad ADX = \text{EMA}_{14}(DX)$$
Where $+DM$/$-DM$ (directional movement) capture whether a bar's high/low moved further than the prior bar's, in which direction. ADX measures *trend strength*, not direction — a high ADX means a strong trend (up or down), a low ADX means a choppy, range-bound market. Used as an optional filter to avoid trading mean-reversion strategies in a strongly trending market (where they tend to fail) or trend strategies in a choppy one.

### VWAP (Volume-Weighted Average Price, rolling)
$$\text{Typical Price} = \frac{\text{High}+\text{Low}+\text{Close}}{3}$$
$$VWAP = \frac{\sum_{i=0}^{n-1} \text{Typical Price}(t-i) \cdot \text{Volume}(t-i)}{\sum_{i=0}^{n-1} \text{Volume}(t-i)}$$
A *rolling*-window VWAP (default 20 bars), not the cumulative-since-market-open VWAP day traders usually mean — this one's meant to represent "the volume-weighted fair price over the recent past," a smoother, volume-aware alternative to a plain SMA.

---

## 2. The Nine Strategies

Every strategy follows the same shape: a set of pre-computed indicator columns, a rule for entry, a rule for exit, and — in the state-aware ones — position tracking so the exit rule can reference the entry price (for stop-loss/trailing-stop math). All of them trade on **next-bar open**, not the bar the signal fired on — no look-ahead bias.

| Strategy | Entry | Exit |
|---|---|---|
| **MA Crossover** | Fast SMA(10) crosses above slow SMA(50) | Opposite crossover |
| **RSI Mean Reversion** | RSI < oversold threshold | RSI returns to 50, 2.5×ATR stop-loss, or 40-bar max hold |
| **Momentum Breakout** | Close > 20-bar high **and** volume ≥ 150% of its 20-bar average **and** RSI ≥ 50 | 3×ATR trailing stop or breakdown below the breakout level |
| **Bollinger Breakout** | N consecutive closes above (or below, for shorts) the band + volume confirmation | Price returns to within 1% of the middle band (the 20-SMA) |
| **VWAP Reversion** | Close deviates > *k* standard deviations below rolling VWAP **and** RSI oversold | Price reverts back to VWAP |
| **Bollinger + RSI Combo** | Close ≤ lower band **and** RSI < 45 | Close ≥ middle band **or** RSI > 55 |
| **Trend-Adaptive RSI** | Regime detected from SMA(50) slope (price vs. SMA, SMA rising/falling): uptrend buys dips at RSI 45, downtrend fades bounces at RSI 35, range uses standard RSI 35 | Regime-symmetric sell threshold (uptrend 65, downtrend 55, range 65) |
| **RSI Simple** | RSI < 30 | RSI > 70 (textbook thresholds, no other filters — the "control group" strategy) |
| **Greenblatt Weekly** | Weekly RSI < 35 **or** 10-week SMA crosses above 50-week SMA — *only for stocks that already passed the Greenblatt fundamental screen* | 20% trailing stop from the position's peak price, always active. Minimum hold: 52 weeks. Optional RSI/SMA exits exist but are off by default |

**The project's own finding, worth internalizing**: all eight daily/intraday strategies backtest to negative or near-zero Sharpe ratio against buy-and-hold SPY, consistently, across every real dataset tested. That's not a bug — it's the actual, honestly-measured result of naive technical-indicator trading on liquid large caps, and it's *why* the project pivoted toward Greenblatt.

---

## 3. Greenblatt's Magic Formula

The one strategy here grounded in a published, institutionally-recognized methodology (Joel Greenblatt, *The Little Book That Beats the Market*). Two factors, ranked and combined:

**Earnings Yield** — how cheap the company is relative to its total operating earnings power:
$$\text{Earnings Yield} = \frac{EBIT}{\text{Enterprise Value}}$$
EBIT (Earnings Before Interest and Taxes) rather than net income, because it's capital-structure-neutral — a company with heavy debt and one with none are compared on the same basis. Enterprise Value (market cap + debt − cash) rather than just market cap, for the same reason: it's the real cost to acquire the whole business, debt included.

**Return on Capital** — how efficiently the company turns invested capital into that operating profit:
$$\text{Return on Capital} = \frac{EBIT}{\text{Net Working Capital} + \text{Net Fixed Assets}}$$
The denominator is the actual capital tied up in the operating business (working capital + PP&E) — not total assets, which would understate the ratio for capital-light businesses and penalize them unfairly.

**Combining the two**: rank every stock in the universe on each factor separately (1 = best), then
$$\text{Combined Rank} = \text{Earnings Yield Rank} + \text{Return on Capital Rank}$$
Lower combined rank = better. Buy the top N, hold roughly a year, rebalance. The logic: a company that's both *cheap* (high earnings yield) and *high-quality* (high return on capital) is the value-investing sweet spot — cheap-but-bad and expensive-but-good both get filtered out by requiring both factors to rank well.

Financials and utilities are excluded — EBIT-based ratios aren't meaningful for regulated, balance-sheet-driven businesses (a bank's "capital" is deposits, not fixed assets).

**The honest caveat, already documented in this repo and worth repeating to any employer who asks**: a rigorous re-test found this specific ranking beats plain equal-weight diversification of the same qualified universe in only 2 of 6 historical windows tested, and loses in the other 4 — sometimes badly (an 11-point wrong-direction gap in the 2022 bear market). The formula is real and academically grounded; this implementation's edge over just diversifying is *not* validated by the evidence gathered so far. That distinction — knowing the difference between "backtests well" and "beats a naive baseline" — is the actual point of doing this rigorously.

---

## 4. Portfolio Construction

`PortfolioConstructor` holds the top-N ranked candidates as one basket sharing a single capital pool (distinct from running N independent single-stock backtests, which would give each stock its own separate pretend account). At each rebalance date:

$$\text{Position Weight}_i = \frac{1}{N} \quad \text{for each of the top } N \text{ ranked candidates}$$

Only **equal-weight** is implemented (rank-weighted and risk-parity are explicitly out of scope, not silently unbuilt). A ticker that drops out of the top-N at the next rebalance is force-sold to zero — no silent carrying of a position that no longer qualifies.

---

## 5. Backtest Performance Metrics

Computed by `PerformanceMetrics` on the equity curve and trade log. `periods_per_year` is **inferred from the equity curve's actual date spacing** (252 for daily, 52 for weekly, etc.) rather than hardcoded — a real bug this project found and fixed: a weekly backtest naively annualized as if every bar were a trading day inflated a real ~20% CAGR into a reported 142%.

### CAGR (Compound Annual Growth Rate)
$$CAGR = (1 + \text{Total Return})^{1/\text{years}} - 1$$
The single-number "if this grew smoothly the whole time, what annual rate would that be" summary — smooths over the actual (lumpy) path.

### Sharpe Ratio
$$\text{Sharpe} = \frac{R_{\text{annualized}} - R_f}{\sigma_{\text{annualized}}}$$
Excess return (over the risk-free rate, default 4%) per unit of *total* volatility. The standard risk-adjusted-return number — but it penalizes upside volatility exactly as much as downside, which is arguably the wrong instinct (nobody complains about volatile gains).

### Sortino Ratio
$$\text{Sortino} = \frac{R_{\text{annualized}} - R_f}{\sigma_{\text{downside, annualized}}}$$
Same idea as Sharpe, but the denominator only counts *downside* deviation (the standard deviation of negative-return periods only). Answers "how much bad volatility am I taking on per unit of excess return" — generally considered the more honest risk-adjusted metric for exactly the reason above.

### Calmar Ratio
$$\text{Calmar} = \frac{R_{\text{annualized}}}{|\text{Max Drawdown}|}$$
Return per unit of worst-case peak-to-trough loss. Where Sharpe/Sortino use statistical volatility, Calmar uses the single worst real outcome — closer to "how bad did it actually get" than a probabilistic measure.

### VaR / CVaR (Value at Risk / Conditional VaR, 95%)
$$VaR_{95} = \text{5th percentile of the return distribution}$$
$$CVaR_{95} = \text{mean of all returns} \leq VaR_{95}$$
VaR: "on a bad day (worst 5%), how bad is it." CVaR: "given that it's already a bad day, how bad *on average*" — CVaR is the more informative number because it captures tail severity, not just the tail's boundary (VaR is silent on how bad the worst 1% actually gets; CVaR isn't).

### Max Drawdown
$$DD(t) = \frac{\text{Equity}(t) - \text{Running Peak Equity}(t)}{\text{Running Peak Equity}(t)}, \quad \text{Max Drawdown} = \min_t DD(t)$$
The largest peak-to-trough decline over the whole backtest — the number that answers "what's the worst it would have felt to hold this."

---

## 6. Statistical Validation (the part most backtests skip)

This is the part that separates "I found a strategy that looks good" from "I checked whether it's actually likely to be real" — and it's the most defensible, interview-worthy part of this project, precisely because the honest answer it produced was often "no."

### Deflated Sharpe Ratio (Bailey & López de Prado, 2014)
The core problem it solves: if you test 6 candidate strategies and pick the best-looking one, that Sharpe ratio is inflated by *selection bias* — even 6 random-noise strategies will produce one that looks good by chance. DSR corrects for this, and for non-normal (skewed, fat-tailed) return distributions where the standard Sharpe standard-error formula breaks down.

$$\hat\sigma(SR) = \sqrt{\frac{1 - \gamma_3 \cdot SR + \frac{\gamma_4-1}{4}SR^2}{T-1}}$$
$$SR_0 = \hat\sigma(SR)\Big[(1-\gamma)\,\Phi^{-1}\!\Big(1-\tfrac{1}{N}\Big) + \gamma\,\Phi^{-1}\!\Big(1-\tfrac{1}{Ne}\Big)\Big]$$
$$DSR = \Phi\!\left(\frac{SR - SR_0}{\hat\sigma(SR)}\right)$$
Where $\gamma_3$/$\gamma_4$ are the return distribution's skewness and (Pearson, not excess) kurtosis, $N$ is the number of strategies/trials tried (the multiple-testing correction), $T$ the number of return observations, $\gamma \approx 0.5772$ (Euler-Mascheroni constant), and $\Phi$ the standard normal CDF. $SR_0$ is "the best Sharpe ratio you'd expect from N *unskilled* trials by pure luck" — DSR is the probability your actual Sharpe genuinely exceeds that luck baseline. Conventional bar: DSR > 0.95.

**The finding**: the faithful Greenblatt portfolio beat both SPY buy-and-hold and the Faber overlay descriptively, but its DSR (0.55 in one test window, 0.65 in another) never cleared 0.95. Verdict: **not statistically validated**, despite looking good on the surface — exactly the trap DSR exists to catch.

### Faber Overlay (2007/2013 tactical timing benchmark)
A mandatory second benchmark alongside plain buy-and-hold, because buy-and-hold isn't actually the hardest bar to clear:
$$\text{Invested}(t) = \begin{cases}\text{True} & \text{if } \text{Close}(t) > SMA_{10\text{mo}}(t) \\ \text{False (hold cash)} & \text{otherwise}\end{cases}$$
Decided once a month using a 10-month simple moving average on monthly closes. If a strategy claims a "timing" or "trend" edge, it should beat this — a genuinely simple, well-documented timing rule — not just an uninvested buy-and-hold baseline.

### Equal-Weight Diversification Benchmark
The check that actually caught Greenblatt's real weakness: compare the ranked strategy's return not just to SPY, but to **plain equal-weighting of the same qualified universe**, with zero ranking logic at all. If the ranked strategy can't beat "hold everything that passed the filter, weighted equally," the ranking itself isn't adding value — only the *filter* is (and diversification is doing the rest). This is exactly what happened in 4 of 6 windows.

### Walk-Forward Validation
Split history into non-overlapping train/test windows; parameters are only ever chosen using the train window, then applied unmodified to the following, previously-unseen test window. Protects against the single most common backtest failure mode: tuning parameters on the same data you're using to "prove" the strategy works, which will always look great and mean nothing.

---

## The one-paragraph version, for an interview

*"I built a backtesting engine with realistic execution (next-bar fills, slippage, commissions, no look-ahead bias), implemented both standard technical-indicator strategies and Joel Greenblatt's Magic Formula, and — critically — didn't stop at 'does this backtest look good.' I applied walk-forward validation, a Deflated Sharpe Ratio correction for multiple-testing and non-normal returns, and an equal-weight diversification benchmark. The honest result: none of the eight technical strategies beat buy-and-hold, and even the academically-grounded Greenblatt ranking didn't clear the statistical significance bar or reliably beat simply diversifying across the same filtered universe. That's not a failed project — that's what rigorous quantitative validation is supposed to produce most of the time, and knowing how to tell the difference between 'looks good' and 'is real' is the actual skill."*
