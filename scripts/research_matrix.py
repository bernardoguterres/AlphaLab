"""Run an offline AlphaLab research and regression matrix on aligned OHLCV parquet files.

From the repository root:
backend/venv/bin/python scripts/research_matrix.py DATA_DIR REPORT.json
"""

import argparse
from collections import defaultdict
from datetime import date
from email.utils import parsedate_to_datetime
import json
import logging
from math import isclose, isfinite
from pathlib import Path
from statistics import median
import subprocess
from tempfile import NamedTemporaryFile
import sys
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from alphalab.api.blueprints.backtest import STRATEGY_MAP
from alphalab.api.helpers import _fetch_and_prepare
from alphalab.api.routes import create_app
from alphalab.api.validators import BacktestRequest
from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.metrics import PerformanceMetrics
from alphalab.data.fetcher import DataFetchError
from alphalab.strategies.research import DonchianBreakout, TrendPullback

SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "AAPL", "GLD")
WINDOWS = {
    "2007-2009": ("2007-07-01", "2009-12-31"),
    "2010-2014": ("2010-01-01", "2014-12-31"),
    "2015-2016": ("2015-01-01", "2016-12-31"),
    "2017-2019": ("2017-01-01", "2019-12-31"),
    "2020-2022": ("2020-01-01", "2022-12-31"),
    "2023-2025": ("2023-01-01", "2025-12-31"),
}
PROFILES = {
    "default": {},
    "trailing_with_fees": {
        "risk_settings": {
            "max_position_size_pct": 35,
            "stop_loss_pct": 6,
            "take_profit_pct": 25,
            "trailing_stop_enabled": True,
            "trailing_stop_pct": 5,
            "commission_per_trade": 2,
        },
        "max_drawdown_pct": 15,
    },
    "volatility_with_fees": {
        "position_sizing": "volatility_weighted",
        "risk_settings": {
            "max_position_size_pct": 50,
            "stop_loss_pct": 10,
            "take_profit_pct": 50,
            "commission_per_trade": 5,
        },
        "drawdown_halt_enabled": False,
    },
}
OHLCV = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum",
}


EXPERIMENTAL = {"donchian_55_20": DonchianBreakout, "trend_pullback": TrendPullback}


class ParquetFetcher:
    def __init__(self, directory):
        fields = {
            field: pd.read_parquet(directory / f"{field.lower()}.parquet")
            for field in OHLCV
        }
        self.daily = {
            symbol: (
                pd.DataFrame({field: table[symbol] for field, table in fields.items()})
                .sort_index()
                .dropna()
            )
            for symbol in SYMBOLS
        }

    def fetch(self, ticker, start_date, end_date, interval):
        daily = self.daily.get(ticker)
        if daily is None:
            raise DataFetchError(f"No local bars for {ticker}")
        daily = daily.loc[str(start_date) : str(end_date)]
        if interval == "1wk":
            # Use only completed week labels inside the requested window.
            daily = daily.resample("W-FRI").agg(OHLCV).dropna().loc[: str(end_date)]
        if daily.empty:
            raise DataFetchError(f"No local bars for {ticker}")
        return {"data": daily.copy(), "metadata": {"from_cache": True}}


def run_experiment(app, fetcher, payload, strategy_class):
    # Reuse request validation and the normal data path. Research prototypes are
    # deliberately kept out of the public strategy registry and export pipeline.
    validated = BacktestRequest(**dict(payload, strategy="ma_crossover"))
    with app.app_context():
        data, report, error = _fetch_and_prepare(
            fetcher, validated.ticker, validated.start_date, validated.end_date, "1d"
        )
        if error:
            raise ValueError(error[0].get_json()["message"])
    result = BacktestEngine().run_backtest(
        strategy_class(),
        data,
        initial_capital=validated.initial_capital,
        start_date=validated.start_date,
        end_date=validated.end_date,
        **validated.engine_options(),
    )
    if result.failure_reason:
        raise ValueError(result.failure_reason)
    result.metrics = PerformanceMetrics().calculate_all(
        result.equity_curve, result.trades, result.benchmark["equity_curve"]
    )
    return dict(result.to_dict(), data_quality_warnings=report.warnings)


