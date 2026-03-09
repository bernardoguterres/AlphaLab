"""Flask REST API with request validation, error handling, and middleware."""

import time
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, request, g, Response
from flask_cors import CORS
from pydantic import ValidationError

from .validators import (
    FetchDataRequest,
    BacktestRequest,
    OptimizeRequest,
    HeatmapRequest,
    CompareRequest,
    ExportStrategyRequest,
    BatchBacktestRequest,
    PortfolioOptimizeRequest,
    PortfolioConstraints,
)
from .settings_validators import (
    NotificationSettingsRequest,
    NotificationSettingsResponse,
)
from ..data.fetcher import DataFetcher, DataFetchError
from ..data.validator import DataValidator
from ..data.processor import FeatureEngineer
from ..strategies.implementations import (
    MovingAverageCrossover,
    RSIMeanReversion,
    MomentumBreakout,
    BollingerBreakout,
    VWAPReversion,
)
from ..backtest.engine import BacktestEngine
from ..backtest.metrics import PerformanceMetrics
from ..backtest.portfolio_optimizer import PortfolioOptimizer, build_returns_matrix
from ..backtest.parameter_optimizer import ParameterOptimizer
from ..utils.logger import setup_logger
from ..utils.config import load_config
from ..utils.settings_manager import SettingsManager

# Import strategy export schema for validation
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from strategy_schema import StrategyExportSchema, export_strategy_to_json
except ImportError:
    logger.warning("Could not import StrategyExportSchema - export validation disabled")
    StrategyExportSchema = None
    export_strategy_to_json = None

logger = setup_logger("alphalab.api")

