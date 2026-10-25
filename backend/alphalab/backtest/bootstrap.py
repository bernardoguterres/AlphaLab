"""Block-bootstrap uncertainty for a completed backtest.

Question answered
-----------------
"If the strategy's realised per-bar returns are a representative sample of
its return-generating process, how much could this period's final value,
maximum drawdown and Sharpe ratio have differed through sampling variation
alone?"

Method
------
Circular moving-block bootstrap (Kunsch 1989; Politis & Romano 1992) of the
strategy's realised per-bar equity returns. Each resample concatenates
blocks of `block_length` consecutive returns starting at uniformly drawn
positions (wrapping around the end), truncated to the original length.
Blocks keep short-range dependence (volatility clustering, autocorrelated
P&L from multi-bar holds) that an i.i.d. resample would destroy. A seed is
always used and reported, so results are reproducible.

What it does NOT do
-------------------
- It never re-runs the strategy or re-times trades, so it cannot execute on
  information from the future (the previous "Monte Carlo" shifted the
  signal series by -2..+2 bars - negative shifts traded before the signal
  existed - and could only ever produce 5 distinct outcomes).
- It does not model parameter-selection uncertainty, regime change,
  execution/slippage differences or survivorship; a wide or narrow band is
  a statement about sampling noise in THIS return series only.
- Dependence longer than the block length is not preserved.
"""

from __future__ import annotations

import math

import numpy as np

from .metrics import _MIN_RATIO_DENOMINATOR

METHOD = "circular_moving_block_bootstrap"
QUESTION = (
    "Sampling variation of final value, max drawdown and Sharpe if the "
    "realised per-bar strategy returns are representative of its return "
    "process. Excludes parameter, regime, execution and survivorship "
    "uncertainty; never re-runs the strategy."
)


def default_block_length(n: int) -> int:
    """n^(1/3) rule of thumb (Hall, Horowitz & Jing 1995), at least 1."""
    return max(1, int(round(n ** (1 / 3))))


def _max_drawdown(path: np.ndarray) -> float:
    peak = np.maximum.accumulate(path)
    return float(((path - peak) / peak).min())


def block_bootstrap(
    returns: np.ndarray,
    initial_value: float,
    n_runs: int,
    periods_per_year: float,
    risk_free_rate: float = 0.04,
    block_length: int | None = None,
    seed: int | None = None,
) -> dict:
    """Resample `returns` (per-bar simple returns) and summarise outcomes."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 2 or n_runs <= 0:
        raise ValueError("need at least 2 returns and n_runs > 0")
    L = int(block_length or default_block_length(n))
    L = max(1, min(L, n))
    if seed is None:
        seed = int(np.random.SeedSequence().entropy % (2**31))
    rng = np.random.default_rng(seed)

    n_blocks = math.ceil(n / L)
    offsets = np.arange(L)
    finals = np.empty(n_runs)
    mdds = np.empty(n_runs)
    sharpes = np.empty(n_runs)
    for k in range(n_runs):
        starts = rng.integers(0, n, size=n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        sample = r[idx]
        path = initial_value * np.cumprod(1 + sample)
        finals[k] = path[-1]
        mdds[k] = _max_drawdown(np.concatenate([[initial_value], path]))
        # Same degenerate-volatility guard as the headline Sharpe
        # (metrics._MIN_RATIO_DENOMINATOR on ANNUALISED vol): a resample of a
        # mostly-in-cash strategy that draws one or two non-zero returns
        # would otherwise report Sharpe percentiles in the thousands.
        vol = sample.std(ddof=1) * math.sqrt(periods_per_year)
        sharpes[k] = (
            (sample.mean() * periods_per_year - risk_free_rate) / vol
            if vol > _MIN_RATIO_DENOMINATOR
            else 0.0
        )

    def pct(a, q):
        return round(float(np.percentile(a, q)), 4)

    return {
        "method": METHOD,
        "question": QUESTION,
        "runs": int(n_runs),
        "seed": int(seed),
        "block_length": L,
        "observations": n,
        "mean_final_value": round(float(finals.mean()), 2),
        "median_final_value": round(float(np.median(finals)), 2),
        "std_final_value": round(float(finals.std()), 2),
        "min_final_value": round(float(finals.min()), 2),
        "max_final_value": round(float(finals.max()), 2),
        "percentile_5": round(float(np.percentile(finals, 5)), 2),
        "percentile_95": round(float(np.percentile(finals, 95)), 2),
        "prob_profit": round(float((finals > initial_value).mean()), 4),
        # String keys: JSON object keys are strings anyway; int keys silently
        # changed type between the Python result and the API response.
        "max_drawdown_pct": {f"p{q}": pct(mdds * 100, q) for q in (5, 50, 95)},
        "sharpe": {f"p{q}": pct(sharpes, q) for q in (5, 50, 95)},
    }
