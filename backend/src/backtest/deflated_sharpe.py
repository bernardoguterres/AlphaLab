"""Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

"The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest
Overfitting and Non-Normality", Journal of Portfolio Management 40(5).
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

Implements the paper's closed-form correction for two things at once:
  1. Multiple testing / selection bias: if you evaluated N strategy
     variants and report the best one, its Sharpe ratio overstates true
     skill purely from the number of trials (the "if you flip enough coins,
     one looks skilled" effect). SR_0 below is the expected maximum Sharpe
     ratio achievable by N trials under the null hypothesis of NO skill.
  2. Non-normality: the standard error of a Sharpe ratio estimate is not
     the naive 1/sqrt(T) approximation once returns are skewed or
     fat-tailed - it depends on the return distribution's skewness and
     kurtosis too (this generalizes the Lo (2002) standard-error formula
     already used for the sample-size derivation in
     scripts/greenblatt_faithful_backtest.py).

The Deflated Sharpe Ratio (DSR) is the probability that the TRUE Sharpe
ratio exceeds SR_0, given the observed Sharpe ratio and its (skew/kurtosis
-adjusted) standard error. DSR > 0.95 is the conventional "significant at
95% confidence, even after correcting for N trials and non-normality" bar.

Formula (all in PER-PERIOD units - i.e. using the same return frequency as
T, not annualized - annualized figures are also returned for convenience):

    sigma_hat(SR) = sqrt( (1 - skew*SR + (kurtosis-1)/4 * SR^2) / (T-1) )

    SR_0 = sigma_hat(SR) * [ (1-gamma)*Phi^-1(1 - 1/N) + gamma*Phi^-1(1 - 1/(N*e)) ]

    DSR = Phi( (SR - SR_0) / sigma_hat(SR) )

where `skew` is the Fisher-Pearson skewness, `kurtosis` is the PEARSON
(raw, normal=3) kurtosis (not excess kurtosis - pandas' .kurt() returns
excess kurtosis, so callers using pandas must add 3), gamma is the
Euler-Mascheroni constant, N is the number of trials, T is the number of
per-period return observations, and Phi/Phi^-1 are the standard normal
CDF/inverse CDF.

Known limitation, stated explicitly (see docs/STRATEGY_RESEARCH_PLAN.md
section D): SR_0's derivation assumes the N trials' Sharpe-ratio estimates
have the same standard error as this one candidate's sigma_hat(SR) - the
standard simplifying assumption used whenever the other N-1 trials'
individual Sharpe estimates aren't available (which is the case here: at
the time any one Greenblatt experiment runs, most of the locked 6-trial
roster hasn't been executed yet). This is not a fabrication - it's the
approximation the original paper itself uses in its worked examples when
per-trial variance data isn't on hand - but it is an approximation, and is
labeled as such in every result this module produces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm

EULER_MASCHERONI = 0.5772156649015329


@dataclass
class DeflatedSharpeResult:
    n_trials: int
    n_observations: int
    periods_per_year: float
    sharpe_period: float
    sharpe_annualized: float
    skewness: float
    kurtosis_pearson: float
    sharpe_std_error_period: float
    expected_max_sharpe_under_null_period: float
    expected_max_sharpe_under_null_annualized: float
    deflated_sharpe_ratio: float
    significant_at_95pct: bool
    assumption_note: str = (
        "SR_0 assumes the other trials in the roster share this candidate's "
        "own Sharpe standard error (no per-trial variance data available "
        "for not-yet-run trials) - see module docstring."
    )


def deflated_sharpe_ratio(
    sharpe_annualized: float,
    skewness: float,
    kurtosis_pearson: float,
    n_observations: int,
    n_trials: int,
    periods_per_year: float,
) -> DeflatedSharpeResult:
    """Compute the Deflated Sharpe Ratio for one candidate against a locked
    trial roster.

    Args:
        sharpe_annualized: the candidate's own (already-annualized) Sharpe
            ratio, as reported elsewhere (e.g. PerformanceMetrics).
        skewness: Fisher-Pearson skewness of the per-period returns.
        kurtosis_pearson: Pearson (raw) kurtosis of the per-period returns -
            normal distribution = 3. If computed via pandas' `.kurt()`
            (which returns EXCESS kurtosis), add 3 before passing in.
        n_observations: number of per-period return observations (T).
        n_trials: size of the locked trial roster (N) - see
            docs/EXPERIMENT_REGISTRY_SCHEMA.md "Multiple-testing roster".
        periods_per_year: return-observation frequency, for reporting an
            annualized SR_0 alongside the per-period figure used internally.

    Returns:
        DeflatedSharpeResult with both per-period and annualized figures.

    Raises:
        ValueError: if n_observations < 2 or n_trials < 1.
    """
    if n_observations < 2:
        raise ValueError(
            "Need at least 2 return observations to estimate a standard error"
        )
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")

    sharpe_period = sharpe_annualized / math.sqrt(periods_per_year)

    variance_term = (
        1 - skewness * sharpe_period + ((kurtosis_pearson - 1) / 4) * sharpe_period**2
    )
    # Non-normality can, in pathological cases, drive this negative for a
    # single sample; floor at a tiny positive value rather than raise, since
    # a preliminary research run shouldn't crash on a degenerate return
    # distribution - the resulting DSR will simply come out very close to
    # 0 or 1 (uninformative), which is an honest reflection of insufficient
    # data, not a bug to hide via silent clamping without saying so.
    variance_term = max(variance_term, 1e-8)
    sharpe_se_period = math.sqrt(variance_term / (n_observations - 1))

    if n_trials == 1:
        # With exactly one trial there is nothing to correct for beyond
        # non-normality - SR_0 collapses to 0 (no multiple-testing penalty).
        sr_0_period = 0.0
    else:
        z_a = norm.ppf(1 - 1 / n_trials)
        z_b = norm.ppf(1 - 1 / (n_trials * math.e))
        sr_0_period = sharpe_se_period * (
            (1 - EULER_MASCHERONI) * z_a + EULER_MASCHERONI * z_b
        )

    dsr = float(norm.cdf((sharpe_period - sr_0_period) / sharpe_se_period))

    return DeflatedSharpeResult(
        n_trials=n_trials,
        n_observations=n_observations,
        periods_per_year=periods_per_year,
        sharpe_period=round(sharpe_period, 6),
        sharpe_annualized=round(sharpe_annualized, 4),
        skewness=round(skewness, 4),
        kurtosis_pearson=round(kurtosis_pearson, 4),
        sharpe_std_error_period=round(sharpe_se_period, 6),
        expected_max_sharpe_under_null_period=round(sr_0_period, 6),
        expected_max_sharpe_under_null_annualized=round(
            sr_0_period * math.sqrt(periods_per_year), 4
        ),
        deflated_sharpe_ratio=round(dsr, 4),
        significant_at_95pct=dsr > 0.95,
    )
