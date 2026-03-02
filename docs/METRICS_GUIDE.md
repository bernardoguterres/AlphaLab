# AlphaLab Metrics Guide

Understanding what each metric means and how to interpret backtest results.

---

## Return Metrics

| Metric | What It Measures | Good Value |
|--------|-----------------|------------|
| **Total Return %** | Overall gain/loss | Positive, ideally > benchmark |
| **CAGR** | Annualized compound growth | >10% is strong for equities |
| **Mean Daily Return** | Average daily gain | Positive |
| **Skewness** | Return distribution asymmetry | Positive = more large gains than losses |
| **Kurtosis** | Tail risk (extreme events) | Lower = fewer surprises |

**CAGR** is more meaningful than total return because it accounts for time. A 50% return over 5 years (8.4% CAGR) is different from 50% in 1 year.

---

## Risk Metrics

| Metric | What It Measures | Good Value |
|--------|-----------------|------------|
| **Volatility** | Annualized standard deviation of returns | Lower = smoother ride |
| **Sharpe Ratio** | Return per unit of risk: (Return - Risk-Free) / Volatility | >1.0 good, >2.0 excellent |
| **Sortino Ratio** | Like Sharpe but only penalizes downside volatility | >1.5 good, >3.0 excellent |
| **Calmar Ratio** | Annual return / Max drawdown | >1.0 means return exceeds worst loss |
| **VaR (95%)** | Worst expected daily loss 95% of the time | Closer to 0 = less risk |
| **CVaR (95%)** | Average loss in the worst 5% of days | More conservative than VaR |

**Sharpe Ratio** is the most widely used risk-adjusted metric. A strategy with 20% return and 40% volatility (Sharpe ~0.4) is worse risk-adjusted than 10% return with 8% volatility (Sharpe ~0.75).

**Sortino Ratio** is better than Sharpe when returns are skewed, because it doesn't penalize upside volatility.

---

## Drawdown Metrics

| Metric | What It Measures | Good Value |
|--------|-----------------|------------|
| **Max Drawdown** | Largest peak-to-trough decline | >-20% is concerning |
| **Avg Drawdown** | Typical decline during losing periods | Smaller = more consistent |
| **Max Duration** | Longest time underwater (days) | Shorter = faster recovery |
| **Recovery Days** | Days to recover from max drawdown | Shorter = more resilient |

**Max Drawdown** is critical for practical trading. A 50% drawdown requires a 100% gain to recover. Most traders can't psychologically handle drawdowns beyond 20-30%.

---

## Trade Statistics

| Metric | What It Measures | Good Value |
|--------|-----------------|------------|
| **Win Rate** | % of profitable trades | >50% for most strategies |
| **Avg Win / Avg Loss** | Reward-to-risk per trade | Avg Win > Avg Loss |
| **Profit Factor** | Gross Profit / Gross Loss | >1.5 good, >2.0 excellent |
| **Expectancy** | Expected profit per trade | Positive |
| **Best/Worst Trade** | Extremes | Worst trade shouldn't be catastrophic |

**Win Rate alone is misleading.** A strategy with 30% win rate but 5:1 reward-to-risk is profitable. Expectancy combines win rate with average win/loss to give the true picture.

**Profit Factor** above 1.0 means gross profits exceed gross losses. Below 1.0 = losing strategy.

---

## Consistency Metrics

| Metric | What It Measures | Good Value |
|--------|-----------------|------------|
| **Profitable Months %** | How often you make money monthly | >60% |
| **Longest Win Streak** | Best consecutive winning days | Higher = momentum |
| **Longest Loss Streak** | Worst consecutive losing days | <10 days |
| **Ulcer Index** | Measures depth and duration of drawdowns | Lower = less painful |
| **Rolling Sharpe** | 12-month rolling risk-adjusted return | Stable and positive |

**Consistency matters more than peaks.** A strategy that makes 5% every month is far better than one that makes 60% in one month and loses 50% the next.

---

## Benchmark Comparison

| Metric | What It Measures | Good Value |
|--------|-----------------|------------|
| **Beta** | Sensitivity to market moves | 1.0 = moves with market |
| **Alpha** | Excess return above market (risk-adjusted) | Positive and significant |
| **Tracking Error** | How much returns deviate from benchmark | Depends on strategy |
| **Information Ratio** | Active return / Tracking error | >0.5 good |
| **Up Capture** | % of market gains captured when market rises | >100% = outperforms in up markets |
| **Down Capture** | % of market losses captured when market falls | <100% = protects in down markets |

**Alpha** is the holy grail — excess return that can't be explained by market exposure. The `alpha_p_value` tells you if alpha is statistically significant (p < 0.05 = significant).

**Ideal profile:** High up capture (>100%) + low down capture (<80%) = you participate in rallies but are protected in crashes.

---

## Interpreting Results

### Red Flags
- Sharpe < 0: Strategy loses money on a risk-adjusted basis
- Max Drawdown > -30%: Likely unsustainable for real trading
- Win Rate < 30% without high reward-to-risk ratio
- Profit Factor < 1.0: Gross losses exceed gross profits
- Alpha p-value > 0.05: Outperformance may be due to luck

### Green Flags
- Sharpe > 1.5 with >2 years of data
- Max Drawdown > -15% with decent returns
- Consistent monthly profitability (>60% of months)
- Statistically significant alpha (p < 0.05)
- Results hold across walk-forward validation periods

### Important Caveats
- Past performance does not predict future results
- Backtests are optimistic — real trading has more friction
- Overfitting to historical data is the biggest risk
- Use Monte Carlo and walk-forward to stress-test results
- Transaction costs compound over time — fewer trades is often better
