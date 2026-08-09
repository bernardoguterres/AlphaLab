"""Schema Migration Infrastructure for Strategy Export Schemas.

Handles version upgrades for strategy configuration JSON files.
Ensures backward compatibility when schema evolves.

Version History:
- 1.0 (2026-03-08): Initial release with safety_limits block
"""

from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


def migrate_schema(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate strategy config to latest schema version.

    Applies migrations in sequence: 1.0 → 1.1 → 2.0 → ...

    Args:
        config: Strategy export schema dictionary (from JSON)

    Returns:
        Migrated config dictionary at latest version

    Raises:
        ValueError: If schema_version is unknown or unsupported
    """
    version = config.get("schema_version", "1.0")
    logger.info(f"Migrating schema from version {version}")

    if version == "1.0":
        # Current version - apply backward compatibility enhancements
        config = _apply_v1_0_defaults(config)
        return config

    # Future migrations would go here (chained recursively):
    # elif version == "1.1":
    #     config = migrate_1_1_to_2_0(config)
    #     return migrate_schema(config)  # Recursive for chaining
    # elif version == "2.0":
    #     # Already at latest
    #     return config

    else:
        raise ValueError(
            f"Unknown or unsupported schema version: {version}. "
            f"Please upgrade AlphaLab to support this schema version."
        )


def _apply_v1_0_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default values for v1.0 schema fields.

    Ensures backward compatibility for configs exported before safety_limits
    block was added (even though it was in v1.0 from the start, this handles
    any JSON files missing the block).

    Args:
        config: v1.0 schema dictionary

    Returns:
        v1.0 schema with defaults applied
    """
    if "safety_limits" not in config:
        logger.warning(
            "Adding default safety_limits to v1.0 schema (backward compatibility)"
        )
        config["safety_limits"] = {
            "max_trades_per_day": 20,
            "max_api_calls_per_hour": 500,
            "signal_generation_timeout_seconds": 5.0,
            "broker_degraded_mode_threshold_failures": 3,
        }
    else:
        # Partial safety_limits - fill in missing fields
        defaults = {
            "max_trades_per_day": 20,
            "max_api_calls_per_hour": 500,
            "signal_generation_timeout_seconds": 5.0,
            "broker_degraded_mode_threshold_failures": 3,
        }
        for key, value in defaults.items():
            if key not in config["safety_limits"]:
                logger.debug(f"Adding missing safety_limits.{key} = {value}")
                config["safety_limits"][key] = value

    return config


# ============================================================================
# Validation Helpers
# ============================================================================


def get_supported_versions() -> list[str]:
    """Get list of schema versions supported by this migration module.

    Returns:
        List of version strings (e.g., ["1.0", "1.1", "2.0"])
    """
    return ["1.0"]


def is_version_supported(version: str) -> bool:
    """Check if a schema version is supported.

    Args:
        version: Schema version string

    Returns:
        True if version can be migrated to latest, False otherwise
    """
    return version in get_supported_versions()


def get_latest_version() -> str:
    """Get the latest supported schema version.

    Returns:
        Latest version string (e.g., "1.0")
    """
    return "1.0"


# ============================================================================
# Testing Utilities
# ============================================================================


def create_minimal_v1_0_config() -> Dict[str, Any]:
    """Create minimal valid v1.0 config for testing.

    Returns:
        Minimal v1.0 schema dictionary (includes safety_limits for backward compat testing)
    """
    return {
        "schema_version": "1.0",
        "strategy": {
            "name": "ma_crossover",
            "parameters": {
                "strategy_type": "ma_crossover",
                "fast_period": 50,
                "slow_period": 200,
                "volume_confirmation": True,
                "cooldown_days": 5,
            },
        },
        "ticker": "SPY",
        "timeframe": "1Day",
        "risk": {
            "stop_loss_pct": 3.0,
            "take_profit_pct": 10.0,
            "max_position_size_pct": 25.0,
            "max_daily_loss_pct": 5.0,
            "max_open_positions": 1,
            "portfolio_max_positions": 5,
            "trailing_stop_enabled": False,
            "trailing_stop_pct": 0.0,
            "commission_per_trade": 0.0,
        },
        "execution": {
            "order_type": "market",
            "limit_offset_pct": 0.0,
            "cooldown_bars": 5,
        },
        "safety_limits": {
            "max_trades_per_day": 20,
            "max_api_calls_per_hour": 500,
            "signal_generation_timeout_seconds": 5.0,
            "broker_degraded_mode_threshold_failures": 3,
        },
        "metadata": {
            "exported_from": "AlphaLab",
            "exported_at": "2026-03-08T14:30:00Z",
            "alphalab_version": "0.2.0",
            "backtest_id": "bt_test_123",
            "backtest_period": {"start": "2020-01-01", "end": "2024-12-31"},
            "performance": {
                "sharpe_ratio": 1.23,
                "sortino_ratio": 1.65,
                "total_return_pct": 28.4,
                "max_drawdown_pct": -11.2,
                "win_rate_pct": 54.5,
                "profit_factor": 1.52,
                "total_trades": 22,
                "calmar_ratio": 2.54,
            },
        },
    }
