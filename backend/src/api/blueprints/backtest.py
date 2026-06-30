"""Strategy backtest, optimize, compare, and export endpoints."""

import json
import os
import sys
import time
import uuid
from datetime import datetime

import numpy as np
from flask import Blueprint, Response, current_app, jsonify, request
from pydantic import ValidationError

from ..helpers import _build_export_json, _fetch_and_prepare
from ..validators import (
    BacktestRequest,
    BatchBacktestRequest,
    CompareRequest,
    ExportStrategyRequest,
    HeatmapRequest,
    OptimizeRequest,
)
from ...backtest.engine import BacktestEngine
from ...backtest.metrics import PerformanceMetrics
from ...backtest.parameter_optimizer import ParameterOptimizer
from ...data.fetcher import DataFetchError
from ...strategies.implementations import (
    BollingerBreakout,
    BollingerRSICombo,
    GreenblattWeekly,
    MomentumBreakout,
    MovingAverageCrossover,
    RSIMeanReversion,
    TrendAdaptiveRSI,
    VWAPReversion,
)
from ...utils.config import load_config
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.api.backtest")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
try:
    from strategy_schema import StrategyExportSchema
except ImportError:
    StrategyExportSchema = None

STRATEGY_MAP = {
    "ma_crossover": MovingAverageCrossover,
    "rsi_mean_reversion": RSIMeanReversion,
    "momentum_breakout": MomentumBreakout,
    "bollinger_breakout": BollingerBreakout,
    "vwap_reversion": VWAPReversion,
    "bollinger_rsi_combo": BollingerRSICombo,
    "trend_adaptive_rsi": TrendAdaptiveRSI,
    "greenblatt_weekly": GreenblattWeekly,
}

backtest_bp = Blueprint("backtest", __name__)


@backtest_bp.route("/api/strategies/backtest", methods=["POST"])
def run_backtest():
    fetcher = current_app.extensions["fetcher"]
    results_store = current_app.extensions["results_store"]
    body = BacktestRequest(**request.get_json(force=True))

    featured, report, err = _fetch_and_prepare(
        fetcher, body.ticker, body.start_date, body.end_date
    )
    if err:
        return err

    strategy_cls = STRATEGY_MAP.get(body.strategy)
    if not strategy_cls:
        return (
            jsonify(
                {"status": "error", "message": f"Unknown strategy: {body.strategy}"}
            ),
            400,
        )

    strategy = strategy_cls(body.params or {})

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

    metrics_calc = PerformanceMetrics()
    metrics = metrics_calc.calculate_all(results.equity_curve, results.trades)
    results.metrics = metrics

    result_id = str(uuid.uuid4())[:8]
    results_store[result_id] = {
        "results": results.to_dict(),
        "request": {
            "ticker": body.ticker,
            "strategy": body.strategy,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "initial_capital": body.initial_capital,
            "params": body.params or {},
            "risk_settings": (
                body.risk_settings.model_dump() if body.risk_settings else None
            ),
        },
    }

    response = results.to_dict()
    response["backtest_id"] = result_id
    response["data_quality_warnings"] = report.warnings
    return jsonify({"status": "ok", "data": response})


@backtest_bp.route("/api/strategies/optimize", methods=["POST"])
def optimize_strategy():
    """Optimize strategy parameters with optional walk-forward validation."""
    fetcher = current_app.extensions["fetcher"]
    body = OptimizeRequest(**request.get_json(force=True))

    featured, report, err = _fetch_and_prepare(
        fetcher, body.ticker, body.start_date, body.end_date
    )
    if err:
        return err

    strategy_cls = STRATEGY_MAP.get(body.strategy)
    if not strategy_cls:
        return jsonify({"status": "error", "message": "Unknown strategy"}), 400

    param_optimizer = ParameterOptimizer()
    engine = BacktestEngine()
    metrics_calc = PerformanceMetrics()

    try:
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


@backtest_bp.route("/api/strategies/optimize/heatmap", methods=["POST"])
def parameter_heatmap():
    """Generate 2D parameter heatmap for visualization."""
    fetcher = current_app.extensions["fetcher"]
    body = HeatmapRequest(**request.get_json(force=True))

    featured, report, err = _fetch_and_prepare(
        fetcher, body.ticker, body.start_date, body.end_date
    )
    if err:
        return err

    strategy_cls = STRATEGY_MAP.get(body.strategy)
    if not strategy_cls:
        return jsonify({"status": "error", "message": "Unknown strategy"}), 400

    param1_values = list(
        np.arange(body.param1_min, body.param1_max + body.param1_step, body.param1_step)
    )
    param2_values = list(
        np.arange(body.param2_min, body.param2_max + body.param2_step, body.param2_step)
    )

    if len(param1_values) * len(param2_values) > 400:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Heatmap grid too large (max 400 cells). Use larger step sizes.",
                }
            ),
            400,
        )

    param_optimizer = ParameterOptimizer()
    engine = BacktestEngine()
    metrics_calc = PerformanceMetrics()

    try:
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


