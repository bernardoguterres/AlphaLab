"""Validation of the block-bootstrap uncertainty estimate on controlled
examples (alphalab/backtest/bootstrap.py), before any real-data use."""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from alphalab.backtest.bootstrap import block_bootstrap, default_block_length
from alphalab.backtest.engine import BacktestEngine
from alphalab.strategies.base_strategy import BaseStrategy


def _mean_return_spread(returns, block_length, runs=4000, seed=1):
    """Std of the resampled mean return, read back from final values:
    with tiny returns, log(final/initial)/n ~= mean return."""
    out = block_bootstrap(returns, 1.0, runs, 252, 0.0, block_length, seed)
    # reconstruct via percentiles is lossy; recompute directly instead
    rng = np.random.default_rng(seed)
    n = len(returns)
    L = block_length
    means = []
    for _ in range(runs):
        starts = rng.integers(0, n, size=int(np.ceil(n / L)))
        idx = ((starts[:, None] + np.arange(L)[None, :]) % n).ravel()[:n]
        means.append(returns[idx].mean())
    return out, float(np.std(means))


def test_constant_returns_have_zero_spread():
    r = np.full(250, 0.001)
    out = block_bootstrap(r, 100_000, 200, 252, seed=7)
    assert out["min_final_value"] == out["max_final_value"]
    assert out["std_final_value"] == 0.0
    expected = 100_000 * 1.001**250
    assert out["median_final_value"] == pytest.approx(expected, abs=0.01)  # cents


def test_seed_makes_results_reproducible_and_is_reported():
    r = np.random.default_rng(0).normal(0.0005, 0.01, 500)
    a = block_bootstrap(r, 1e5, 300, 252, seed=42)
    b = block_bootstrap(r, 1e5, 300, 252, seed=42)
    c = block_bootstrap(r, 1e5, 300, 252, seed=43)
    assert a == b
    assert a["percentile_5"] != c["percentile_5"]
    unseeded = block_bootstrap(r, 1e5, 50, 252)
    assert isinstance(unseeded["seed"], int)
    assert block_bootstrap(r, 1e5, 50, 252, seed=unseeded["seed"]) == unseeded


def test_iid_returns_reproduce_textbook_standard_error():
    r = np.random.default_rng(3).normal(0.0, 0.01, 1000)
    _, spread = _mean_return_spread(r, block_length=1)
    textbook = r.std(ddof=1) / np.sqrt(len(r))
    assert spread == pytest.approx(textbook, rel=0.08)


def test_blocks_capture_autocorrelation_iid_resampling_misses():
    """AR(1) with phi=0.6: the true variance of the mean is ~(1+phi)/(1-phi)
    = 4x the i.i.d. formula. L=1 (i.i.d.) understates it; long blocks recover
    most of it."""
    rng = np.random.default_rng(5)
    phi, n = 0.6, 4000
    e = rng.normal(0, 0.01, n)
    r = np.empty(n)
    r[0] = e[0]
    for t in range(1, n):
        r[t] = phi * r[t - 1] + e[t]
    _, iid = _mean_return_spread(r, 1, runs=2000)
    _, blk = _mean_return_spread(r, 40, runs=2000)
    ratio = (blk / iid) ** 2
    assert 2.5 < ratio < 5.0


def test_default_block_length_rule():
    assert default_block_length(1000) == 10
    assert default_block_length(8) == 2
    assert default_block_length(1) == 1


class _Buy(BaseStrategy):
    name = "buy"

    def validate_params(self):
        pass

    def required_columns(self):
        return ["Close"]

    def generate_signals(self, data):
        s = self._init_signals_frame(data)
        s.iloc[0, 0] = 1
        return s


def test_engine_bootstrap_never_reruns_the_strategy():
    """No look-ahead by construction: only the completed equity curve is
    resampled; the strategy is generated exactly once (the real backtest)."""
    idx = pd.bdate_range("2023-01-02", periods=300)
    px = 100 * np.cumprod(1 + np.random.default_rng(2).normal(0.0004, 0.01, 300))
    df = pd.DataFrame(
        {"Open": px, "High": px, "Low": px, "Close": px, "Volume": 1e6}, index=idx
    )
    df.attrs["ticker"] = "T"
    strat = _Buy()
    with patch.object(_Buy, "generate_signals", wraps=strat.generate_signals) as gen:
        res = BacktestEngine().run_backtest(
            strat, df, 100_000, monte_carlo_runs=100, monte_carlo_seed=11
        )
    assert gen.call_count == 1
    mc = res.monte_carlo
    assert mc["method"] == "circular_moving_block_bootstrap"
    assert mc["seed"] == 11 and mc["runs"] == 100
    assert mc["percentile_5"] <= mc["median_final_value"] <= mc["percentile_95"]


def test_mostly_cash_strategy_has_no_exploding_bootstrap_sharpe():
    """Regression (2026-10 review): with a per-period 1e-12 guard, resamples
    of a ~0.1%-exposure strategy that drew one tiny non-zero return gave
    Sharpe percentiles of -1e3..-1e6; the headline metric (annualised-vol
    guard) reports 0 for the same degenerate case."""
    r = np.zeros(1000)
    r[500] = 1e-6
    out = block_bootstrap(
        r, initial_value=100_000, n_runs=500, periods_per_year=252, seed=1
    )
    assert set(out["sharpe"]) == {"p5", "p50", "p95"}
    assert all(abs(v) < 100 for v in out["sharpe"].values())
