"""Settings, credential-test, and notification endpoints."""

import os

import httpx
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from ..settings_validators import NotificationSettingsRequest
from ...utils.logger import setup_logger
from ...utils.settings_manager import SettingsManager

logger = setup_logger("alphalab.api.settings")

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/settings/notifications", methods=["GET"])
def get_notification_settings():
    """Get notification settings (non-sensitive only). Never returns API keys."""
    settings = SettingsManager().load_settings()
    return jsonify({"status": "ok", "data": settings})


@settings_bp.route("/api/settings/notifications", methods=["POST"])
def save_notification_settings():
    """Save notification settings. Rejects requests containing secrets."""
    try:
        body = NotificationSettingsRequest(**request.get_json(force=True))
    except ValidationError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    settings = {
        "telegram": body.telegram.model_dump(),
        "alpaca": body.alpaca.model_dump(),
    }

    try:
        SettingsManager().save_settings(settings)
        return jsonify({"status": "ok", "message": "Settings saved successfully"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to save settings")
        return jsonify({"status": "error", "message": str(e)}), 500


@settings_bp.route("/api/settings/telegram/test", methods=["POST"])
def test_telegram():
    """Test Telegram connection using TELEGRAM_BOT_TOKEN env var. Never accepts credentials in body."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return (
            jsonify({"status": "error", "message": "TELEGRAM_BOT_TOKEN environment variable not set"}),
            400,
        )

    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        return (
            jsonify({"status": "error", "message": "TELEGRAM_CHAT_ID environment variable not set"}),
            400,
        )

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = httpx.post(
            url,
            json={"chat_id": chat_id, "text": "🔔 AlphaLab notification test successful!"},
            timeout=10.0,
        )

        if response.status_code == 200:
            return jsonify({"status": "ok", "message": "Test message sent successfully"})
        return (
            jsonify({
                "status": "error",
                "message": f"Telegram API returned status {response.status_code}: {response.text}",
            }),
            400,
        )
    except Exception as e:
        logger.exception("Telegram test failed")
        return jsonify({"status": "error", "message": f"Failed to send test message: {str(e)}"}), 500


@settings_bp.route("/api/settings/alpaca/test", methods=["POST"])
def test_alpaca():
    """Test Alpaca connection using ALPACA_API_KEY and ALPACA_SECRET_KEY env vars."""
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        return (
            jsonify({
                "status": "error",
                "message": "ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set",
            }),
            400,
        )

    try:
        from alpaca.trading.client import TradingClient

        settings = SettingsManager().load_settings()
        paper = settings.get("alpaca", {}).get("paper_trading", True)
        client = TradingClient(api_key, secret_key, paper=paper)
        account = client.get_account()

        return jsonify({
            "status": "ok",
            "message": f"Connection successful (paper={paper})",
            "data": {
                "account_number": account.account_number,
                "status": account.status,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "paper_trading": paper,
            },
        })

    except ImportError:
        return (
            jsonify({
                "status": "error",
                "message": "alpaca-py library not installed. Run: pip install alpaca-py",
            }),
            500,
        )
    except Exception as e:
        logger.exception("Alpaca test failed")
        return jsonify({"status": "error", "message": f"Connection failed: {str(e)}"}), 400
