"""Regression tests for strategy parameter validation: every strategy must
reject an unrecognized parameter name at construction time rather than
silently accepting it into self.params and never reading it (a typo like
"lookbakc" or a stale/foreign param name used to pass through validate_params
untouched, with no signal that it had zero effect on generate_signals()).

Also verifies the specific naming facts CLAUDE.md documents and this
hardening pass was asked to confirm: rsi_simple uses `period` (default 14),
not `rsi_period`; greenblatt_weekly uses `trailing_stop_pct` internally as a
0-1 fraction.
"""

import pytest

from alphalab.strategies.implementations import (
    BollingerBreakout,
    BollingerRSICombo,
    GreenblattWeekly,
    MomentumBreakout,
    MovingAverageCrossover,
    RSIMeanReversion,
    RSISimple,
    TrendAdaptiveRSI,
    VWAPReversion,
)

# (strategy_class, one valid non-default param to prove the class still
# constructs fine, unknown param name to prove rejection)
STRATEGIES = [
    (MovingAverageCrossover, {"short_window": 10}),
    (RSIMeanReversion, {"rsi_period": 10}),
    (RSISimple, {"period": 10}),
    (MomentumBreakout, {"lookback": 10}),
    (BollingerBreakout, {"bb_period": 10}),
    (VWAPReversion, {"vwap_period": 10}),
    (BollingerRSICombo, {"bb_period": 10}),
    (TrendAdaptiveRSI, {"trend_sma": 40}),
    (GreenblattWeekly, {"fast_sma": 5, "slow_sma": 20}),
]


class TestUnknownParameterRejection:
    @pytest.mark.parametrize("strategy_cls,valid_override", STRATEGIES)
    def test_valid_params_construct_fine(self, strategy_cls, valid_override):
        strategy_cls(dict(valid_override))

    @pytest.mark.parametrize("strategy_cls,valid_override", STRATEGIES)
    def test_unknown_param_is_rejected(self, strategy_cls, valid_override):
        bad = dict(valid_override)
        bad["definitely_not_a_real_param"] = 123
        with pytest.raises(ValueError, match="unknown parameter"):
            strategy_cls(bad)

    def test_defaults_construct_with_no_params(self):
        for cls, _ in STRATEGIES:
            cls()  # must not raise


class TestRSISimpleParamNaming:
    """rsi_simple must use `period`, default 14 - not `rsi_period` (that
    name belongs to rsi_mean_reversion/vwap_reversion/others and is a
    different strategy's field)."""

    def test_default_period_is_14(self):
        s = RSISimple()
        assert s.params["period"] == 14

    def test_period_accepted(self):
        s = RSISimple({"period": 21})
        assert s.params["period"] == 21

    def test_rsi_period_is_rejected_as_unknown(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            RSISimple({"rsi_period": 21})


class TestGreenblattWeeklyTrailingStopNaming:
    """greenblatt_weekly's internal field is `trailing_stop_pct`, a 0-1
    fraction (0.20 = 20%) - export renames it to `trailing_stop_fraction`
    (see alphalab/api/helpers.py::_translate_params_for_export). The two
    names must not both be accepted internally."""

    def test_default_is_020_fraction(self):
        s = GreenblattWeekly()
        assert s.params["trailing_stop_pct"] == 0.20

    def test_trailing_stop_fraction_rejected_internally(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            GreenblattWeekly({"trailing_stop_fraction": 0.20})

    def test_export_translates_pct_to_fraction(self):
        from alphalab.api.helpers import _translate_params_for_export

        out = _translate_params_for_export(
            "greenblatt_weekly", {"trailing_stop_pct": 0.20, "fast_sma": 10}
        )
        assert out["trailing_stop_fraction"] == 0.20
        assert "trailing_stop_pct" not in out
        assert out["strategy_type"] == "greenblatt_weekly"


class TestParameterIsolation:
    """A parameter belonging to one strategy must not be silently accepted
    by an unrelated strategy just because the name happens to exist
    somewhere in the codebase (e.g. `bb_period` is BollingerBreakout's and
    BollingerRSICombo's, not MovingAverageCrossover's)."""

    def test_bb_period_rejected_by_ma_crossover(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            MovingAverageCrossover({"bb_period": 20})

    def test_short_window_rejected_by_rsi_mean_reversion(self):
        with pytest.raises(ValueError, match="unknown parameter"):
            RSIMeanReversion({"short_window": 10})

    def test_trailing_stop_pct_rejected_by_momentum_breakout(self):
        """momentum_breakout has its own `trailing_stop_atr_mult` -
        greenblatt_weekly's differently-shaped `trailing_stop_pct` (a 0-1
        fraction, not an ATR multiplier) must not silently apply."""
        with pytest.raises(ValueError, match="unknown parameter"):
            MomentumBreakout({"trailing_stop_pct": 0.20})


class TestNonDefaultParamsChangeBehavior:
    """A handful of spot checks that a non-default parameter value actually
    reaches generate_signals() and changes what it computes, rather than
    being accepted but silently unused."""

    def test_rsi_simple_oversold_threshold_changes_signal_count(self):
        from helpers import make_featured_data

        data = make_featured_data(n=300)
        loose = RSISimple({"oversold": 49, "overbought": 51})
        tight = RSISimple({"oversold": 5, "overbought": 95})
        loose_signals = (loose.generate_signals(data)["signal"] != 0).sum()
        tight_signals = (tight.generate_signals(data)["signal"] != 0).sum()
        assert loose_signals > tight_signals

    def test_ma_crossover_window_changes_signal_timing(self):
        from helpers import make_featured_data

        data = make_featured_data(n=300)
        fast = MovingAverageCrossover(
            {"short_window": 5, "long_window": 20, "volume_confirmation": False}
        )
        slow = MovingAverageCrossover(
            {"short_window": 20, "long_window": 100, "volume_confirmation": False}
        )
        fast_signals = fast.generate_signals(data)
        slow_signals = slow.generate_signals(data)
        assert not fast_signals["signal"].equals(slow_signals["signal"])
