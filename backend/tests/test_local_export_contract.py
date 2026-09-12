"""Local, always-running AlphaLive export-contract safeguard.

test_schema_contract.py compares AlphaLab's and AlphaLive's live Pydantic
schemas field-for-field, but it SKIPS entirely when AlphaLive isn't checked
out as a sibling directory (see that file's docstring) - and CI's cross-repo
checkout step runs with continue-on-error, so a missing/misscoped secret
degrades to the same skip there too. That leaves no protection at all in an
environment where AlphaLive simply isn't present.

This file is the local, self-contained replacement for that gap: a small,
explicitly versioned JSON fixture (tests/fixtures/export_contract_v1.0.json)
records what AlphaLab's OWN StrategyExportSchema currently produces for each
exportable strategy - required/optional fields, nested block shapes, alias
translations, strategy identifiers, schema_version - and every test below
validates against that fixture, not against AlphaLive. It cannot prove
AlphaLive would still accept a given export (only the cross-repo test does
that); it can catch AlphaLab silently changing its own export shape.

Refresh policy: see the fixture's own "refresh_policy" field. A diff here
means either a real, accidental drift (fix the code) or a deliberate export
shape change (update the fixture, bump contract_version, explain why in the
commit).
"""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from alphalab.api.helpers import _build_export_json, _translate_params_for_export
from alphalab.api.routes import create_app
from strategy_schema import StrategyExportSchema
from alphalab.strategies.implementations import (
    BollingerBreakout,
    BollingerRSICombo,
    GreenblattWeekly,
    MomentumBreakout,
    MovingAverageCrossover,
    RSIMeanReversion,
    TrendAdaptiveRSI,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "export_contract_v1.0.json"

with open(_FIXTURE_PATH) as f:
    CONTRACT = json.load(f)

# One instantiated strategy per exportable strategy, so its own
# validate_params()-applied defaults (not hand-duplicated literals) drive
# the export - if a default ever changes, this test picks up the new value
# automatically rather than silently comparing against a stale hardcode.
_STRATEGY_INSTANCES = {
    "ma_crossover": MovingAverageCrossover(),
    "rsi_mean_reversion": RSIMeanReversion(),
    "momentum_breakout": MomentumBreakout(),
    "bollinger_breakout": BollingerBreakout(),
    "bollinger_rsi_combo": BollingerRSICombo(),
    "trend_adaptive_rsi": TrendAdaptiveRSI(),
    "greenblatt_weekly": GreenblattWeekly(),
}

_FAKE_RESULTS = {
    "total_return_pct": 12.3,
    "total_trades": 4,
    "metrics": {
        "risk": {"sharpe_ratio": 1.1, "sortino_ratio": 1.4, "calmar_ratio": 1.8},
        "drawdown": {"max_drawdown_pct": -9.5},
        "trades": {"win_rate": 0.5, "profit_factor": 1.6},
    },
}
_FAKE_CONFIG = {"app": {"version": "0.1.0"}}


def _export_for(strategy_name: str) -> dict:
    """Build the export JSON exactly the way POST /api/strategies/export
    actually returns it: _build_export_json()'s raw dict, THEN
    StrategyExportSchema.model_validate(...).model_dump(mode="json",
    exclude_none=True) - the same two-step sequence
    alphalab/api/blueprints/backtest.py's export_strategy() runs.

    This distinction is load-bearing, not cosmetic: the schema-validation
    step can itself change the field set. Discovered during this pass -
    rsi_mean_reversion's raw dict carries `cooldown_days` (a real internal
    strategy param) but AlphaLab's own RSIMeanReversionParams export model
    doesn't declare that field, so it's silently dropped by Pydantic's
    default extra="ignore" behavior; separately, that same model declares
    `bb_period`/`bb_std` with defaults (20, 2.0) that RSIMeanReversion never
    accepts as tunable params internally (FeatureEngineer's Bollinger Bands
    are fixed at 20/2.0, not per-strategy-configurable), so those two
    fields appear in the final export despite never being backtested as
    parameters. Values aren't lost: cooldown_days's actual value already
    flows into execution.cooldown_bars via _build_export_json's execution
    block, independent of this drop - and 20/2.0 happens to be correct
    regardless, since that's what FeatureEngineer always computes anyway.
    Testing only the raw dict (as an earlier version of this fixture and
    test did) would have missed this real difference between the two
    layers.
    """
    strategy = _STRATEGY_INSTANCES[strategy_name]
    raw = _build_export_json(
        backtest_id="contract_test",
        ticker="AAPL",
        strategy_name=strategy_name,
        params=strategy.params,
        start_date="2020-01-01",
        end_date="2024-12-31",
        initial_capital=100_000,
        results=_FAKE_RESULTS,
        config=_FAKE_CONFIG,
    )
    validated = StrategyExportSchema.model_validate(raw)
    return validated.model_dump(mode="json", exclude_none=True)


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestFixtureItselfIsCurrent:
    def test_fixture_schema_version_matches_live_schema(self):
        assert CONTRACT["schema_version"] == "1.0"
        # StrategyExportSchema.schema_version is a Literal["1.0"] - if the
        # live schema's version literal is ever bumped, this must be too.
        field = StrategyExportSchema.model_fields["schema_version"]
        assert "1.0" in str(field.annotation)

    def test_fixture_lists_exactly_the_seven_exportable_strategies(self):
        from alphalab.api.blueprints.backtest import STRATEGY_MAP

        assert set(CONTRACT["exportable_strategies"].keys()) == set(
            STRATEGY_MAP.keys()
        ) - set(CONTRACT["rejected_strategies"].keys())
        assert set(CONTRACT["rejected_strategies"].keys()) == {
            "rsi_simple",
            "vwap_reversion",
        }


class TestExportableStrategiesMatchTheLocalContract:
    @pytest.mark.parametrize("strategy_name", list(_STRATEGY_INSTANCES.keys()))
    def test_export_validates_against_strategy_export_schema(self, strategy_name):
        export_json = _export_for(strategy_name)
        validated = StrategyExportSchema.model_validate(export_json)
        assert validated.strategy.name == strategy_name

    @pytest.mark.parametrize("strategy_name", list(_STRATEGY_INSTANCES.keys()))
    def test_top_level_required_fields_present(self, strategy_name):
        export_json = _export_for(strategy_name)
        for field in CONTRACT["top_level_required_fields"]:
            assert field in export_json, f"{strategy_name}: missing {field!r}"

    @pytest.mark.parametrize("strategy_name", list(_STRATEGY_INSTANCES.keys()))
    def test_nested_block_fields_match_contract(self, strategy_name):
        export_json = _export_for(strategy_name)
        assert set(export_json["risk"].keys()) == set(CONTRACT["risk_fields"])
        assert set(export_json["execution"].keys()) == set(CONTRACT["execution_fields"])
        assert set(export_json["safety_limits"].keys()) == set(
            CONTRACT["safety_limits_fields"]
        )
        assert set(export_json["metadata"].keys()) == set(CONTRACT["metadata_fields"])

    @pytest.mark.parametrize("strategy_name", list(_STRATEGY_INSTANCES.keys()))
    def test_strategy_parameter_field_names_match_contract(self, strategy_name):
        export_json = _export_for(strategy_name)
        actual_fields = set(export_json["strategy"]["parameters"].keys())
        expected_fields = set(
            CONTRACT["exportable_strategies"][strategy_name]["parameter_fields"]
        )
        assert actual_fields == expected_fields, (
            f"{strategy_name}: export parameter field set drifted from the "
            f"local contract - a real change (update the fixture + bump "
            f"contract_version) or an accidental one (fix the code)."
        )

    @pytest.mark.parametrize("strategy_name", list(_STRATEGY_INSTANCES.keys()))
    def test_internal_to_export_alias_translation(self, strategy_name):
        strategy = _STRATEGY_INSTANCES[strategy_name]
        aliases = CONTRACT["exportable_strategies"][strategy_name][
            "internal_to_export_aliases"
        ]
        translated = _translate_params_for_export(strategy_name, strategy.params)
        for internal_name, export_name in aliases.items():
            assert internal_name in strategy.params, (
                f"{strategy_name}: fixture claims an alias from "
                f"{internal_name!r}, but that isn't even one of this "
                f"strategy's internal params"
            )
            assert export_name in translated, (
                f"{strategy_name}: expected exported field {export_name!r} "
                f"(aliased from internal {internal_name!r}) is missing"
            )
            assert internal_name not in translated or internal_name == export_name, (
                f"{strategy_name}: internal name {internal_name!r} leaked "
                f"into the export unchanged instead of being renamed to "
                f"{export_name!r}"
            )


class TestNestedTypesAndValueConstraints:
    def test_risk_block_types(self):
        export_json = _export_for("ma_crossover")
        risk = export_json["risk"]
        assert isinstance(risk["stop_loss_pct"], (int, float))
        assert isinstance(risk["max_open_positions"], int)
        assert isinstance(risk["trailing_stop_enabled"], bool)

    def test_wrong_nested_type_is_rejected(self):
        export_json = _export_for("ma_crossover")
        export_json["risk"]["stop_loss_pct"] = "not-a-number"
        with pytest.raises(ValidationError):
            StrategyExportSchema.model_validate(export_json)

    def test_missing_required_top_level_field_is_rejected(self):
        export_json = _export_for("ma_crossover")
        del export_json["risk"]
        with pytest.raises(ValidationError):
            StrategyExportSchema.model_validate(export_json)

    def test_wrong_schema_version_is_rejected(self):
        export_json = _export_for("ma_crossover")
        export_json["schema_version"] = "2.0"
        with pytest.raises(ValidationError):
            StrategyExportSchema.model_validate(export_json)

    def test_strategy_name_parameters_mismatch_is_rejected(self):
        """strategy.name must match strategy.parameters.strategy_type - the
        discriminated union + validate_name_matches_parameters() guard
        against one strategy's config being silently validated as another's
        (this is the exact bug class test_schema_contract.py's own docstring
        cites: a field renamed on one side and not the other)."""
        ma_export = _export_for("ma_crossover")
        greenblatt_export = _export_for("greenblatt_weekly")
        mismatched = dict(ma_export)
        mismatched["strategy"] = dict(ma_export["strategy"])
        mismatched["strategy"]["parameters"] = greenblatt_export["strategy"][
            "parameters"
        ]
        with pytest.raises(ValidationError):
            StrategyExportSchema.model_validate(mismatched)


class TestRejectedStrategiesStayRejected:
    def _store_and_export(self, client, strategy_name):
        app = client.application
        results_store = app.extensions["results_store"]
        instance = _STRATEGY_INSTANCES.get(strategy_name)
        params = dict(instance.params) if instance is not None else {}
        results_store["contract_test_reject"] = {
            "results": {"total_return_pct": 0, "total_trades": 0, "metrics": {}},
            "request": {
                "ticker": "AAPL",
                "strategy": strategy_name,
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100_000,
                "params": params,
                "risk_settings": None,
                "interval": "1d",
            },
        }
        return client.post(
            "/api/strategies/export",
            json={"backtest_id": "contract_test_reject"},
        )

    def test_rsi_simple_is_rejected(self, client):
        resp = self._store_and_export(client, "rsi_simple")
        assert resp.status_code == 422

    def test_vwap_reversion_is_rejected(self, client):
        resp = self._store_and_export(client, "vwap_reversion")
        assert resp.status_code == 422

    @pytest.mark.parametrize("strategy_name", list(_STRATEGY_INSTANCES.keys()))
    def test_exportable_strategies_are_not_rejected_by_the_route(
        self, client, strategy_name
    ):
        resp = self._store_and_export(client, strategy_name)
        assert resp.status_code != 422 or "not found" in resp.get_data(as_text=True)


class TestOptionalCrossRepoTestAbsenceIsHandledSeparately:
    """Documents (doesn't re-implement) how the optional live cross-repo
    comparison degrades - see test_schema_contract.py's own module
    docstring and skip guard for the actual behavior. This test only
    confirms that file's skip mechanism exists so a refactor can't silently
    drop it without any test noticing."""

    def test_schema_contract_module_has_a_skip_guard_for_missing_alphalive(self):
        contract_test_path = Path(__file__).parent / "test_schema_contract.py"
        source = contract_test_path.read_text()
        assert "pytest.skip" in source
        assert "allow_module_level=True" in source
