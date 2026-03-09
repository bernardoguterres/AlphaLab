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
        # Current version — apply backward compatibility enhancements
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
        # Partial safety_limits — fill in missing fields
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
# Example Future Migration (Commented Out)
# ============================================================================


def migrate_1_0_to_1_1(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate schema from v1.0 to v1.1 (EXAMPLE - not yet implemented).

    Example changes in v1.1 (hypothetical):
    - Add new optional field: "portfolio_currency" (default "USD")
    - Add new strategy: "mean_reversion_pairs"

    Args:
        config: v1.0 schema dictionary

    Returns:
        v1.1 schema dictionary
    """
    logger.info("Migrating schema from 1.0 to 1.1")

    # Add new optional fields with defaults
    if "portfolio_currency" not in config:
        config["portfolio_currency"] = "USD"

    # Update version
    config["schema_version"] = "1.1"

    return config


def migrate_1_1_to_2_0(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate schema from v1.1 to v2.0 (EXAMPLE - not yet implemented).

    Example breaking changes in v2.0 (hypothetical):
    - Rename field: "ticker" → "primary_symbol"
    - Change type: "timeframe" from string to object with multiplier
    - Add required field: "broker_id" (computed from metadata if missing)

    Args:
        config: v1.1 schema dictionary

    Returns:
        v2.0 schema dictionary

    Raises:
        ValueError: If migration cannot be completed (missing required data)
    """
    logger.info("Migrating schema from 1.1 to 2.0 (BREAKING CHANGES)")

    # Rename fields
    if "ticker" in config:
        config["primary_symbol"] = config.pop("ticker")
        logger.debug(f"Renamed 'ticker' → 'primary_symbol': {config['primary_symbol']}")

    # Change type (string → object)
    if isinstance(config.get("timeframe"), str):
        old_timeframe = config["timeframe"]
        # Parse "1Day" → {"period": "Day", "multiplier": 1}
        timeframe_map = {
            "1Day": {"period": "Day", "multiplier": 1},
            "1Hour": {"period": "Hour", "multiplier": 1},
            "15Min": {"period": "Minute", "multiplier": 15},
        }
        config["timeframe"] = timeframe_map.get(old_timeframe)
        if config["timeframe"] is None:
            raise ValueError(f"Cannot migrate unknown timeframe: {old_timeframe}")
        logger.debug(f"Migrated timeframe: {old_timeframe} → {config['timeframe']}")

    # Add required field (compute if missing)
    if "broker_id" not in config:
        # Default broker ID (would normally be required input)
        config["broker_id"] = "alpaca"
        logger.warning("Added default broker_id='alpaca' (v2.0 required field)")

    # Update version
    config["schema_version"] = "2.0"

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
                "short_window": 50,
                "long_window": 200,
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
