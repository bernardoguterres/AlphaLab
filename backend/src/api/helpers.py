"""Shared helper functions for API route handlers."""

import json
from datetime import datetime, timezone

from flask import jsonify

from ..data.fetcher import DataFetchError
from ..data.validator import DataValidator
from ..data.processor import FeatureEngineer


def _fetch_and_prepare(fetcher, ticker: str, start_date, end_date, interval: str = "1d") -> tuple:
    """Fetch, validate, and feature-engineer data for a ticker.

    Returns (featured_df, report, None) on success or (None, None, flask_response_tuple) on failure.
    """
    try:
        raw = fetcher.fetch(ticker, start_date, end_date, interval)
    except DataFetchError as e:
        return None, None, (jsonify({"status": "error", "message": str(e)}), 400)

    validator = DataValidator()
    cleaned, report = validator.validate_and_clean(raw["data"], ticker)
    if not report.is_acceptable:
        return (
            None,
            None,
            (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Data quality too low ({report.confidence:.2f})",
                        "quality_report": report.to_dict(),
                    }
                ),
                422,
            ),
        )

    featured = FeatureEngineer().process(cleaned)
    featured.attrs["ticker"] = ticker
    return featured, report, None


_INTERVAL_TO_TIMEFRAME = {
    "1d": "1Day",
    "1wk": "1Week",
}


def _build_export_json(
    backtest_id: str,
    ticker: str,
    strategy_name: str,
    params: dict,
    start_date: str,
    end_date: str,
    initial_capital: float,
    results: dict,
    config,
    risk_settings: dict = None,
    interval: str = "1d",
) -> dict:
    """Build export JSON following the schema v1.0.

    Maps backtest results to the StrategyExportSchema format. `timeframe` is
    derived from the interval the backtest actually ran on, so the export
    never claims a timeframe the data didn't back up.
    """
    metrics = results.get("metrics", {})

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

    rs = risk_settings or {}
    risk = {
        "stop_loss_pct": rs.get("stop_loss_pct", 2.0),
        "take_profit_pct": rs.get("take_profit_pct", 5.0),
        "max_position_size_pct": rs.get("max_position_size_pct", 10.0),
        "max_daily_loss_pct": rs.get("max_daily_loss_pct", 3.0),
        "max_open_positions": rs.get("max_open_positions", 5),
        "portfolio_max_positions": 10,
        "trailing_stop_enabled": rs.get("trailing_stop_enabled", False),
        "trailing_stop_pct": rs.get("trailing_stop_pct", 3.0),
        "commission_per_trade": rs.get("commission_per_trade", 0.0),
    }

    execution = {
        "order_type": "market",
        "limit_offset_pct": 0.1,
        "cooldown_bars": params.get("cooldown_days", 1),
    }

    safety_limits = {
        "max_trades_per_day": 20,
        "max_api_calls_per_hour": 500,
        "signal_generation_timeout_seconds": 5.0,
        "broker_degraded_mode_threshold_failures": 3,
    }

    return {
        "schema_version": "1.0",
        "strategy": {
            "name": strategy_name,
            "parameters": params,
            "description": f"{strategy_name.replace('_', ' ').title()} strategy for {ticker}",
        },
        "ticker": ticker,
        "timeframe": _INTERVAL_TO_TIMEFRAME.get(interval, "1Day"),
        "risk": risk,
        "execution": execution,
        "safety_limits": safety_limits,
        "metadata": {
            "exported_from": "AlphaLab",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "alphalab_version": (
                config.app.version
                if hasattr(config, "app")
                else config.get("app", {}).get("version", "0.1.0")
            ),
            "backtest_id": backtest_id,
            "backtest_period": {
                "start": start_date,
                "end": end_date,
            },
            "performance": performance,
        },
    }
