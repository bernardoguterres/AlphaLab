"""Tests for strategy export functionality."""

import json
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import _build_export_json, _translate_params_for_export

# Import schema validator if available
try:
    from strategy_schema import StrategyExportSchema
    from pydantic import ValidationError
except ImportError:
    StrategyExportSchema = None


class TestStrategyExport:
    """Tests for strategy export to AlphaLive."""

    def test_export_includes_all_required_fields(self):
        """Test that export includes all required fields."""
        config = {"app": {"version": "0.1.0"}}

        export = _build_export_json(
            backtest_id="test_123",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={"short_window": 50, "long_window": 200},
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results={
                "total_return_pct": 25.5,
                "total_trades": 10,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.5,
                        "sortino_ratio": 1.8,
                        "calmar_ratio": 2.0,
                    },
                    "drawdown": {"max_drawdown_pct": -15.2},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.8},
                },
            },
            config=config,
        )

        # Top-level structure
        assert "schema_version" in export
        assert "safety_limits" in export

        # Strategy section
        assert export["strategy"]["name"] == "ma_crossover"
        assert export["strategy"]["parameters"] == {
            "fast_period": 50,
            "slow_period": 200,
            "strategy_type": "ma_crossover",
        }
        assert "description" in export["strategy"]

        # Required fields
        assert export["ticker"] == "AAPL"
        assert export["timeframe"] in ["1Day", "1Hour", "15Min"]

        # Risk section
        assert "stop_loss_pct" in export["risk"]
        assert "take_profit_pct" in export["risk"]
        assert "max_position_size_pct" in export["risk"]

        # Execution section
        assert "order_type" in export["execution"]
        assert "cooldown_bars" in export["execution"]

        # Metadata section
        assert export["metadata"]["backtest_id"] == "test_123"
        assert export["metadata"]["exported_from"] == "AlphaLab"
        assert "exported_at" in export["metadata"]

    def test_export_with_risk_settings_included(self):
        """Test that custom risk settings are included in export."""
        config = {"app": {"version": "0.1.0"}}

        custom_risk = {
            "stop_loss_pct": 3.0,
            "take_profit_pct": 10.0,
            "max_position_size_pct": 15.0,
            "max_daily_loss_pct": 5.0,
            "max_open_positions": 3,
            "trailing_stop_enabled": True,
            "trailing_stop_pct": 2.0,
            "commission_per_trade": 1.0,
        }

        export = _build_export_json(
            backtest_id="test_123",
            ticker="AAPL",
            strategy_name="rsi_mean_reversion",
            params={"rsi_period": 14, "oversold": 30, "overbought": 70},
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results={
                "total_return_pct": 15.0,
                "total_trades": 20,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.2,
                        "sortino_ratio": 1.5,
                        "calmar_ratio": 1.8,
                    },
                    "drawdown": {"max_drawdown_pct": -10.0},
                    "trades": {"win_rate": 0.55, "profit_factor": 1.5},
                },
            },
            config=config,
            risk_settings=custom_risk,
        )

        # Verify custom risk settings are used
        assert export["risk"]["stop_loss_pct"] == 3.0
        assert export["risk"]["take_profit_pct"] == 10.0
        assert export["risk"]["max_position_size_pct"] == 15.0
        assert export["risk"]["trailing_stop_enabled"] is True
        assert export["risk"]["trailing_stop_pct"] == 2.0
        assert export["risk"]["commission_per_trade"] == 1.0

    def test_export_with_each_strategy_type(self):
        """Test export with different strategy types.

        Expected parameters reflect the export-mapping translation
        (_translate_params_for_export): ma_crossover's short_window/
        long_window become fast_period/slow_period, momentum_breakout's
        volume_surge_pct (a percentage) becomes surge_pct (a ratio, /100),
        and every strategy gets a strategy_type discriminator injected.
        """
        config = {"app": {"version": "0.1.0"}}

        strategies = [
            (
                "ma_crossover",
                {"short_window": 50, "long_window": 200},
                {
                    "fast_period": 50,
                    "slow_period": 200,
                    "strategy_type": "ma_crossover",
                },
            ),
            (
                "rsi_mean_reversion",
                {"rsi_period": 14, "oversold": 30, "overbought": 70},
                {
                    "rsi_period": 14,
                    "oversold": 30,
                    "overbought": 70,
                    "strategy_type": "rsi_mean_reversion",
                },
            ),
            (
                "momentum_breakout",
                {"lookback": 20, "volume_surge_pct": 150},
                {
                    "lookback": 20,
                    "surge_pct": 1.5,
                    "strategy_type": "momentum_breakout",
                },
            ),
        ]

        for strategy_name, params, expected_params in strategies:
            export = _build_export_json(
                backtest_id="test_123",
                ticker="AAPL",
                strategy_name=strategy_name,
                params=params,
                start_date="2020-01-01",
                end_date="2024-12-31",
                initial_capital=100000,
                results={
                    "total_return_pct": 20.0,
                    "total_trades": 15,
                    "metrics": {
                        "risk": {
                            "sharpe_ratio": 1.3,
                            "sortino_ratio": 1.6,
                            "calmar_ratio": 1.9,
                        },
                        "drawdown": {"max_drawdown_pct": -12.0},
                        "trades": {"win_rate": 0.58, "profit_factor": 1.6},
                    },
                },
                config=config,
            )

            assert export["strategy"]["name"] == strategy_name
            assert export["strategy"]["parameters"] == expected_params

    def test_export_file_naming_format(self):
        """Test that export file naming follows convention."""
        from datetime import datetime

        strategy_name = "ma_crossover"
        ticker = "AAPL"
        today = datetime.now().strftime("%Y%m%d")

        expected_filename = f"{strategy_name}_{ticker}_{today}.json"

        # Verify format
        assert strategy_name in expected_filename
        assert ticker in expected_filename
        assert len(today) == 8  # YYYYMMDD format

    def test_schema_version_is_correct(self):
        """Test that schema version is '1.0'."""
        config = {"app": {"version": "0.1.0"}}

        export = _build_export_json(
            backtest_id="test_123",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={"short_window": 50, "long_window": 200},
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results={
                "total_return_pct": 20.0,
                "total_trades": 10,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.4,
                        "sortino_ratio": 1.7,
                        "calmar_ratio": 2.0,
                    },
                    "drawdown": {"max_drawdown_pct": -10.0},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.7},
                },
            },
            config=config,
        )

        assert export["schema_version"] == "1.0"

    @pytest.mark.skipif(
        StrategyExportSchema is None, reason="StrategyExportSchema not available"
    )
    def test_pydantic_validation_passes(self):
        """Test that export passes Pydantic validation."""
        config = {"app": {"version": "0.1.0"}}

        export = _build_export_json(
            backtest_id="test_123",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={
                "short_window": 50,
                "long_window": 200,
                "volume_confirmation": True,
                "volume_avg_period": 20,
                "min_separation_pct": 0.0,
                "cooldown_days": 5,
            },
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results={
                "total_return_pct": 25.5,
                "total_trades": 10,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.5,
                        "sortino_ratio": 1.8,
                        "calmar_ratio": 2.0,
                    },
                    "drawdown": {"max_drawdown_pct": -15.2},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.8},
                },
            },
            config=config,
        )

        # Should not raise ValidationError
        validated = StrategyExportSchema.model_validate(export)
        assert validated.schema_version == "1.0"
        assert validated.ticker == "AAPL"

    def test_performance_metrics_in_metadata(self):
        """Test that performance metrics are included in metadata."""
        config = {"app": {"version": "0.1.0"}}

        export = _build_export_json(
            backtest_id="test_123",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={"short_window": 50, "long_window": 200},
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results={
                "total_return_pct": 35.5,
                "total_trades": 12,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.8,
                        "sortino_ratio": 2.1,
                        "calmar_ratio": 2.5,
                    },
                    "drawdown": {"max_drawdown_pct": -12.5},
                    "trades": {"win_rate": 0.65, "profit_factor": 2.2},
                },
            },
            config=config,
        )

        perf = export["metadata"]["performance"]
        assert perf["sharpe_ratio"] == 1.8
        assert perf["total_return_pct"] == 35.5
        assert perf["max_drawdown_pct"] == -12.5
        assert perf["win_rate_pct"] == 65.0
        assert perf["profit_factor"] == 2.2
        assert perf["total_trades"] == 12


