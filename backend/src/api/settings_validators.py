"""Pydantic validators for settings API endpoints."""

from typing import Optional, Any
from pydantic import BaseModel, field_validator, model_validator


class TelegramSettings(BaseModel):
    """Telegram notification settings (non-sensitive only)."""
    enabled: bool = False
    alert_trades: bool = True
    alert_daily_summary: bool = True
    alert_errors: bool = True
    alert_drawdown: bool = True
    alert_signals: bool = False
    drawdown_threshold_pct: float = 5.0

    @field_validator("drawdown_threshold_pct")
    @classmethod
    def validate_threshold(cls, v):
        if not 0.1 <= v <= 50.0:
            raise ValueError("Drawdown threshold must be between 0.1% and 50%")
        return v

    @model_validator(mode='before')
    @classmethod
    def reject_credentials(cls, data: Any) -> Any:
        """Reject any credential-like fields."""
        if isinstance(data, dict):
            forbidden_keys = {"bot_token", "token", "api_key", "secret_key", "password", "secret"}
            found = forbidden_keys & set(k.lower() for k in data.keys())
            if found:
                raise ValueError(
                    f"API keys must be set as environment variables, not saved via this endpoint. "
                    f"Found forbidden fields: {', '.join(found)}"
                )
        return data


class AlpacaSettings(BaseModel):
    """Alpaca settings (non-sensitive only)."""
    paper_trading: bool = True
    api_key_configured: Optional[bool] = None
    secret_key_configured: Optional[bool] = None

    @model_validator(mode='before')
    @classmethod
    def reject_credentials(cls, data: Any) -> Any:
        """Reject any credential-like fields (except *_configured flags)."""
        if isinstance(data, dict):
            forbidden_keys = {"api_key", "secret_key", "password", "secret", "token"}
            # Filter out *_configured fields (they're OK)
            actual_keys = {k.lower() for k in data.keys() if not k.endswith("_configured")}
            found = forbidden_keys & actual_keys
            if found:
                raise ValueError(
                    f"API keys must be set as environment variables, not saved via this endpoint. "
                    f"Found forbidden fields: {', '.join(found)}"
                )
        return data


class NotificationSettingsRequest(BaseModel):
    """Request to update notification settings.

    IMPORTANT: This must NOT accept api_key or secret_key fields.
    All credentials must be set as environment variables.
    Validation is done at the TelegramSettings and AlpacaSettings level.
    """
    telegram: TelegramSettings
    alpaca: AlpacaSettings


class NotificationSettingsResponse(BaseModel):
    """Response for notification settings (non-sensitive only)."""
    telegram: TelegramSettings
    alpaca: AlpacaSettings
