"""Flask application factory — registers blueprints and middleware."""

import time
import uuid

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from .blueprints.backtest import backtest_bp
from .blueprints.data import data_bp
from .blueprints.portfolio import portfolio_bp
from .blueprints.screener import screener_bp
from .blueprints.settings_bp import settings_bp

# Re-exported for backward compatibility (tests import these from routes)
from .helpers import _build_export_json, _fetch_and_prepare  # noqa: F401
from ..data.fetcher import DataFetcher
from ..utils.config import load_config
from ..utils.logger import setup_logger

logger = setup_logger("alphalab.api")


def create_app() -> Flask:
    """Create and configure the Flask application."""
    config = load_config()

    app = Flask(__name__)
    CORS(app, origins=config.api.cors_origins)

    app.extensions["fetcher"] = DataFetcher()
    app.extensions["results_store"] = {}

    @app.before_request
    def _before():
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()

    @app.after_request
    def _after(response):
        elapsed = (time.time() - g.start_time) * 1000
        response.headers["X-Request-Id"] = g.request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed:.0f}"
        if elapsed > 2000:
            logger.warning(
                "[%s] Slow request: %s %s took %.0fms",
                g.request_id,
                request.method,
                request.path,
                elapsed,
            )
        return response

    @app.errorhandler(Exception)
    def _handle_error(e):
        if isinstance(e, ValidationError):
            return jsonify({"status": "error", "message": str(e)}), 422
        logger.exception("[%s] Unhandled error", getattr(g, "request_id", "?"))
        return jsonify({"status": "error", "message": "Internal server error"}), 500

    @app.errorhandler(404)
    def _not_found(e):
        return jsonify({"status": "error", "message": "Not found"}), 404

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": config.app.version})

    app.register_blueprint(data_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(screener_bp)

    return app
