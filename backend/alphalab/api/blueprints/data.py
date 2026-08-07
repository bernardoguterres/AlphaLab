"""Data fetch and cache endpoints."""

from flask import Blueprint, jsonify, request, current_app

from ...data.fetcher import DataFetchError
from ..validators import FetchDataRequest
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.api.data")

data_bp = Blueprint("data", __name__)


@data_bp.route("/api/data/fetch", methods=["POST"])
def fetch_data():
    fetcher = current_app.extensions["fetcher"]
    body = FetchDataRequest(**request.get_json(force=True))
    results = {}
    errors = []

    for ticker in body.tickers:
        try:
            res = fetcher.fetch(ticker, body.start_date, body.end_date, body.interval)
            results[ticker] = {
                "records": res["metadata"]["records"],
                "quality_score": res["metadata"]["quality_score"],
                "start_date": res["metadata"]["start_date"],
                "end_date": res["metadata"]["end_date"],
            }
        except DataFetchError as e:
            errors.append({"ticker": ticker, "error": str(e)})

    return jsonify({"status": "ok", "data": results, "errors": errors})


@data_bp.route("/api/data/available")
def available_data():
    fetcher = current_app.extensions["fetcher"]
    cached = fetcher.cache.list_cached()
    return jsonify({"status": "ok", "data": cached})
