"""Portfolio optimization endpoint."""

from flask import Blueprint, current_app, jsonify, request

from ..validators import PortfolioConstraints, PortfolioOptimizeRequest
from ...backtest.portfolio_optimizer import PortfolioOptimizer, build_returns_matrix
from ...utils.config import load_config
from ...utils.logger import setup_logger

logger = setup_logger("alphalab.api.portfolio")

portfolio_bp = Blueprint("portfolio", __name__)


@portfolio_bp.route("/api/portfolio/optimize", methods=["POST"])
def optimize_portfolio():
    """Optimize portfolio weights across multiple strategies."""
    results_store = current_app.extensions["results_store"]
    body = PortfolioOptimizeRequest(**request.get_json(force=True))

    strategies = [s.model_dump() for s in body.strategies]
    constraints = body.constraints or PortfolioConstraints()
    max_weight = constraints.max_weight_per_strategy
    min_weight = constraints.min_weight_per_strategy
    target_return = constraints.target_return

    try:
        backtest_results = {}
        for strat in strategies:
            bt_id = strat["backtest_id"]
            if bt_id in results_store:
                backtest_results[bt_id] = results_store[bt_id].get(
                    "results", results_store[bt_id]
                )

        returns_matrix, labels = build_returns_matrix(strategies, backtest_results)

        config = load_config()
        optimizer = PortfolioOptimizer(returns_matrix, config.backtest.risk_free_rate)

        result = optimizer.optimize(
            method=body.method,
            max_weight=max_weight,
            min_weight=min_weight,
            target_return=target_return,
        )

        frontier = optimizer.efficient_frontier(
            n_points=20, max_weight=max_weight, min_weight=min_weight
        )

        result["strategy_labels"] = labels
        result["efficient_frontier"] = frontier

        return jsonify({"status": "ok", "data": result})

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.exception("Portfolio optimization failed")
        return jsonify({"status": "error", "message": str(e)}), 500
