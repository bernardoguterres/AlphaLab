"""Shared helper functions for API route handlers."""

from datetime import datetime, timezone

from flask import jsonify, request
from werkzeug.exceptions import BadRequest

from ..data.fetcher import DataFetchError
from ..data.validator import DataValidator
from ..data.processor import FeatureEngineer


def json_body(allow_empty: bool = False) -> dict:
    """The request's JSON object, or a 400 if the body is not one.

    ``request.get_json(force=True)`` raised BadRequest on malformed JSON (which
    the catch-all handler turned into a 500), and a valid non-object body
    (``[]``, ``null``) crashed the ``Model(**body)`` call with a TypeError.
    """
    body = request.get_json(force=True, silent=True)
    if body is None and allow_empty and not request.get_data():
        return {}
    if not isinstance(body, dict):
        raise BadRequest("Request body must be a JSON object")
    return body


def _fetch_and_prepare(
    fetcher, ticker: str, start_date, end_date, interval: str = "1d"
) -> tuple:
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

    report.warnings.extend(
        _coverage_warnings(cleaned.index, start_date, end_date, interval)
    )
    featured = FeatureEngineer().process(cleaned)
    featured.attrs["ticker"] = ticker
    featured.attrs["interval"] = interval
    return featured, report, None


# Calendar-day slack before a gap at either end is reported: covers weekends,
# holidays and the bar size itself.
_COVERAGE_SLACK_DAYS = {"1d": 7, "1wk": 14, "1mo": 45}


def _coverage_warnings(index, start_date, end_date, interval: str = "1d") -> list:
    """Warn when the data starts after / ends before the requested window.

    A run silently covering a shorter period than asked for looked like a
    normal result (a corrupted cache entry ending 14 months early went
    unnoticed). Requested dates in the future are not counted as gaps.
    """
    if len(index) == 0 or not start_date or not end_date:
        return []
    import pandas as pd

    slack = pd.Timedelta(days=_COVERAGE_SLACK_DAYS.get(interval, 7))
    idx = pd.DatetimeIndex(index)
    first = idx.min().tz_localize(None) if idx.tz is not None else idx.min()
    last = idx.max().tz_localize(None) if idx.tz is not None else idx.max()
    start = pd.Timestamp(start_date)
    end = min(pd.Timestamp(end_date), pd.Timestamp(datetime.now(timezone.utc).date()))
    out = []
    if first - start > slack:
        out.append(
            f"Data starts {first.date()}, {(first - start).days} days after the "
            f"requested start {start.date()}"
        )
    if end - last > slack:
        out.append(
            f"Data ends {last.date()}, {(end - last).days} days before the "
            f"requested end {end.date()}"
        )
    return out


_INTERVAL_TO_TIMEFRAME = {
    "1d": "1Day",
    "1wk": "1Week",
}


def _export_timeframe(interval: str) -> str:
    """AlphaLive timeframe for a backtest interval. Raises for an interval
    AlphaLive cannot trade (e.g. 1mo) instead of defaulting to 1Day."""
    try:
        return _INTERVAL_TO_TIMEFRAME[interval]
    except KeyError:
        raise ValueError(
            f"Interval {interval!r} has no AlphaLive timeframe "
            f"(supported: {', '.join(sorted(_INTERVAL_TO_TIMEFRAME))})"
        ) from None


def _translate_params_for_export(strategy_name: str, params: dict) -> dict:
    """Translate AlphaLab's internal strategy parameter names to the
    AlphaLive export-contract names, and inject the strategy_type
    discriminator StrategyExportSchema now requires.

    AlphaLab's internal strategy classes (alphalab/strategies/implementations/)
    keep their own field names unchanged - only the exported JSON's field
    names change here, at the export-mapping layer.
    """
    out = dict(params)

    if strategy_name == "ma_crossover":
        if "short_window" in out:
            out["fast_period"] = out.pop("short_window")
        if "long_window" in out:
            out["slow_period"] = out.pop("long_window")
    elif strategy_name == "momentum_breakout":
        if "volume_surge_pct" in out:
            out["surge_pct"] = out.pop("volume_surge_pct") / 100.0
        if "volume_avg_period" in out:
            out["volume_ma_period"] = out.pop("volume_avg_period")
    elif strategy_name == "bollinger_breakout":
        if "bb_period" in out:
            out["period"] = out.pop("bb_period")
        if "bb_std_dev" in out:
            out["std_dev"] = out.pop("bb_std_dev")
    elif strategy_name == "greenblatt_weekly":
        if "trailing_stop_pct" in out:
            out["trailing_stop_fraction"] = out.pop("trailing_stop_pct")

    out["strategy_type"] = strategy_name
    return out


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
        "max_drawdown_pct": round(
            metrics.get("drawdown", {}).get("max_drawdown_pct", 0.0), 2
        ),
        "win_rate_pct": round(metrics.get("trades", {}).get("win_rate", 0.0) * 100, 2),
        "profit_factor": round(metrics.get("trades", {}).get("profit_factor", 0.0), 2),
        # completed round trips (AlphaLab metrics definition)
        "total_trades": metrics.get("trades", {}).get(
            "round_trips", results.get("total_trades", 0)
        ),
        "calmar_ratio": round(metrics.get("risk", {}).get("calmar_ratio", 0.0), 2),
    }

    rs = risk_settings or {}
    max_open = rs.get("max_open_positions", 5)
    portfolio_max = rs.get("portfolio_max_positions", 10)
    risk = {
        "stop_loss_pct": rs.get("stop_loss_pct", 2.0),
        "take_profit_pct": rs.get("take_profit_pct", 5.0),
        "max_position_size_pct": rs.get("max_position_size_pct", 10.0),
        "max_daily_loss_pct": rs.get("max_daily_loss_pct", 3.0),
        "max_open_positions": max_open,
        "portfolio_max_positions": max(portfolio_max, max_open),
        "trailing_stop_enabled": rs.get("trailing_stop_enabled", False),
        "trailing_stop_pct": rs.get("trailing_stop_pct", 3.0),
        "commission_per_trade": rs.get("commission_per_trade", 0.0),
        # Only halt-free backtests are exportable (see export_strategy);
        # stated explicitly so AlphaLive can tell these from older exports.
        "drawdown_halt_enabled": False,
    }

    execution = {
        "order_type": "market",
        "limit_offset_pct": 0.1,
        "cooldown_bars": params.get("cooldown_days", 1),
        "bear_market_filter": params.get("bear_market_filter", None),
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
            "parameters": _translate_params_for_export(strategy_name, params),
            "description": f"{strategy_name.replace('_', ' ').title()} strategy for {ticker}",
        },
        "ticker": ticker,
        "timeframe": _export_timeframe(interval),
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
