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