def check_result(result):
    equity = result["equity_curve"]
    timestamps = pd.to_datetime(
        [
            (
                parsedate_to_datetime(point["date"])
                if isinstance(point["date"], str)
                else point["date"]
            )
            for point in equity
        ],
        utc=True,
    )
    if not equity or not timestamps.is_monotonic_increasing or not timestamps.is_unique:
        raise ValueError("Equity dates must be nonempty, ordered and unique")
    if any(not isfinite(point["value"]) for point in equity):
        raise ValueError("Equity contains non-finite values")
    if not isclose(result["final_value"], equity[-1]["value"], abs_tol=0.01):
        raise ValueError("Final value differs from last equity point")
    expected = 100 * (result["final_value"] / result["initial_capital"] - 1)
    if not isclose(result["total_return_pct"], expected, abs_tol=0.006):
        raise ValueError("Return differs from final value divided by starting capital")
    if not isfinite(result["benchmark"]["total_return_pct"]):
        raise ValueError("Missing or non-finite benchmark return")
    shares = 0
    filled = 0
    rejected = 0
    for order in result["trades"]:
        if order["status"] == "rejected":
            rejected += 1
        if order["status"] == "filled":
            filled += 1
            shares += order["shares"] if order["side"] == "buy" else -order["shares"]
            if shares < -1e-8:
                raise ValueError("Ledger sold more shares than it bought")
    if (filled, rejected) != (result["filled_orders"], result["rejected_orders"]):
        raise ValueError("Order counts differ from ledger")


def evaluate(fetcher, symbols):
    with patch("alphalab.api.routes.DataFetcher", return_value=fetcher):
        app = create_app()
    rows = []
    strategies = list(STRATEGY_MAP) + list(EXPERIMENTAL)
    with app.test_client() as client:
        for window, (start, end) in WINDOWS.items():
            for ticker in symbols:
                for strategy in strategies:
                    for profile, settings in PROFILES.items():
                        interval = "1wk" if strategy == "greenblatt_weekly" else "1d"
                        payload = dict(
                            settings,
                            ticker=ticker,
                            strategy=strategy,
                            start_date=start,
                            end_date=end,
                            interval=interval,
                        )
                        row = dict(
                            window=window,
                            ticker=ticker,
                            strategy=strategy,
                            profile=profile,
                            interval=interval,
                        )
                        try:
                            if strategy in EXPERIMENTAL:
                                result = run_experiment(
                                    app, fetcher, payload, EXPERIMENTAL[strategy]
                                )
                            else:
                                response = client.post(
                                    "/api/strategies/backtest", json=payload
                                )
                                body = response.get_json()
                                if response.status_code != 200:
                                    raise ValueError(
                                        f"HTTP {response.status_code}: {body}"
                                    )
                                result = body["data"]
                            check_result(result)
                            row.update(
                                return_pct=float(result["total_return_pct"]),
                                benchmark_pct=float(
                                    result["benchmark"]["total_return_pct"]
                                ),
                                drawdown_pct=float(
                                    result["metrics"]["drawdown"]["max_drawdown_pct"]
                                ),
                                round_trips=int(result["total_trades"]),
                                filled_orders=int(result["filled_orders"]),
                                rejected_orders=int(result["rejected_orders"]),
                                bars=len(result["equity_curve"]),
                                warnings=result["data_quality_warnings"],
                                halted=bool(
                                    (result["drawdown_halt"] or {}).get("halted")
                                ),
                            )
                        except (ValueError, KeyError, TypeError) as error:
                            row["error"] = str(error)
                        finally:
                            app.extensions["results_store"].clear()
                        rows.append(row)
            print(f"{window}: {len(rows)} scenarios complete", flush=True)
        parity_errors, parity_checks = verify_endpoint_parity(client, symbols, rows)
    return rows, parity_errors, parity_checks