STRATEGY_MAP = {
    "ma_crossover": MovingAverageCrossover,
    "rsi_mean_reversion": RSIMeanReversion,
    "momentum_breakout": MomentumBreakout,
    "bollinger_breakout": BollingerBreakout,
    "vwap_reversion": VWAPReversion,
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

        # Store for later retrieval (including request params for export)
        result_id = str(uuid.uuid4())[:8]
        _results_store[result_id] = {
            "results": results.to_dict(),
            "request": {
                "ticker": body.ticker,
                "strategy": body.strategy,
                "start_date": body.start_date,
                "end_date": body.end_date,
                "initial_capital": body.initial_capital,
                "params": body.params or {},
                "risk_settings": body.risk_settings.model_dump() if body.risk_settings else None,
            }
        }

        response = results.to_dict()
        response["backtest_id"] = result_id
        response["data_quality_warnings"] = report.warnings  # Add quality warnings
        return jsonify({"status": "ok", "data": response})

    @app.route("/api/strategies/optimize", methods=["POST"])
    def optimize_strategy():
        """Optimize strategy parameters with optional walk-forward validation.

        Returns best parameters and performance metrics. Supports walk-forward
        to prevent overfitting.
        """
        body = OptimizeRequest(**request.get_json(force=True))

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
            }), 422

        processor = FeatureEngineer()
        featured = processor.process(cleaned)
        featured.attrs["ticker"] = body.ticker

        # Get strategy class
        strategy_cls = STRATEGY_MAP.get(body.strategy)
        if not strategy_cls:
            return jsonify({"status": "error", "message": "Unknown strategy"}), 400

        # Initialize optimizer
        param_optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        try:
            # Run parameter optimization
            result = param_optimizer.grid_search(
                strategy_class=strategy_cls,
                data=featured,
                param_grid=body.param_grid,
                initial_capital=body.initial_capital,
                engine=engine,
                metrics_calc=metrics_calc,
                optimization_target=body.optimization_target,
                walk_forward=body.walk_forward,
                n_folds=body.n_folds,
            )

            return jsonify({"status": "ok", "data": result})

        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.exception("Parameter optimization failed")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/strategies/optimize/heatmap", methods=["POST"])
    def parameter_heatmap():
        """Generate 2D parameter heatmap for visualization.

        Returns a grid of performance metrics (Sharpe ratio) for two varying parameters.
        """
        body = HeatmapRequest(**request.get_json(force=True))

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
            }), 422

        processor = FeatureEngineer()
        featured = processor.process(cleaned)
        featured.attrs["ticker"] = body.ticker

        # Get strategy class
        strategy_cls = STRATEGY_MAP.get(body.strategy)
        if not strategy_cls:
            return jsonify({"status": "error", "message": "Unknown strategy"}), 400

        # Generate parameter value ranges
        import numpy as np
        param1_values = list(np.arange(body.param1_min, body.param1_max + body.param1_step, body.param1_step))
        param2_values = list(np.arange(body.param2_min, body.param2_max + body.param2_step, body.param2_step))

        # Limit grid size to prevent excessive computation
        if len(param1_values) * len(param2_values) > 400:
            return jsonify({
                "status": "error",
                "message": "Heatmap grid too large (max 400 cells). Use larger step sizes."
            }), 400

        # Initialize optimizer
        param_optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        try:
            # Generate heatmap
            result = param_optimizer.generate_heatmap(
                strategy_class=strategy_cls,
                data=featured,
                param1_name=body.param1_name,
                param1_values=param1_values,
                param2_name=body.param2_name,
                param2_values=param2_values,
                fixed_params=body.fixed_params or {},
                initial_capital=body.initial_capital,
                engine=engine,
                metrics_calc=metrics_calc,
            )

            return jsonify({"status": "ok", "data": result})

        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.exception("Heatmap generation failed")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/metrics/<backtest_id>")
    def get_metrics(backtest_id):
        stored = _results_store.get(backtest_id)
        if not stored:
            return jsonify({"status": "error", "message": "Backtest not found"}), 404
        # Return the results part (for backward compatibility)
        return jsonify({"status": "ok", "data": stored.get("results", stored)})

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

    @app.route("/api/strategies/batch-backtest", methods=["POST"])
    def batch_backtest():
        """Run backtests across multiple tickers with the same strategy.

        Returns results sorted by Sharpe ratio with batch summary statistics.
        """
        body = BatchBacktestRequest(**request.get_json(force=True))

        start_time = time.time()
        fetcher = DataFetcher()
        validator = DataValidator()
        processor = FeatureEngineer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()

        # Get strategy class
        strategy_cls = STRATEGY_MAP.get(body.strategy)
        if not strategy_cls:
            return jsonify({"status": "error", "message": f"Unknown strategy: {body.strategy}"}), 400

        results = []
        errors = []

        for ticker in body.tickers:
            try:
                # Fetch data (uses cache if available)
                raw = fetcher.fetch(ticker, body.start_date, body.end_date)

                # If not cached, add small delay to avoid rate limits
                if not raw.get("from_cache", False):
                    time.sleep(0.5)

                # Validate and clean
                cleaned, report = validator.validate_and_clean(raw["data"], ticker)
                if not report.is_acceptable:
                    errors.append({
                        "ticker": ticker,
                        "error": f"Data quality too low ({report.confidence:.2f})"
                    })
                    continue

                # Process features
                featured = processor.process(cleaned)
                featured.attrs["ticker"] = ticker

                # Build strategy
                strategy = strategy_cls(body.params or {})

                # Run backtest
                backtest_result = engine.run_backtest(
                    strategy=strategy,
                    data=featured,
                    initial_capital=body.initial_capital,
                    start_date=body.start_date,
                    end_date=body.end_date,
                    position_sizing=body.position_sizing,
                    monte_carlo_runs=0,  # Skip Monte Carlo for batch
                )

                # Calculate metrics
                metrics = metrics_calc.calculate_all(backtest_result.equity_curve, backtest_result.trades)

                results.append({
                    "ticker": ticker,
                    "total_return_pct": backtest_result.total_return_pct,
                    "sharpe_ratio": metrics["risk"]["sharpe_ratio"],
                    "max_drawdown_pct": metrics["drawdown"]["max_drawdown_pct"],
                    "win_rate": metrics["trades"]["win_rate"],
                    "total_trades": len(backtest_result.trades),
                    "final_value": backtest_result.final_value,
                    "metrics": metrics,
                })

            except DataFetchError as e:
                errors.append({"ticker": ticker, "error": str(e)})
            except Exception as e:
                logger.exception(f"Batch backtest failed for {ticker}")
                errors.append({"ticker": ticker, "error": str(e)})

        # Sort by Sharpe ratio descending
        results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

        # Calculate batch summary
        total_runtime = time.time() - start_time
        num_profitable = sum(1 for r in results if r["total_return_pct"] > 0)
        avg_sharpe = sum(r["sharpe_ratio"] for r in results) / len(results) if results else 0

        best_ticker = results[0] if results else None
        worst_ticker = results[-1] if results else None

        batch_summary = {
            "total_tickers": len(body.tickers),
            "successful": len(results),
            "failed": len(errors),
            "profitable_count": num_profitable,
            "profitable_pct": (num_profitable / len(results) * 100) if results else 0,
            "avg_sharpe_ratio": round(avg_sharpe, 2),
            "best_ticker": best_ticker["ticker"] if best_ticker else None,
            "best_sharpe": round(best_ticker["sharpe_ratio"], 2) if best_ticker else None,
            "worst_ticker": worst_ticker["ticker"] if worst_ticker else None,
            "worst_sharpe": round(worst_ticker["sharpe_ratio"], 2) if worst_ticker else None,
            "runtime_seconds": round(total_runtime, 1),
        }

        return jsonify({
            "status": "ok",
            "data": {
                "results": results,
                "batch_summary": batch_summary,
                "errors": errors,
            }
        })

    @app.route("/api/portfolio/optimize", methods=["POST"])
    def optimize_portfolio():
        """Optimize portfolio weights across multiple strategies.

        Uses Modern Portfolio Theory to allocate capital across strategies.
        """
        body = PortfolioOptimizeRequest(**request.get_json(force=True))

        # Extract strategies list
        strategies = [s.model_dump() for s in body.strategies]

        # Get constraints
        constraints = body.constraints or PortfolioConstraints()
        max_weight = constraints.max_weight_per_strategy
        min_weight = constraints.min_weight_per_strategy
        target_return = constraints.target_return

        try:
            # Extract results from store (strip wrapper)
            backtest_results = {}
            for strat in strategies:
                bt_id = strat['backtest_id']
                if bt_id in _results_store:
                    backtest_results[bt_id] = _results_store[bt_id].get('results', _results_store[bt_id])

            # Build returns matrix from stored backtests
            returns_matrix, labels = build_returns_matrix(strategies, backtest_results)

            # Initialize optimizer
            config = load_config()
            risk_free_rate = config.get("backtest", {}).get("risk_free_rate", 0.04)
            optimizer = PortfolioOptimizer(returns_matrix, risk_free_rate)

            # Optimize
            result = optimizer.optimize(
                method=body.method,
                max_weight=max_weight,
                min_weight=min_weight,
                target_return=target_return,
            )

            # Calculate efficient frontier
            frontier = optimizer.efficient_frontier(
                n_points=20,
                max_weight=max_weight,
                min_weight=min_weight,
            )

            # Add strategy labels to result
            result["strategy_labels"] = labels
            result["efficient_frontier"] = frontier

            return jsonify({"status": "ok", "data": result})

        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.exception("Portfolio optimization failed")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/strategies/export", methods=["POST"])
    def export_strategy():
        """Export a strategy config for AlphaLive.

        Builds a JSON export following the schema in docs/STRATEGY_SCHEMA.md.
        Returns a downloadable JSON file.
        """
        body = ExportStrategyRequest(**request.get_json(force=True))

        # Look up stored backtest
        stored = _results_store.get(body.backtest_id)
        if not stored:
            return jsonify({"status": "error", "message": f"Backtest {body.backtest_id} not found"}), 404

        results = stored["results"]
        req = stored["request"]

        # Build export JSON following schema v1.0
        try:
            export_json = _build_export_json(
                backtest_id=body.backtest_id,
                ticker=req["ticker"],
                strategy_name=req["strategy"],
                params=req["params"],
                start_date=req["start_date"],
                end_date=req["end_date"],
                initial_capital=req["initial_capital"],
                results=results,
                config=config,
                risk_settings=req.get("risk_settings"),
            )

            # Validate against schema (if available)
            if StrategyExportSchema:
                try:
                    validated = StrategyExportSchema.model_validate(export_json)
                    export_json = validated.model_dump(mode="json", exclude_none=True)
                except ValidationError as e:
                    logger.error(f"Export validation failed: {e}")
                    return jsonify({
                        "status": "error",
                        "message": f"Export validation failed: {str(e)}"
                    }), 422

            # Convert to JSON string
            import json
            json_str = json.dumps(export_json, indent=2)

            # Return as downloadable file
            filename = f"{req['strategy']}_{req['ticker']}_{datetime.now().strftime('%Y%m%d')}.json"

            response = Response(
                json_str,
                mimetype="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Backtest-Id": body.backtest_id,
                }
            )

            logger.info(f"Exported strategy {req['strategy']} for {req['ticker']} (backtest {body.backtest_id})")
            return response

        except Exception as e:
            logger.exception(f"Export failed for backtest {body.backtest_id}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # ------------------------------------------------------------------
    # Settings endpoints
    # ------------------------------------------------------------------

    @app.route("/api/settings/notifications", methods=["GET"])
    def get_notification_settings():
        """Get notification settings (non-sensitive only).

        Returns current settings with API key configured flags.
        NEVER returns actual API keys.
        """
        settings_mgr = SettingsManager()
        settings = settings_mgr.load_settings()

        return jsonify({
            "status": "ok",
            "data": settings,
        })

    @app.route("/api/settings/notifications", methods=["POST"])
    def save_notification_settings():
        """Save notification settings (non-sensitive only).

        Rejects requests that include API keys or secrets.
        All credentials must be set as environment variables.
        """
        try:
            body = NotificationSettingsRequest(**request.get_json(force=True))
        except ValidationError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        settings_mgr = SettingsManager()

        # Convert Pydantic model to dict
        settings = {
            "telegram": body.telegram.model_dump(),
            "alpaca": body.alpaca.model_dump(),
        }

        try:
            settings_mgr.save_settings(settings)
            return jsonify({
                "status": "ok",
                "message": "Settings saved successfully",
            })
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.exception("Failed to save settings")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/settings/telegram/test", methods=["POST"])
    def test_telegram():
        """Test Telegram connection.

        Reads bot token from TELEGRAM_BOT_TOKEN environment variable.
        NEVER accepts credentials via request body.
        """
        import os
        import httpx

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            return jsonify({
                "status": "error",
                "message": "TELEGRAM_BOT_TOKEN environment variable not set",
            }), 400

        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not chat_id:
            return jsonify({
                "status": "error",
                "message": "TELEGRAM_CHAT_ID environment variable not set",
            }), 400

        try:
            # Send test message using httpx (no library)
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            response = httpx.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": "🔔 AlphaLab notification test successful!",
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                return jsonify({
                    "status": "ok",
                    "message": "Test message sent successfully",
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Telegram API returned status {response.status_code}: {response.text}",
                }), 400

        except Exception as e:
            logger.exception("Telegram test failed")
            return jsonify({
                "status": "error",
                "message": f"Failed to send test message: {str(e)}",
            }), 500

    @app.route("/api/settings/alpaca/test", methods=["POST"])
    def test_alpaca():
        """Test Alpaca connection.

        Reads credentials from ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.
        NEVER accepts credentials via request body.
        """
        import os

        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            return jsonify({
                "status": "error",
                "message": "ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set",
            }), 400

        try:
            # Test connection using alpaca-py
            from alpaca.trading.client import TradingClient

            # Get paper trading setting
            settings_mgr = SettingsManager()
            settings = settings_mgr.load_settings()
            paper = settings.get("alpaca", {}).get("paper_trading", True)

            # Create client
            client = TradingClient(api_key, secret_key, paper=paper)

            # Test by getting account info
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
            return jsonify({
                "status": "error",
                "message": "alpaca-py library not installed. Run: pip install alpaca-py",
            }), 500
        except Exception as e:
            logger.exception("Alpaca test failed")
            return jsonify({
                "status": "error",
                "message": f"Connection failed: {str(e)}",
            }), 400

    return app


def _build_export_json(
    backtest_id: str,
    ticker: str,
    strategy_name: str,
    params: dict,
    start_date: str,
    end_date: str,
    initial_capital: float,
    results: dict,
    config: dict,
    risk_settings: dict = None,
) -> dict:
    """Build export JSON following the schema v1.0.

    Maps backtest results to the StrategyExportSchema format.
    """
    # Map strategy name format
    strategy_name_map = {
        "ma_crossover": "ma_crossover",
        "rsi_mean_reversion": "rsi_mean_reversion",
        "momentum_breakout": "momentum_breakout",
    }

    # Extract metrics
    metrics = results.get("metrics", {})

    # Build performance block
    performance = {
        "sharpe_ratio": round(metrics.get("risk", {}).get("sharpe_ratio", 0.0), 2),
        "sortino_ratio": round(metrics.get("risk", {}).get("sortino_ratio", 0.0), 2),
        "total_return_pct": round(results.get("total_return_pct", 0.0), 2),
        "max_drawdown_pct": round(metrics.get("drawdown", {}).get("max_drawdown", 0.0), 2),
        "win_rate_pct": round(metrics.get("trades", {}).get("win_rate", 0.0) * 100, 2),
        "profit_factor": round(metrics.get("trades", {}).get("profit_factor", 0.0), 2),
        "total_trades": results.get("total_trades", 0),
        "calmar_ratio": round(metrics.get("risk", {}).get("calmar_ratio", 0.0), 2),
    }

    # Use provided risk settings or defaults
    if risk_settings:
        risk = {
            "stop_loss_pct": risk_settings.get("stop_loss_pct", 2.0),
            "take_profit_pct": risk_settings.get("take_profit_pct", 5.0),
            "max_position_size_pct": risk_settings.get("max_position_size_pct", 10.0),
            "max_daily_loss_pct": risk_settings.get("max_daily_loss_pct", 3.0),
            "max_open_positions": risk_settings.get("max_open_positions", 5),
            "portfolio_max_positions": 10,  # Not configurable in UI yet
            "trailing_stop_enabled": risk_settings.get("trailing_stop_enabled", False),
            "trailing_stop_pct": risk_settings.get("trailing_stop_pct", 3.0),
            "commission_per_trade": risk_settings.get("commission_per_trade", 0.0),
        }
    else:
        # Default risk parameters
        risk = {
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "max_position_size_pct": 10.0,
            "max_daily_loss_pct": 3.0,
            "max_open_positions": 5,
            "portfolio_max_positions": 10,
            "trailing_stop_enabled": False,
            "trailing_stop_pct": 3.0,
            "commission_per_trade": 0.0,
        }

    # Default execution parameters
    execution = {
        "order_type": "market",
        "limit_offset_pct": 0.1,
        "cooldown_bars": params.get("cooldown_days", 1),
    }

    # Default safety limits
    safety_limits = {
        "max_trades_per_day": 20,
        "max_api_calls_per_hour": 500,
        "signal_generation_timeout_seconds": 5.0,
        "broker_degraded_mode_threshold_failures": 3,
    }

    # Build export
    export = {
        "schema_version": "1.0",
        "strategy": {
            "name": strategy_name_map.get(strategy_name, strategy_name),
            "parameters": params,
            "description": f"{strategy_name.replace('_', ' ').title()} strategy for {ticker}",
        },
        "ticker": ticker,
        "timeframe": "1Day",  # Default to daily (could be enhanced to detect from data)
        "risk": risk,
        "execution": execution,
        "safety_limits": safety_limits,
        "metadata": {
            "exported_from": "AlphaLab",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "alphalab_version": config.get("app", {}).get("version", "0.1.0"),
            "backtest_id": backtest_id,
            "backtest_period": {
                "start": start_date,
                "end": end_date,
            },
            "performance": performance,
        }
    }

    return export
