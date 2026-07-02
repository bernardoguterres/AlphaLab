"""Tests for the Greenblatt screener Flask blueprint."""

import json
from unittest.mock import patch, MagicMock

import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes import create_app
from src.screener.fundamental_screener import ScreenerResult


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _fake_result(ticker="AAPL", rank=1):
    return ScreenerResult(
        ticker=ticker,
        company_name=f"{ticker} Inc.",
        sector="Technology",
        earnings_yield=0.05,
        return_on_equity=0.25,
        pe_ratio=20.0,
        market_cap_b=500.0,
        debt_to_equity=0.5,
        earnings_yield_rank=rank,
        roe_rank=rank,
        combined_rank=rank * 2,
    )


class TestGreenblattScreenEndpoint:
    def test_missing_tickers_returns_400(self, client):
        resp = client.post(
            "/api/screener/greenblatt",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"

    def test_tickers_not_a_list_returns_400(self, client):
        resp = client.post(
            "/api/screener/greenblatt",
            data=json.dumps({"tickers": "AAPL"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_successful_screen_returns_ranked_candidates(self, client):
        fake_results = [_fake_result("AAPL", 1), _fake_result("MSFT", 2)]
        with patch(
            "src.api.blueprints.screener.FundamentalScreener"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.screen.return_value = fake_results
            mock_cls.return_value = mock_instance

            resp = client.post(
                "/api/screener/greenblatt",
                data=json.dumps({"tickers": ["AAPL", "MSFT"], "top_n": 5}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert body["data"]["total_screened"] == 2
        assert body["data"]["total_qualified"] == 2
        candidates = body["data"]["candidates"]
        assert candidates[0]["ticker"] == "AAPL"
        assert candidates[0]["earnings_yield_pct"] == 5.0
        assert candidates[0]["roe_pct"] == 25.0

        # Screener constructed with the request's filters.
        _, kwargs = mock_cls.call_args
        assert kwargs["universe"] == ["AAPL", "MSFT"]

    def test_custom_filters_passed_through(self, client):
        with patch(
            "src.api.blueprints.screener.FundamentalScreener"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.screen.return_value = []
            mock_cls.return_value = mock_instance

            resp = client.post(
                "/api/screener/greenblatt",
                data=json.dumps(
                    {
                        "tickers": ["AAPL"],
                        "min_market_cap_b": 5.0,
                        "max_debt_to_equity": 1.0,
                    }
                ),
                content_type="application/json",
            )

        assert resp.status_code == 200
        _, kwargs = mock_cls.call_args
        assert kwargs["min_market_cap_b"] == 5.0
        assert kwargs["max_debt_to_equity"] == 1.0

    def test_screener_exception_returns_500(self, client):
        with patch(
            "src.api.blueprints.screener.FundamentalScreener",
            side_effect=RuntimeError("yfinance down"),
        ):
            resp = client.post(
                "/api/screener/greenblatt",
                data=json.dumps({"tickers": ["AAPL"]}),
                content_type="application/json",
            )
        assert resp.status_code == 500
        assert "yfinance down" in resp.get_json()["message"]

    def test_empty_qualified_results(self, client):
        with patch(
            "src.api.blueprints.screener.FundamentalScreener"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.screen.return_value = []
            mock_cls.return_value = mock_instance

            resp = client.post(
                "/api/screener/greenblatt",
                data=json.dumps({"tickers": ["ZZZZ"]}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["candidates"] == []
        assert body["data"]["total_qualified"] == 0
