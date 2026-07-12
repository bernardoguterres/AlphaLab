"""Tests for the Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)."""

import pytest

from src.backtest.deflated_sharpe import deflated_sharpe_ratio, DeflatedSharpeResult


class TestDeflatedSharpeRatio:
    def test_returns_dataclass_with_expected_fields(self):
        result = deflated_sharpe_ratio(
            sharpe_annualized=1.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=200,
            n_trials=6,
            periods_per_year=52,
        )
        assert isinstance(result, DeflatedSharpeResult)
        assert 0.0 <= result.deflated_sharpe_ratio <= 1.0

    def test_single_trial_has_zero_null_penalty(self):
        result = deflated_sharpe_ratio(
            sharpe_annualized=1.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=200,
            n_trials=1,
            periods_per_year=52,
        )
        assert result.expected_max_sharpe_under_null_period == 0.0

    def test_more_trials_lowers_dsr_for_same_sharpe(self):
        kwargs = dict(
            sharpe_annualized=1.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=200,
            periods_per_year=52,
        )
        dsr_1_trial = deflated_sharpe_ratio(n_trials=1, **kwargs).deflated_sharpe_ratio
        dsr_6_trials = deflated_sharpe_ratio(n_trials=6, **kwargs).deflated_sharpe_ratio
        dsr_50_trials = deflated_sharpe_ratio(
            n_trials=50, **kwargs
        ).deflated_sharpe_ratio

        assert dsr_1_trial > dsr_6_trials > dsr_50_trials

    def test_more_observations_raises_dsr_for_same_sharpe(self):
        kwargs = dict(
            sharpe_annualized=1.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_trials=6,
            periods_per_year=52,
        )
        dsr_short = deflated_sharpe_ratio(
            n_observations=60, **kwargs
        ).deflated_sharpe_ratio
        dsr_long = deflated_sharpe_ratio(
            n_observations=500, **kwargs
        ).deflated_sharpe_ratio

        assert dsr_long > dsr_short

    def test_negative_skew_lowers_dsr_for_positive_sharpe(self):
        """Crash risk (negative skew) should make a positive-Sharpe result
        look less reliable, not more - the SE formula must penalize it."""
        kwargs = dict(
            sharpe_annualized=1.0,
            kurtosis_pearson=3.0,
            n_observations=200,
            n_trials=6,
            periods_per_year=52,
        )
        dsr_neg_skew = deflated_sharpe_ratio(
            skewness=-1.0, **kwargs
        ).deflated_sharpe_ratio
        dsr_zero_skew = deflated_sharpe_ratio(
            skewness=0.0, **kwargs
        ).deflated_sharpe_ratio
        dsr_pos_skew = deflated_sharpe_ratio(
            skewness=1.0, **kwargs
        ).deflated_sharpe_ratio

        assert dsr_neg_skew < dsr_zero_skew < dsr_pos_skew

    def test_fatter_tails_lower_dsr(self):
        kwargs = dict(
            sharpe_annualized=1.0,
            skewness=0.0,
            n_observations=200,
            n_trials=6,
            periods_per_year=52,
        )
        dsr_normal_tails = deflated_sharpe_ratio(
            kurtosis_pearson=3.0, **kwargs
        ).deflated_sharpe_ratio
        dsr_fat_tails = deflated_sharpe_ratio(
            kurtosis_pearson=9.0, **kwargs
        ).deflated_sharpe_ratio

        assert dsr_fat_tails < dsr_normal_tails

    def test_significant_flag_matches_threshold(self):
        # A very high Sharpe with ample observations should clear 0.95.
        result = deflated_sharpe_ratio(
            sharpe_annualized=3.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=500,
            n_trials=6,
            periods_per_year=52,
        )
        assert result.significant_at_95pct == (result.deflated_sharpe_ratio > 0.95)
        assert result.significant_at_95pct is True

    def test_low_sharpe_low_observations_not_significant(self):
        result = deflated_sharpe_ratio(
            sharpe_annualized=0.3,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=20,
            n_trials=6,
            periods_per_year=52,
        )
        assert result.significant_at_95pct is False

    def test_too_few_observations_raises(self):
        with pytest.raises(ValueError):
            deflated_sharpe_ratio(
                sharpe_annualized=1.0,
                skewness=0.0,
                kurtosis_pearson=3.0,
                n_observations=1,
                n_trials=6,
                periods_per_year=52,
            )

    def test_zero_trials_raises(self):
        with pytest.raises(ValueError):
            deflated_sharpe_ratio(
                sharpe_annualized=1.0,
                skewness=0.0,
                kurtosis_pearson=3.0,
                n_observations=200,
                n_trials=0,
                periods_per_year=52,
            )

    def test_annualized_sr0_scales_with_sqrt_periods_per_year(self):
        weekly = deflated_sharpe_ratio(
            sharpe_annualized=1.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=200,
            n_trials=6,
            periods_per_year=52,
        )
        daily = deflated_sharpe_ratio(
            sharpe_annualized=1.0,
            skewness=0.0,
            kurtosis_pearson=3.0,
            n_observations=200,
            n_trials=6,
            periods_per_year=252,
        )
        # Same T and same annualized Sharpe, but daily's per-period Sharpe is
        # smaller (same annual Sharpe spread over more, noisier periods) -
        # expect a different (typically lower, more conservative) DSR.
        assert weekly.deflated_sharpe_ratio != daily.deflated_sharpe_ratio
