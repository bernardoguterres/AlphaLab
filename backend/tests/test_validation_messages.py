"""422 responses carry a readable message, not Pydantic's debug dump.

The frontend shows the message verbatim in its error toast; before this it
read "1 validation error for FetchDataRequest ... https://errors.pydantic.dev/...".
"""

import pytest

from alphalab.api.routes import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_invalid_ticker_message_is_clean(client):
    resp = client.post(
        "/api/data/fetch",
        json={
            "tickers": ["ZZZZZQ"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-01",
        },
    )
    assert resp.status_code == 422
    msg = resp.get_json()["message"]
    assert msg == "tickers: Invalid ticker: ZZZZZQ"


def test_missing_fields_are_listed_by_name(client):
    resp = client.post("/api/data/fetch", json={})
    assert resp.status_code == 422
    msg = resp.get_json()["message"]
    assert "validation error for" not in msg
    assert "pydantic.dev" not in msg
    assert "tickers: Field required" in msg


# B24: client errors keep their status code instead of becoming 500s.


def test_malformed_json_is_400_not_500(client):
    resp = client.post("/api/data/fetch", data="{bad", content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Request body must be a JSON object"


@pytest.mark.parametrize("body", ["[]", "null", '"text"', "3"])
def test_non_object_json_body_is_400(client, body):
    resp = client.post(
        "/api/strategies/backtest", data=body, content_type="application/json"
    )
    assert resp.status_code == 400


def test_wrong_method_is_405(client):
    resp = client.get("/api/data/fetch")
    assert resp.status_code == 405
    assert resp.get_json()["status"] == "error"


def test_screener_non_numeric_top_n_is_400(client):
    resp = client.post(
        "/api/screener/greenblatt", json={"tickers": ["AAPL"], "top_n": "abc"}
    )
    assert resp.status_code == 400