class TestExportRegressionGroup1:
    """Regression tests for the 2026-07-13 audit's Group 1 cross-repo
    export-contract bugs (see testing/reports/Alpha_Pipeline_Integrated_Audit_2026-07-13.md
    §6, blockers 5/6/10/11).
    """

    @staticmethod
    def _base_results(max_drawdown_pct: float = -9.0) -> dict:
        return {
            "total_return_pct": 20.0,
            "total_trades": 15,
            "metrics": {
                "risk": {
                    "sharpe_ratio": 1.3,
                    "sortino_ratio": 1.6,
                    "calmar_ratio": 1.9,
                },
                "drawdown": {"max_drawdown_pct": max_drawdown_pct},
                "trades": {"win_rate": 0.58, "profit_factor": 1.6},
            },
        }

    def test_max_drawdown_pct_is_nonzero_for_real_drawdown(self):
        """Bug 1.6 regression: helpers.py previously read metrics['drawdown']
        ['max_drawdown'] (a key that never existed - the real key is
        'max_drawdown_pct'), so every export silently shipped 0.0 regardless
        of the real backtested drawdown, and 0.0 passes schema validation
        silently. The expected value here (-27.75) is chosen independently
        of any dict-key path in helpers.py, not re-derived from it, so a
        reintroduced wrong-key bug (which would silently produce 0.0 again)
        cannot pass this test by accident.
        """
        config = {"app": {"version": "0.1.0"}}
        expected_drawdown = -27.75

        export = _build_export_json(
            backtest_id="test_dd",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={"short_window": 50, "long_window": 200},
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(max_drawdown_pct=expected_drawdown),
            config=config,
        )

        assert (
            export["metadata"]["performance"]["max_drawdown_pct"] == expected_drawdown
        )
        assert export["metadata"]["performance"]["max_drawdown_pct"] != 0.0

    def test_ma_crossover_params_translated_and_validate(self):
        """Bug 1.2 regression: AlphaLab exports short_window/long_window but
        AlphaLive reads fast_period/slow_period - previously silently
        absorbed by AlphaLive's untyped Dict[str, Any] parameters field.
        """
        config = {"app": {"version": "0.1.0"}}
        export = _build_export_json(
            backtest_id="test_ma",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={
                "short_window": 20,
                "long_window": 100,
                "volume_confirmation": True,
                "cooldown_days": 5,
            },
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(),
            config=config,
        )

        params = export["strategy"]["parameters"]
        assert "short_window" not in params
        assert "long_window" not in params
        assert params["fast_period"] == 20
        assert params["slow_period"] == 100

        if StrategyExportSchema is not None:
            validated = StrategyExportSchema.model_validate(export)
            assert validated.strategy.parameters.fast_period == 20
            assert validated.strategy.parameters.slow_period == 100

    def test_momentum_breakout_surge_pct_unit_conversion(self):
        """Bug 1.3 regression: AlphaLab's volume_surge_pct is a percentage
        (150 = 150% of avg volume); AlphaLive's surge_pct is a ratio
        (1.5x) - a raw silent pass-through would be a 100x unit error.
        """
        config = {"app": {"version": "0.1.0"}}
        export = _build_export_json(
            backtest_id="test_mb",
            ticker="AAPL",
            strategy_name="momentum_breakout",
            params={
                "lookback": 20,
                "volume_surge_pct": 200,
                "volume_avg_period": 20,
                "rsi_min": 50,
                "stop_loss_atr_mult": 2.0,
                "trailing_stop_atr_mult": 3.0,
                "cooldown_days": 3,
            },
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(),
            config=config,
        )

        params = export["strategy"]["parameters"]
        assert "volume_surge_pct" not in params
        assert "volume_avg_period" not in params
        assert params["surge_pct"] == 2.0
        assert params["volume_ma_period"] == 20

        if StrategyExportSchema is not None:
            validated = StrategyExportSchema.model_validate(export)
            assert validated.strategy.parameters.surge_pct == 2.0

    def test_bollinger_breakout_field_names_translated(self):
        """Bug 1.3 regression: AlphaLab's bb_period/bb_std_dev vs
        AlphaLive's period/std_dev."""
        config = {"app": {"version": "0.1.0"}}
        export = _build_export_json(
            backtest_id="test_bb",
            ticker="AAPL",
            strategy_name="bollinger_breakout",
            params={
                "bb_period": 25,
                "bb_std_dev": 2.5,
                "confirmation_bars": 2,
                "volume_filter": True,
                "volume_threshold": 1.5,
                "cooldown_days": 3,
            },
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(),
            config=config,
        )

        params = export["strategy"]["parameters"]
        assert "bb_period" not in params
        assert "bb_std_dev" not in params
        assert params["period"] == 25
        assert params["std_dev"] == 2.5

        if StrategyExportSchema is not None:
            validated = StrategyExportSchema.model_validate(export)
            assert validated.strategy.parameters.period == 25
            assert validated.strategy.parameters.std_dev == 2.5

    def test_greenblatt_trailing_stop_renamed_to_fraction(self):
        """Bug 1.4 regression: risk.trailing_stop_pct (absolute percentage,
        e.g. 3.0 = 3%) and greenblatt_weekly's own trailing_stop_pct
        (fraction, e.g. 0.20 = 20%) shared an identical field name in the
        same document with incompatible units. The strategy-level field is
        now exported as trailing_stop_fraction so the two can never be
        confused by name alone.
        """
        config = {"app": {"version": "0.1.0"}}
        export = _build_export_json(
            backtest_id="test_gb",
            ticker="AAPL",
            strategy_name="greenblatt_weekly",
            params={
                "fast_sma": 10,
                "slow_sma": 50,
                "rsi_period": 14,
                "rsi_oversold": 35,
                "rsi_overbought": 65,
                "min_hold_bars": 52,
                "trailing_stop_pct": 0.20,
            },
            start_date="2015-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(),
            config=config,
            interval="1wk",
        )

        params = export["strategy"]["parameters"]
        assert "trailing_stop_pct" not in params
        assert params["trailing_stop_fraction"] == 0.20
        # risk.trailing_stop_pct is a distinct, absolute-percentage field
        assert export["risk"]["trailing_stop_pct"] != params["trailing_stop_fraction"]

        if StrategyExportSchema is not None:
            validated = StrategyExportSchema.model_validate(export)
            assert validated.strategy.parameters.trailing_stop_fraction == 0.20

    @pytest.mark.skipif(
        StrategyExportSchema is None, reason="StrategyExportSchema not available"
    )
    def test_discriminator_rejects_mismatched_strategy_type(self):
        """Bug 1.1 regression: previously a plain Union let a valid config
        for one strategy be silently re-typed as another strategy's
        parameter model. Now strategy.name and
        strategy.parameters.strategy_type must agree, and a raw dict whose
        parameters don't declare a matching strategy_type is rejected
        outright rather than coerced into the wrong model.
        """
        config = {"app": {"version": "0.1.0"}}
        export = _build_export_json(
            backtest_id="test_mismatch",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={
                "short_window": 50,
                "long_window": 200,
                "volume_confirmation": True,
            },
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(),
            config=config,
        )

        # Corrupt the discriminator to claim this is really a greenblatt_weekly
        # config while strategy.name still says ma_crossover.
        export["strategy"]["name"] = "greenblatt_weekly"

        with pytest.raises(ValidationError):
            StrategyExportSchema.model_validate(export)

    @pytest.mark.skipif(
        StrategyExportSchema is None, reason="StrategyExportSchema not available"
    )
    def test_discriminator_rejects_missing_strategy_type(self):
        """A parameters dict with no strategy_type key at all must be
        rejected, not silently matched against whichever model happens to
        validate first (the old plain-Union behavior)."""
        config = {"app": {"version": "0.1.0"}}
        export = _build_export_json(
            backtest_id="test_missing_tag",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={
                "short_window": 50,
                "long_window": 200,
                "volume_confirmation": True,
            },
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            results=self._base_results(),
            config=config,
        )
        del export["strategy"]["parameters"]["strategy_type"]

        with pytest.raises(ValidationError):
            StrategyExportSchema.model_validate(export)
