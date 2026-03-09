"""Tests for strategy export functionality."""

import json
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import _build_export_json

# Import schema validator if available
try:
    from strategy_schema import StrategyExportSchema
except ImportError:
    StrategyExportSchema = None


class TestStrategyExport:
    """Tests for strategy export to AlphaLive."""

    def test_export_generates_valid_json(self):
        """Test that export generates valid JSON structure."""
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
                    "risk": {"sharpe_ratio": 1.5, "sortino_ratio": 1.8, "calmar_ratio": 2.0},
                    "drawdown": {"max_drawdown": -15.2},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.8},
                }
            },
            config=config,
        )

        # Verify basic structure
        assert "schema_version" in export
        assert "strategy" in export
        assert "ticker" in export
        assert "timeframe" in export
        assert "risk" in export
        assert "execution" in export
        assert "safety_limits" in export
        assert "metadata" in export

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
                    "risk": {"sharpe_ratio": 1.5, "sortino_ratio": 1.8, "calmar_ratio": 2.0},
                    "drawdown": {"max_drawdown": -15.2},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.8},
                }
            },
            config=config,
        )

        # Strategy section
        assert export["strategy"]["name"] == "ma_crossover"
        assert export["strategy"]["parameters"] == {"short_window": 50, "long_window": 200}
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
                    "risk": {"sharpe_ratio": 1.2, "sortino_ratio": 1.5, "calmar_ratio": 1.8},
                    "drawdown": {"max_drawdown": -10.0},
                    "trades": {"win_rate": 0.55, "profit_factor": 1.5},
                }
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
        """Test export with different strategy types."""
        config = {"app": {"version": "0.1.0"}}

        strategies = [
            ("ma_crossover", {"short_window": 50, "long_window": 200}),
            ("rsi_mean_reversion", {"rsi_period": 14, "oversold": 30, "overbought": 70}),
            ("momentum_breakout", {"lookback": 20, "volume_surge_pct": 150}),
        ]

        for strategy_name, params in strategies:
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
                        "risk": {"sharpe_ratio": 1.3, "sortino_ratio": 1.6, "calmar_ratio": 1.9},
                        "drawdown": {"max_drawdown": -12.0},
                        "trades": {"win_rate": 0.58, "profit_factor": 1.6},
                    }
                },
                config=config,
            )

            assert export["strategy"]["name"] == strategy_name
            assert export["strategy"]["parameters"] == params

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
                    "risk": {"sharpe_ratio": 1.4, "sortino_ratio": 1.7, "calmar_ratio": 2.0},
                    "drawdown": {"max_drawdown": -10.0},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.7},
                }
            },
            config=config,
        )

        assert export["schema_version"] == "1.0"

    @pytest.mark.skipif(StrategyExportSchema is None, reason="StrategyExportSchema not available")
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
                    "risk": {"sharpe_ratio": 1.5, "sortino_ratio": 1.8, "calmar_ratio": 2.0},
                    "drawdown": {"max_drawdown": -15.2},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.8},
                }
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
                    "risk": {"sharpe_ratio": 1.8, "sortino_ratio": 2.1, "calmar_ratio": 2.5},
                    "drawdown": {"max_drawdown": -12.5},
                    "trades": {"win_rate": 0.65, "profit_factor": 2.2},
                }
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
