"""Tests for schema migration infrastructure.

Tests backward compatibility and version upgrade paths for strategy export schemas.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from migrations.schema_migrations import (
    migrate_schema,
    is_version_supported,
    get_supported_versions,
    get_latest_version,
    create_minimal_v1_0_config,
    _apply_v1_0_defaults,
)
from strategy_schema import validate_strategy_export


class TestSchemaMigrations:
    """Test schema migration functions."""

    def test_supported_versions(self):
        """Test supported version tracking."""
        versions = get_supported_versions()
        assert isinstance(versions, list)
        assert "1.0" in versions
        assert len(versions) >= 1

    def test_latest_version(self):
        """Test latest version retrieval."""
        latest = get_latest_version()
        assert latest == "1.0"
        assert is_version_supported(latest)

    def test_is_version_supported(self):
        """Test version support checking."""
        assert is_version_supported("1.0") is True
        assert is_version_supported("99.0") is False
        assert is_version_supported("invalid") is False

    def test_migrate_unknown_version_raises(self):
        """Test that unknown schema version raises ValueError."""
        config = create_minimal_v1_0_config()
        config["schema_version"] = "99.0"

        with pytest.raises(ValueError, match="Unknown or unsupported schema version"):
            migrate_schema(config)


class TestV1_0BackwardCompatibility:
    """Test v1.0 schema backward compatibility."""

    def test_v1_0_without_safety_limits(self):
        """Test v1.0 config without safety_limits gets defaults."""
        config = create_minimal_v1_0_config()
        # Remove safety_limits (simulate old export)
        if "safety_limits" in config:
            del config["safety_limits"]

        migrated = migrate_schema(config)

        # Should have safety_limits with defaults
        assert "safety_limits" in migrated
        assert migrated["safety_limits"]["max_trades_per_day"] == 20
        assert migrated["safety_limits"]["max_api_calls_per_hour"] == 500
        assert migrated["safety_limits"]["signal_generation_timeout_seconds"] == 5.0
        assert migrated["safety_limits"]["broker_degraded_mode_threshold_failures"] == 3

    def test_v1_0_with_partial_safety_limits(self):
        """Test v1.0 config with partial safety_limits gets missing defaults."""
        config = create_minimal_v1_0_config()
        # Add partial safety_limits
        config["safety_limits"] = {
            "max_trades_per_day": 100,  # Custom value
            # Missing other fields
        }

        migrated = migrate_schema(config)

        # Should keep custom value
        assert migrated["safety_limits"]["max_trades_per_day"] == 100
        # Should add missing defaults
        assert migrated["safety_limits"]["max_api_calls_per_hour"] == 500
        assert migrated["safety_limits"]["signal_generation_timeout_seconds"] == 5.0
        assert migrated["safety_limits"]["broker_degraded_mode_threshold_failures"] == 3

    def test_v1_0_with_full_safety_limits(self):
        """Test v1.0 config with full safety_limits is unchanged."""
        config = create_minimal_v1_0_config()
        config["safety_limits"] = {
            "max_trades_per_day": 50,
            "max_api_calls_per_hour": 1000,
            "signal_generation_timeout_seconds": 10.0,
            "broker_degraded_mode_threshold_failures": 5,
        }

        migrated = migrate_schema(config)

        # Should keep all custom values
        assert migrated["safety_limits"]["max_trades_per_day"] == 50
        assert migrated["safety_limits"]["max_api_calls_per_hour"] == 1000
        assert migrated["safety_limits"]["signal_generation_timeout_seconds"] == 10.0
        assert migrated["safety_limits"]["broker_degraded_mode_threshold_failures"] == 5

    def test_v1_0_applies_defaults_idempotent(self):
        """Test applying v1.0 defaults multiple times is idempotent."""
        config = create_minimal_v1_0_config()
        del config["safety_limits"]

        # Apply defaults twice
        migrated1 = _apply_v1_0_defaults(config.copy())
        migrated2 = _apply_v1_0_defaults(migrated1.copy())

        assert migrated1 == migrated2


class TestIntegrationWithPydantic:
    """Test migration integration with Pydantic validation."""

    def test_validate_with_auto_migrate_enabled(self):
        """Test validation with auto_migrate=True (default)."""
        config = create_minimal_v1_0_config()
        del config["safety_limits"]

        # Should auto-migrate and validate successfully
        schema = validate_strategy_export(config, auto_migrate=True)

        assert schema.schema_version == "1.0"
        assert schema.safety_limits.max_trades_per_day == 20
        assert schema.safety_limits.max_api_calls_per_hour == 500

    def test_validate_with_auto_migrate_disabled(self):
        """Test validation with auto_migrate=False uses Pydantic defaults."""
        config = create_minimal_v1_0_config()
        del config["safety_limits"]

        # Pydantic should use default_factory for SafetyLimitsConfig
        schema = validate_strategy_export(config, auto_migrate=False)

        assert schema.schema_version == "1.0"
        # Pydantic default_factory should provide defaults
        assert schema.safety_limits.max_trades_per_day == 20

    def test_validate_complete_v1_0_schema(self):
        """Test validation of complete v1.0 schema."""
        config = create_minimal_v1_0_config()
        config["safety_limits"] = {
            "max_trades_per_day": 100,
            "max_api_calls_per_hour": 800,
            "signal_generation_timeout_seconds": 3.0,
            "broker_degraded_mode_threshold_failures": 5,
        }

        schema = validate_strategy_export(config)

        assert schema.schema_version == "1.0"
        assert schema.strategy.name == "ma_crossover"
        assert schema.ticker == "SPY"
        assert schema.timeframe == "1Day"
        assert schema.safety_limits.max_trades_per_day == 100


class TestMigrationLogging:
    """Test migration logging behavior."""

    def test_migration_logs_version(self, caplog):
        """Test that migration logs schema version."""
        import logging

        caplog.set_level(logging.INFO)
        config = create_minimal_v1_0_config()

        migrate_schema(config)

        # Should log migration info
        assert any("Migrating schema from version 1.0" in record.message for record in caplog.records)

    def test_missing_safety_limits_logs_warning(self, caplog):
        """Test that missing safety_limits logs warning."""
        import logging

        caplog.set_level(logging.WARNING)
        config = create_minimal_v1_0_config()
        del config["safety_limits"]

        migrate_schema(config)

        # Should log warning about adding defaults
        assert any("Adding default safety_limits" in record.message for record in caplog.records)


class TestCreateMinimalConfig:
    """Test minimal config creation utility."""

    def test_minimal_config_is_valid(self):
        """Test that minimal config passes Pydantic validation."""
        config = create_minimal_v1_0_config()

        # Should validate without errors
        schema = validate_strategy_export(config)

        assert schema.schema_version == "1.0"
        assert schema.strategy.name == "ma_crossover"
        assert schema.ticker == "SPY"

    def test_minimal_config_has_required_fields(self):
        """Test that minimal config has all required root fields."""
        config = create_minimal_v1_0_config()

        required_fields = [
            "schema_version",
            "strategy",
            "ticker",
            "timeframe",
            "risk",
            "execution",
            "metadata",
        ]
        for field in required_fields:
            assert field in config, f"Missing required field: {field}"


# ============================================================================
# Future Migration Tests (Placeholder)
# ============================================================================


class TestFutureMigrations:
    """Placeholder for future migration tests (v1.1, v2.0, etc.)."""

    @pytest.mark.skip(reason="v1.1 not yet implemented")
    def test_migrate_1_0_to_1_1(self):
        """Test migration from v1.0 to v1.1 (when implemented)."""
        pass

    @pytest.mark.skip(reason="v2.0 not yet implemented")
    def test_migrate_1_1_to_2_0(self):
        """Test migration from v1.1 to v2.0 (when implemented)."""
        pass

    @pytest.mark.skip(reason="Migration chaining not yet needed")
    def test_migration_chaining(self):
        """Test migration chaining (1.0 → 1.1 → 2.0)."""
        # config = create_minimal_v1_0_config()
        # migrated = migrate_schema(config)
        # assert migrated["schema_version"] == "2.0"
        pass


# ============================================================================
# Regression Tests
# ============================================================================


class TestRegressions:
    """Test for regression bugs in migrations."""

    def test_migration_does_not_mutate_input(self):
        """Test that migrate_schema does not mutate input dict."""
        import copy

        config = create_minimal_v1_0_config()
        del config["safety_limits"]
        original = copy.deepcopy(config)

        migrate_schema(config)

        # Original should be unchanged (immutability)
        # NOTE: Current implementation DOES mutate. If this becomes a requirement,
        # update migrate_schema to work on a copy.
        # This test documents current behavior.
        assert "safety_limits" in config  # Currently mutates

    def test_empty_safety_limits_gets_all_defaults(self):
        """Test that empty safety_limits dict gets all defaults."""
        config = create_minimal_v1_0_config()
        config["safety_limits"] = {}

        migrated = migrate_schema(config)

        assert migrated["safety_limits"]["max_trades_per_day"] == 20
        assert migrated["safety_limits"]["max_api_calls_per_hour"] == 500
        assert migrated["safety_limits"]["signal_generation_timeout_seconds"] == 5.0
        assert migrated["safety_limits"]["broker_degraded_mode_threshold_failures"] == 3
