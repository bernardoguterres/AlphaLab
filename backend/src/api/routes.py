"""Flask REST API with request validation, error handling, and middleware."""

import time
import uuid
from functools import wraps

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from pydantic import ValidationError

from .validators import (
    FetchDataRequest,
    BacktestRequest,
    OptimizeRequest,
    CompareRequest,
)
from ..data.fetcher import DataFetcher, DataFetchError
from ..data.validator import DataValidator
from ..data.processor import FeatureEngineer
from ..strategies.implementations import (
    MovingAverageCrossover,
    RSIMeanReversion,
    MomentumBreakout,
)
from ..backtest.engine import BacktestEngine
from ..backtest.metrics import PerformanceMetrics
from ..utils.logger import setup_logger
from ..utils.config import load_config

logger = setup_logger("alphalab.api")

STRATEGY_MAP = {
    "ma_crossover": MovingAverageCrossover,
    "rsi_mean_reversion": RSIMeanReversion,
    "momentum_breakout": MomentumBreakout,
}

# In-memory store for backtest results (swap for DB in production)
_results_store: dict[str, dict] = {}


def create_app() -> Flask:
    """Create and configure the Flask application."""
    config = load_config()
    api_cfg = config.get("api", {})

    app = Flask(__name__)
    CORS(app, origins=config.get("api", {}).get("cors_origins", ["*"]))

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

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
                g.request_id, request.method, request.path, elapsed,
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

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": config["app"]["version"]})

    # ------------------------------------------------------------------
    # Data endpoints
    # ------------------------------------------------------------------

    @app.route("/api/data/fetch", methods=["POST"])
    def fetch_data():
        body = FetchDataRequest(**request.get_json(force=True))
        fetcher = DataFetcher()
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

        return jsonify({
            "status": "ok",
            "data": results,
            "errors": errors,
        })

    @app.route("/api/data/available")
    def available_data():
        fetcher = DataFetcher()
        cached = fetcher.cache.list_cached()
        return jsonify({"status": "ok", "data": cached})

    # ------------------------------------------------------------------
    # Strategy / backtest endpoints
    # ------------------------------------------------------------------

    @app.route("/api/strategies/backtest", methods=["POST"])
    def run_backtest():
        body = BacktestRequest(**request.get_json(force=True))

        # Fetch and process data
        fetcher = DataFetcher()
        try:
            raw = fetcher.fetch(body.ticker, body.start_date, body.end_date)
        except DataFetchError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        validator = DataValidator()
        cleaned, report = validator.validate_and_clean(raw["data"], body.ticker)
        if not report.is_acceptable:
            return jsonify({
                "status": "error",
                "message": f"Data quality too low ({report.confidence:.2f})",
                "quality_report": report.to_dict(),
            }), 422

        processor = FeatureEngineer()
        featured = processor.process(cleaned)
        featured.attrs["ticker"] = body.ticker

        # Build strategy
        strategy_cls = STRATEGY_MAP.get(body.strategy)
        if not strategy_cls:
            return jsonify({"status": "error", "message": f"Unknown strategy: {body.strategy}"}), 400

        strategy = strategy_cls(body.params or {})

        # Run backtest
        engine = BacktestEngine()
        results = engine.run_backtest(
            strategy=strategy,
            data=featured,
            initial_capital=body.initial_capital,
            start_date=body.start_date,
            end_date=body.end_date,
            position_sizing=body.position_sizing,
            monte_carlo_runs=body.monte_carlo_runs,
        )

        # Calculate metrics
        metrics_calc = PerformanceMetrics()
        metrics = metrics_calc.calculate_all(results.equity_curve, results.trades)
        results.metrics = metrics

        # Store for later retrieval
        result_id = str(uuid.uuid4())[:8]
        _results_store[result_id] = results.to_dict()

        response = results.to_dict()
        response["backtest_id"] = result_id
        return jsonify({"status": "ok", "data": response})

    @app.route("/api/strategies/optimize", methods=["POST"])
    def optimize_strategy():
        body = OptimizeRequest(**request.get_json(force=True))

        fetcher = DataFetcher()
        try:
            raw = fetcher.fetch(body.ticker, body.start_date, body.end_date)
        except DataFetchError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        processor = FeatureEngineer()
        validator = DataValidator()
        cleaned, _ = validator.validate_and_clean(raw["data"])
        featured = processor.process(cleaned)

        strategy_cls = STRATEGY_MAP.get(body.strategy)
        if not strategy_cls:
            return jsonify({"status": "error", "message": "Unknown strategy"}), 400

        strategy = strategy_cls()
        opt = strategy.optimize_params(featured, body.param_grid)
        return jsonify({"status": "ok", "data": opt})

    @app.route("/api/metrics/<backtest_id>")
    def get_metrics(backtest_id):
        result = _results_store.get(backtest_id)
        if not result:
            return jsonify({"status": "error", "message": "Backtest not found"}), 404
        return jsonify({"status": "ok", "data": result})

    @app.route("/api/compare", methods=["POST"])
    def compare_strategies():
        body = CompareRequest(**request.get_json(force=True))

        fetcher = DataFetcher()
        try:
            raw = fetcher.fetch(body.ticker, body.start_date, body.end_date)
        except DataFetchError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        processor = FeatureEngineer()
        validator = DataValidator()
        cleaned, _ = validator.validate_and_clean(raw["data"])
        featured = processor.process(cleaned)
        featured.attrs["ticker"] = body.ticker

        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()
        comparison = {}

        for strat_name in body.strategies:
            cls = STRATEGY_MAP.get(strat_name)
            if not cls:
                comparison[strat_name] = {"error": f"Unknown strategy: {strat_name}"}
                continue

            strategy = cls()
            results = engine.run_backtest(
                strategy=strategy,
                data=featured,
                initial_capital=body.initial_capital,
                start_date=body.start_date,
                end_date=body.end_date,
            )
            metrics = metrics_calc.calculate_all(results.equity_curve, results.trades)
            comparison[strat_name] = {
                "total_return_pct": results.total_return_pct,
                "metrics": metrics,
            }

        return jsonify({"status": "ok", "data": comparison})

    return app