@backtest_bp.route("/api/metrics/<backtest_id>")
def get_metrics(backtest_id):
    results_store = current_app.extensions["results_store"]
    stored = results_store.get(backtest_id)
    if not stored:
        return jsonify({"status": "error", "message": "Backtest not found"}), 404
    return jsonify({"status": "ok", "data": stored.get("results", stored)})


@backtest_bp.route("/api/compare", methods=["POST"])
def compare_strategies():
    fetcher = current_app.extensions["fetcher"]
    body = CompareRequest(**request.get_json(force=True))

    featured, report, err = _fetch_and_prepare(
        fetcher, body.ticker, body.start_date, body.end_date
    )
    if err:
        return err

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


@backtest_bp.route("/api/strategies/batch-backtest", methods=["POST"])
def batch_backtest():
    """Run backtests across multiple tickers with the same strategy."""
    fetcher = current_app.extensions["fetcher"]
    body = BatchBacktestRequest(**request.get_json(force=True))

    start_time = time.time()
    from ...data.validator import DataValidator
    from ...data.processor import FeatureEngineer

    validator = DataValidator()
    processor = FeatureEngineer()
    engine = BacktestEngine()
    metrics_calc = PerformanceMetrics()

    strategy_cls = STRATEGY_MAP.get(body.strategy)
    if not strategy_cls:
        return (
            jsonify(
                {"status": "error", "message": f"Unknown strategy: {body.strategy}"}
            ),
            400,
        )

    results = []
    errors = []

    for ticker in body.tickers:
        try:
            raw = fetcher.fetch(ticker, body.start_date, body.end_date)

            if not raw.get("metadata", {}).get("from_cache", False):
                time.sleep(0.5)

            cleaned, report = validator.validate_and_clean(raw["data"], ticker)
            if not report.is_acceptable:
                errors.append(
                    {
                        "ticker": ticker,
                        "error": f"Data quality too low ({report.confidence:.2f})",
                    }
                )
                continue

            featured = processor.process(cleaned)
            featured.attrs["ticker"] = ticker

            strategy = strategy_cls(body.params or {})
            backtest_result = engine.run_backtest(
                strategy=strategy,
                data=featured,
                initial_capital=body.initial_capital,
                start_date=body.start_date,
                end_date=body.end_date,
                position_sizing=body.position_sizing,
                monte_carlo_runs=0,
            )
            metrics = metrics_calc.calculate_all(
                backtest_result.equity_curve, backtest_result.trades
            )

            results.append(
                {
                    "ticker": ticker,
                    "total_return_pct": backtest_result.total_return_pct,
                    "sharpe_ratio": metrics["risk"]["sharpe_ratio"],
                    "max_drawdown_pct": metrics["drawdown"]["max_drawdown_pct"],
                    "win_rate": metrics["trades"]["win_rate"],
                    "total_trades": len(backtest_result.trades),
                    "final_value": backtest_result.final_value,
                    "metrics": metrics,
                }
            )

        except DataFetchError as e:
            errors.append({"ticker": ticker, "error": str(e)})
        except Exception as e:
            logger.exception("Batch backtest failed for %s", ticker)
            errors.append({"ticker": ticker, "error": str(e)})

    results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

    total_runtime = time.time() - start_time
    num_profitable = sum(1 for r in results if r["total_return_pct"] > 0)
    avg_sharpe = (
        sum(r["sharpe_ratio"] for r in results) / len(results) if results else 0
    )
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
        "worst_sharpe": (
            round(worst_ticker["sharpe_ratio"], 2) if worst_ticker else None
        ),
        "runtime_seconds": round(total_runtime, 1),
    }

    return jsonify(
        {
            "status": "ok",
            "data": {
                "results": results,
                "batch_summary": batch_summary,
                "errors": errors,
            },
        }
    )


@backtest_bp.route("/api/strategies/export", methods=["POST"])
def export_strategy():
    """Export a strategy config for AlphaLive."""
    results_store = current_app.extensions["results_store"]
    body = ExportStrategyRequest(**request.get_json(force=True))

    stored = results_store.get(body.backtest_id)
    if not stored:
        return (
            jsonify(
                {"status": "error", "message": f"Backtest {body.backtest_id} not found"}
            ),
            404,
        )

    results = stored["results"]
    req = stored["request"]

    try:
        config = load_config()
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

        if StrategyExportSchema:
            try:
                validated = StrategyExportSchema.model_validate(export_json)
                export_json = validated.model_dump(mode="json", exclude_none=True)
            except ValidationError as e:
                logger.error("Export validation failed: %s", e)
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"Export validation failed: {str(e)}",
                        }
                    ),
                    422,
                )

        json_str = json.dumps(export_json, indent=2)
        filename = f"{req['strategy']}_{req['ticker']}_{datetime.now().strftime('%Y%m%d')}.json"

        response = Response(
            json_str,
            mimetype="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Backtest-Id": body.backtest_id,
            },
        )

        logger.info(
            "Exported strategy %s for %s (backtest %s)",
            req["strategy"],
            req["ticker"],
            body.backtest_id,
        )
        return response

    except Exception as e:
        logger.exception("Export failed for backtest %s", body.backtest_id)
        return jsonify({"status": "error", "message": str(e)}), 500