def verify_endpoint_parity(client, symbols, rows):
    """Match independently submitted compare and batch results to HTTP singles."""
    window = "2020-2022"
    start, end = WINDOWS[window]
    singles = {
        (row["ticker"], row["strategy"], row["profile"]): row
        for row in rows
        if row["window"] == window and row["strategy"] in STRATEGY_MAP
    }
    failures = []
    checks = 0

    def compare(endpoint, ticker, strategy, profile, result):
        nonlocal checks
        checks += 1
        single = singles[ticker, strategy, profile]
        if (
            "error" in single
            or "total_return_pct" not in result
            or not isclose(
                result["total_return_pct"], single["return_pct"], abs_tol=0.006
            )
            or result["total_trades"] != single["round_trips"]
            or result["metrics"]["drawdown"]["max_drawdown_pct"]
            != single["drawdown_pct"]
        ):
            failures.append(
                dict(
                    endpoint=endpoint, ticker=ticker, strategy=strategy, profile=profile
                )
            )

    for profile, settings in PROFILES.items():
        payload = dict(settings, start_date=start, end_date=end)
        for ticker in symbols:
            response = client.post(
                "/api/compare",
                json=dict(payload, ticker=ticker, strategies=list(STRATEGY_MAP)),
            )
            results = response.get_json().get("data", {})
            for strategy in STRATEGY_MAP:
                compare("compare", ticker, strategy, profile, results.get(strategy, {}))
        for strategy in STRATEGY_MAP:
            response = client.post(
                "/api/strategies/batch-backtest",
                json=dict(payload, tickers=list(symbols), strategy=strategy),
            )
            results = {
                result["ticker"]: result
                for result in response.get_json().get("data", {}).get("results", [])
            }
            for ticker in symbols:
                compare("batch", ticker, strategy, profile, results.get(ticker, {}))
    return failures, checks


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        if "error" not in row:
            groups[row["strategy"]].append(row)
    return {
        strategy: {
            "runs": len(group),
            "no_fills": sum(row["filled_orders"] == 0 for row in group),
            "beat_benchmark": sum(
                row["return_pct"] > row["benchmark_pct"] for row in group
            ),
            "median_return_pct": median(row["return_pct"] for row in group),
            "worst_drawdown_pct": max(group, key=lambda row: abs(row["drawdown_pct"]))[
                "drawdown_pct"
            ],
        }
        for strategy, group in groups.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--symbols", nargs="+", choices=SYMBOLS, default=SYMBOLS)
    args = parser.parse_args()
    logging.disable(logging.INFO)
    rows, parity_errors, parity_checks = evaluate(
        ParquetFetcher(args.data), args.symbols
    )
    errors = sum("error" in row for row in rows)
    report = {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "generated": date.today().isoformat(),
        "dataset": str(args.data.resolve()),
        "windows": WINDOWS,
        "profiles": PROFILES,
        "scenario_count": len(rows),
        "error_count": errors,
        "endpoint_parity_checks": parity_checks,
        "endpoint_parity_errors": parity_errors,
        "summary": summarize(rows),
        "scenarios": rows,
    }
    # Serialize before touching the destination so failure cannot publish a partial report.
    encoded = json.dumps(report, indent=2, allow_nan=False)
    with NamedTemporaryFile(mode="w", dir=args.report.parent, delete=False) as output:
        output.write(encoded + "\n")
    Path(output.name).replace(args.report)
    print(f"{len(rows) - errors}/{len(rows)} checks passed. Report: {args.report}")
    print(
        f"{parity_checks - len(parity_errors)}/{parity_checks} endpoint parity checks passed."
    )
    return int(bool(errors or parity_errors))


if __name__ == "__main__":
    raise SystemExit(main())
