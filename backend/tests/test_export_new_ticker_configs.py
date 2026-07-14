"""Regression tests for scripts/export_new_ticker_configs.py (audit bug 3.7).

The script passed fast_period/slow_period (AlphaLive's export-contract
names) directly to MovingAverageCrossover(), whose own validate_params()
only recognizes short_window/long_window - the unrecognized keys were
silently ignored (setdefault()) and the class fell back to its own 50/200
defaults. The backtest that produced the shipped GLD/IWM/XLK performance
numbers therefore ran a different crossover than the 20/50 one the exported
JSON's parameters claimed. _internal_params() now translates export-facing
names to the class's own internal names only for the strategy instantiation
used to run the backtest - the exported JSON's parameters are unaffected
(fast_period/slow_period are already the correct AlphaLive-facing names).

Also covers a second, unrelated bug found while verifying this one: a
print() statement left outside main() (no indentation) crashed on both
import and direct execution with NameError before ever reaching main().
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_new_ticker_configs import _internal_params, JOBS  # noqa: E402
from src.strategies.implementations.moving_average_crossover import (  # noqa: E402
    MovingAverageCrossover,
)


def test_module_imports_without_crashing():
    """The print(f"...{len(exports)}...") left outside main() crashed at
    import time (NameError: 'exports' not defined at module level) - if
    this test file's import above succeeded, that regression is fixed."""
    import export_new_ticker_configs  # noqa: F401


def test_ma_crossover_translates_to_internal_param_names():
    internal = _internal_params("ma_crossover", {"fast_period": 20, "slow_period": 50})
    assert internal == {"short_window": 20, "long_window": 50}


def test_ma_crossover_strategy_actually_uses_translated_windows():
    """The core of the bug: instantiate the real strategy class with the
    translated params and confirm it uses 20/50, not its own 50/200
    defaults (which is what happened silently before this fix)."""
    for job in JOBS:
        if job["strategy_name"] != "ma_crossover":
            continue
        internal = _internal_params(job["strategy_name"], job["params"])
        strategy = MovingAverageCrossover(internal)
        assert strategy.params["short_window"] == job["params"]["fast_period"]
        assert strategy.params["long_window"] == job["params"]["slow_period"]
        # Sanity: this would have failed before the fix (defaults are 50/200)
        assert (
            strategy.params["short_window"] != 50 or job["params"]["fast_period"] == 50
        )
        assert (
            strategy.params["long_window"] != 200 or job["params"]["slow_period"] == 200
        )


def test_export_params_unchanged_by_translation():
    """job["params"] (what ends up in the exported JSON) must stay in
    AlphaLive's export-facing names - only the strategy instantiation used
    for the internal backtest gets translated, never the export dict."""
    for job in JOBS:
        if job["strategy_name"] != "ma_crossover":
            continue
        original = dict(job["params"])
        _internal_params(job["strategy_name"], job["params"])
        assert job["params"] == original
        assert "fast_period" in job["params"]
        assert "slow_period" in job["params"]


def test_non_ma_crossover_params_pass_through_unchanged():
    params = {"period": 14, "oversold": 30, "overbought": 70}
    assert _internal_params("rsi_mean_reversion", params) == params
