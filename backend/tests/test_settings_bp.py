"""Tests for the settings_bp Flask blueprint (notifications + credential tests)."""

import json
from unittest.mock import patch, MagicMock

import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with SettingsManager pointed at a throwaway file."""
    app = create_app()
    app.config["TESTING"] = True

    # Point every SettingsManager() call at an isolated tmp file so tests
    # don't clobber the real backend/configs/app_settings.json.
    settings_file = tmp_path / "app_settings.json"
    with patch(
        "src.api.blueprints.settings_bp.SettingsManager"
    ) as mock_mgr_cls:
        from src.utils.settings_manager import SettingsManager as RealMgr

        real = RealMgr(settings_file)
        mock_mgr_cls.side_effect = lambda *a, **k: real
        with app.test_client() as c:
            yield c


class TestNotificationSettingsGet:
    def test_get_returns_defaults(self, client):
        resp = client.get("/api/settings/notifications")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert "telegram" in body["data"]
        assert "alpaca" in body["data"]


class TestNotificationSettingsPost:
    def test_save_valid_settings(self, client):
        payload = {
            "telegram": {
                "enabled": True,
                "alert_trades": True,
                "alert_daily_summary": True,
                "alert_errors": True,
                "alert_drawdown": True,
                "alert_signals": False,
                "drawdown_threshold_pct": 10.0,
            },
            "alpaca": {"paper_trading": True},
        }
        resp = client.post(
            "/api/settings/notifications",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

        # Confirm it round-trips via GET.
        get_resp = client.get("/api/settings/notifications")
        assert get_resp.get_json()["data"]["telegram"]["enabled"] is True

    def test_save_rejects_api_key_in_body(self, client):
        payload = {
            "telegram": {"enabled": True, "bot_token": "123:ABC"},
            "alpaca": {"paper_trading": True},
        }
        resp = client.post(
            "/api/settings/notifications",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"

    def test_save_rejects_malformed_body(self, client):
        # Missing required nested fields for telegram/alpaca models entirely
        # is fine (they have defaults) but wrong types should 400.
        resp = client.post(
            "/api/settings/notifications",
            data=json.dumps({"telegram": "not-a-dict", "alpaca": {}}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"


class TestTelegramTestEndpoint:
    def test_missing_bot_token_returns_400(self, client, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        resp = client.post("/api/settings/telegram/test")
        assert resp.status_code == 400
        assert "TELEGRAM_BOT_TOKEN" in resp.get_json()["message"]

    def test_missing_chat_id_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        resp = client.post("/api/settings/telegram/test")
        assert resp.status_code == 400
        assert "TELEGRAM_CHAT_ID" in resp.get_json()["message"]

    def test_successful_send(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        mock_response = MagicMock(status_code=200)
        with patch("httpx.post", return_value=mock_response) as mock_post:
            resp = client.post("/api/settings/telegram/test")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        assert mock_post.called

    def test_telegram_api_error_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        mock_response = MagicMock(status_code=401, text="Unauthorized")
        with patch("httpx.post", return_value=mock_response):
            resp = client.post("/api/settings/telegram/test")
        assert resp.status_code == 400
        assert "401" in resp.get_json()["message"]

    def test_telegram_request_exception_returns_500(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        with patch("httpx.post", side_effect=RuntimeError("network down")):
            resp = client.post("/api/settings/telegram/test")
        assert resp.status_code == 500
        assert "network down" in resp.get_json()["message"]


class TestAlpacaTestEndpoint:
    def test_missing_credentials_returns_400(self, client, monkeypatch):
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        resp = client.post("/api/settings/alpaca/test")
        assert resp.status_code == 400
        assert "ALPACA_API_KEY" in resp.get_json()["message"]

    def test_successful_connection(self, client, monkeypatch):
        monkeypatch.setenv("ALPACA_API_KEY", "key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")

        mock_account = MagicMock(
            account_number="ABC123",
            status="ACTIVE",
            buying_power="1000.0",
            cash="500.0",
        )
        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_account

        with patch(
            "alpaca.trading.client.TradingClient", return_value=mock_client
        ):
            resp = client.post("/api/settings/alpaca/test")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert body["data"]["account_number"] == "ABC123"
        assert body["data"]["buying_power"] == 1000.0

    def test_connection_failure_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("ALPACA_API_KEY", "key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")

        with patch(
            "alpaca.trading.client.TradingClient",
            side_effect=RuntimeError("bad credentials"),
        ):
            resp = client.post("/api/settings/alpaca/test")
        assert resp.status_code == 400
        assert "bad credentials" in resp.get_json()["message"]
