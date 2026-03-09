"""Settings manager for non-sensitive application settings.

IMPORTANT: This module handles ONLY non-sensitive settings (alert toggles, thresholds).
API keys and secrets must NEVER be stored here — use environment variables only.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.settings")

# Settings file location (safe to commit — contains NO secrets)
SETTINGS_FILE = Path(__file__).parent.parent.parent / "configs" / "app_settings.json"


class SettingsManager:
    """Manage non-sensitive application settings.

    Settings are stored in configs/app_settings.json and contain only:
    - Alert toggles (enable/disable notifications)
    - Alert thresholds (drawdown %, etc.)
    - Paper trading toggle

    This file is safe to commit to git because it contains NO API keys.
    All credentials must be set as environment variables.
    """

    def __init__(self, settings_file: Path = SETTINGS_FILE):
        self.settings_file = settings_file
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file.

        Returns default settings if file doesn't exist.
        """
        if not self.settings_file.exists():
            logger.info("Settings file not found, using defaults")
            return self._default_settings()

        try:
            with open(self.settings_file, "r") as f:
                settings = json.load(f)
            logger.info("Loaded settings from %s", self.settings_file)

            # Add configured flags based on environment variables
            settings = self._add_configured_flags(settings)
            return settings
        except Exception as e:
            logger.error("Failed to load settings: %s", e)
            return self._default_settings()

    def save_settings(self, settings: Dict[str, Any]) -> None:
        """Save settings to file.

        IMPORTANT: This method validates that no API keys are being saved.
        """
        # Validate no secrets are being saved
        self._validate_no_secrets(settings)

        # Remove configured flags before saving (these are computed from env vars)
        settings_to_save = self._remove_configured_flags(settings)

        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings_to_save, indent=2, fp=f)
            logger.info("Saved settings to %s", self.settings_file)
        except Exception as e:
            logger.error("Failed to save settings: %s", e)
            raise

    def _default_settings(self) -> Dict[str, Any]:
        """Return default settings."""
        return {
            "telegram": {
                "enabled": False,
                "alert_trades": True,
                "alert_daily_summary": True,
                "alert_errors": True,
                "alert_drawdown": True,
                "alert_signals": False,
                "drawdown_threshold_pct": 5.0,
            },
            "alpaca": {
                "paper_trading": True,
            },
        }

    def _add_configured_flags(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Add flags indicating if API keys are configured in environment.

        These flags are computed from environment variables and are NOT saved to file.
        """
        settings_copy = settings.copy()

        # Check if Telegram bot token is configured
        if "telegram" not in settings_copy:
            settings_copy["telegram"] = {}

        # Check if Alpaca credentials are configured
        if "alpaca" not in settings_copy:
            settings_copy["alpaca"] = {}

        settings_copy["alpaca"]["api_key_configured"] = bool(
            os.environ.get("ALPACA_API_KEY")
        )
        settings_copy["alpaca"]["secret_key_configured"] = bool(
            os.environ.get("ALPACA_SECRET_KEY")
        )

        return settings_copy

    def _remove_configured_flags(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Remove configured flags before saving (they are computed from env vars)."""
        settings_copy = json.loads(json.dumps(settings))  # Deep copy

        if "alpaca" in settings_copy:
            settings_copy["alpaca"].pop("api_key_configured", None)
            settings_copy["alpaca"].pop("secret_key_configured", None)

        return settings_copy

    def _validate_no_secrets(self, settings: Dict[str, Any]) -> None:
        """Validate that no API keys or secrets are being saved.

        Raises ValueError if any forbidden fields are found.
        """
        forbidden_fields = {
            "api_key",
            "secret_key",
            "bot_token",
            "token",
            "password",
            "secret",
            "key",
        }

        def check_dict(d: dict, path: str = "") -> None:
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                # Check if key name is forbidden
                if any(forbidden in key.lower() for forbidden in forbidden_fields):
                    # Exception: "api_key_configured" is OK (it's a boolean flag)
                    if key.endswith("_configured"):
                        continue
                    raise ValueError(
                        f"Forbidden field '{current_path}': API keys must be set as "
                        f"environment variables, not saved to settings file"
                    )
                # Recursively check nested dicts
                if isinstance(value, dict):
                    check_dict(value, current_path)

        check_dict(settings)
