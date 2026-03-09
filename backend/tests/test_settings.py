"""Tests for settings management."""

import json
import os
import tempfile
from pathlib import Path
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.settings_manager import SettingsManager
from src.api.settings_validators import (
    NotificationSettingsRequest,
    TelegramSettings,
    AlpacaSettings,
)
from pydantic import ValidationError


class TestSettingsManager:
    """Tests for SettingsManager class."""

    def test_save_and_load_settings(self, tmp_path):
        """Test saving and loading settings from file."""
        settings_file = tmp_path / "app_settings.json"
        mgr = SettingsManager(settings_file)

        # Save settings
        settings = {
            "telegram": {
                "enabled": True,
                "alert_trades": True,
                "alert_daily_summary": False,
                "alert_errors": True,
                "alert_drawdown": True,
                "alert_signals": False,
                "drawdown_threshold_pct": 10.0,
            },
            "alpaca": {
                "paper_trading": False,
            },
        }

        mgr.save_settings(settings)

        # Verify file exists
        assert settings_file.exists()

        # Load settings
        loaded = mgr.load_settings()

        # Configured flags are added when loading
        assert "api_key_configured" in loaded["alpaca"]
        assert "secret_key_configured" in loaded["alpaca"]

        # Remove configured flags for comparison
        loaded["alpaca"].pop("api_key_configured")
        loaded["alpaca"].pop("secret_key_configured")

        assert loaded == settings

    def test_default_settings(self, tmp_path):
        """Test that default settings are returned when file doesn't exist."""
        settings_file = tmp_path / "nonexistent.json"
        mgr = SettingsManager(settings_file)

        settings = mgr.load_settings()

        # Should have default structure
        assert "telegram" in settings
        assert "alpaca" in settings
        assert settings["telegram"]["enabled"] is False
        assert settings["alpaca"]["paper_trading"] is True

    def test_reject_api_keys_in_settings(self, tmp_path):
        """Test that API keys are rejected when saving settings."""
        settings_file = tmp_path / "app_settings.json"
        mgr = SettingsManager(settings_file)

        # Try to save settings with API key
        settings_with_key = {
            "telegram": {
                "enabled": True,
                "bot_token": "12345:ABCDEF",  # FORBIDDEN
            },
            "alpaca": {
                "paper_trading": True,
            },
        }

        with pytest.raises(ValueError, match="API keys must be set as environment variables"):
            mgr.save_settings(settings_with_key)

        # Try with secret_key
        settings_with_secret = {
            "telegram": {"enabled": True},
            "alpaca": {
                "paper_trading": True,
                "secret_key": "my_secret",  # FORBIDDEN
            },
        }

        with pytest.raises(ValueError, match="API keys must be set as environment variables"):
            mgr.save_settings(settings_with_secret)

    def test_configured_flags_not_saved(self, tmp_path):
        """Test that configured flags are not saved to file."""
        settings_file = tmp_path / "app_settings.json"
        mgr = SettingsManager(settings_file)

        # Save settings (without configured flags)
        settings = {
            "telegram": {"enabled": True},
            "alpaca": {"paper_trading": True},
        }

        mgr.save_settings(settings)

        # Read file directly
        with open(settings_file, "r") as f:
            saved_data = json.load(f)

        # Configured flags should NOT be in the file
        assert "api_key_configured" not in saved_data.get("alpaca", {})
        assert "secret_key_configured" not in saved_data.get("alpaca", {})

    def test_api_key_configured_flags(self, tmp_path, monkeypatch):
        """Test that configured flags reflect environment variables."""
        settings_file = tmp_path / "app_settings.json"
        mgr = SettingsManager(settings_file)

        # Save minimal settings
        settings = {
            "telegram": {"enabled": True},
            "alpaca": {"paper_trading": True},
        }
        mgr.save_settings(settings)

        # Load without env vars
        loaded = mgr.load_settings()
        assert loaded["alpaca"]["api_key_configured"] is False
        assert loaded["alpaca"]["secret_key_configured"] is False

        # Set env vars
        monkeypatch.setenv("ALPACA_API_KEY", "test_key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")

        # Load again
        loaded = mgr.load_settings()
        assert loaded["alpaca"]["api_key_configured"] is True
        assert loaded["alpaca"]["secret_key_configured"] is True


class TestSettingsValidators:
    """Tests for settings Pydantic validators."""

    def test_valid_notification_request(self):
        """Test valid notification settings request."""
        data = {
            "telegram": {
                "enabled": True,
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

        request = NotificationSettingsRequest(**data)
        assert request.telegram.enabled is True
        assert request.alpaca.paper_trading is True

    def test_reject_api_key_in_request(self):
        """Test that API keys in request body are rejected."""
        data_with_key = {
            "telegram": {
                "enabled": True,
                "bot_token": "12345:ABCDEF",  # FORBIDDEN
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

        with pytest.raises(ValidationError, match="API keys must be set as environment variables"):
            NotificationSettingsRequest(**data_with_key)

    def test_reject_secret_key_in_request(self):
        """Test that secret keys in request body are rejected."""
        data_with_secret = {
            "telegram": {
                "enabled": True,
                "alert_trades": True,
                "alert_daily_summary": True,
                "alert_errors": True,
                "alert_drawdown": True,
                "alert_signals": False,
                "drawdown_threshold_pct": 5.0,
            },
            "alpaca": {
                "paper_trading": True,
                "api_key": "test_key",  # FORBIDDEN
                "secret_key": "test_secret",  # FORBIDDEN
            },
        }

        with pytest.raises(ValidationError, match="API keys must be set as environment variables"):
            NotificationSettingsRequest(**data_with_secret)

    def test_drawdown_threshold_validation(self):
        """Test drawdown threshold validation."""
        # Too low
        with pytest.raises(ValidationError, match="Drawdown threshold must be between"):
            TelegramSettings(
                enabled=True,
                alert_trades=True,
                alert_daily_summary=True,
                alert_errors=True,
                alert_drawdown=True,
                alert_signals=False,
                drawdown_threshold_pct=0.05,  # Too low
            )

        # Too high
        with pytest.raises(ValidationError, match="Drawdown threshold must be between"):
            TelegramSettings(
                enabled=True,
                alert_trades=True,
                alert_daily_summary=True,
                alert_errors=True,
                alert_drawdown=True,
                alert_signals=False,
                drawdown_threshold_pct=60.0,  # Too high
            )

        # Valid
        settings = TelegramSettings(
            enabled=True,
            alert_trades=True,
            alert_daily_summary=True,
            alert_errors=True,
            alert_drawdown=True,
            alert_signals=False,
            drawdown_threshold_pct=10.0,
        )
        assert settings.drawdown_threshold_pct == 10.0

    def test_api_key_configured_is_allowed(self):
        """Test that *_configured flags are allowed (they're boolean flags, not secrets)."""
        # This should be valid because api_key_configured is a flag, not a credential
        data = {
            "telegram": {
                "enabled": True,
                "alert_trades": True,
                "alert_daily_summary": True,
                "alert_errors": True,
                "alert_drawdown": True,
                "alert_signals": False,
                "drawdown_threshold_pct": 5.0,
            },
            "alpaca": {
                "paper_trading": True,
                "api_key_configured": True,  # OK - it's a boolean flag
                "secret_key_configured": True,  # OK - it's a boolean flag
            },
        }

        request = NotificationSettingsRequest(**data)
        assert request.alpaca.api_key_configured is True
