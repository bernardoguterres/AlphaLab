"""Tests for PerformanceMetrics calculator."""

import json
import math

import numpy as np
import pandas as pd
import pytest

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.backtest.metrics import PerformanceMetrics


def _make_equity_curve(n=252, start_val=10_000, annual_return=0.10, seed=42):
    """Generate a synthetic equity curve."""
    rng = np.random.RandomState(seed)
    daily_ret = annual_return / 252
    daily_vol = 0.01
    returns = rng.normal(daily_ret, daily_vol, n)
    values = [start_val]
    for r in returns:
        values.append(values[-1] * (1 + r))
    dates = pd.bdate_range("2023-01-01", periods=n + 1)
    return [
        {"date": str(d.date()), "value": round(v, 2)} for d, v in zip(dates, values)
    ]


def _make_trades():
    """Generate sample trade log."""
    return [
        {
            "side": "buy",
            "status": "filled",
            "filled_price": 100,
            "shares": 10,
            "commission": 0,
        },
        {
            "side": "sell",
            "status": "filled",
            "filled_price": 110,
            "shares": 10,
            "commission": 0,
        },
        {
            "side": "buy",
            "status": "filled",
            "filled_price": 105,
            "shares": 10,
            "commission": 0,
        },
        {
            "side": "sell",
            "status": "filled",
            "filled_price": 95,
            "shares": 10,
            "commission": 0,
        },
    ]


def _make_weekly_equity_curve(
    n_weeks=157, start_val=100_000, annual_return=0.10, seed=42
):
    """Synthetic WEEKLY-bar equity curve - regression fixture for the
    2026-07-12 TRADING_DAYS=252-hardcoded annualization bug (CAGR/Sharpe
    were silently computed as if weekly bars were daily bars)."""
    rng = np.random.RandomState(seed)
    weekly_ret = annual_return / 52
    weekly_vol = 0.02
    returns = rng.normal(weekly_ret, weekly_vol, n_weeks)
    values = [start_val]
    for r in returns:
        values.append(values[-1] * (1 + r))
    dates = pd.bdate_range("2018-01-01", periods=n_weeks + 1, freq="W-FRI")
    return [
        {"date": str(d.date()), "value": round(v, 2)} for d, v in zip(dates, values)
    ]


class TestPerformanceMetrics:
    def test_weekly_bar_cagr_is_not_inflated_by_daily_bar_assumption(self):
        # Regression test: a ~10%/year weekly-bar equity curve must report
        # CAGR in a sane range (roughly 0-30%, allowing for the specific
        # random draw), NOT the >100% figure that TRADING_DAYS=252 hardcoded
        # for annualization produced when applied to weekly (52/year) data.
        curve = _make_weekly_equity_curve(annual_return=0.10)
        m = PerformanceMetrics()
        result = m.calculate_all(curve, [])
        assert 0 < result["returns"]["cagr_pct"] < 30

    def test_infer_periods_per_year_weekly_vs_daily(self):
        daily_curve = _make_equity_curve(n=252)
        weekly_curve = _make_weekly_equity_curve(n_weeks=104)
        m = PerformanceMetrics()

        daily_idx = pd.to_datetime([c["date"] for c in daily_curve])
        weekly_idx = pd.to_datetime([c["date"] for c in weekly_curve])

        assert m._infer_periods_per_year(daily_idx) == pytest.approx(252, abs=1)
        assert m._infer_periods_per_year(weekly_idx) == pytest.approx(52, abs=1)

    def test_positive_returns(self):
        curve = _make_equity_curve(annual_return=0.15)
        m = PerformanceMetrics()
        result = m.calculate_all(curve, _make_trades())
        assert result["returns"]["total_return_pct"] > 0
        assert result["returns"]["cagr_pct"] > 0

    def test_sharpe_ratio_positive(self):
        curve = _make_equity_curve(annual_return=0.15)
        m = PerformanceMetrics(risk_free_rate=0.04)
        result = m.calculate_all(curve, [])
        assert result["risk"]["sharpe_ratio"] > 0

    def test_max_drawdown_negative(self):
        curve = _make_equity_curve()
        m = PerformanceMetrics()
        result = m.calculate_all(curve, [])
        assert result["drawdown"]["max_drawdown_pct"] <= 0

    def test_trade_statistics(self):
        m = PerformanceMetrics()
        trades = _make_trades()
        result = m.calculate_all(_make_equity_curve(), trades)
        t = result["trades"]
        assert t["total_trades"] == 4
        assert t["round_trips"] == 2
        assert t["win_rate"] == 0.5  # 1 win, 1 loss

    def test_profit_factor(self):
        m = PerformanceMetrics()
        trades = _make_trades()
        result = m.calculate_all(_make_equity_curve(), trades)
        # Win: (110-100)*10 = 100, Loss: (95-105)*10 = -100
        assert result["trades"]["profit_factor"] == 1.0

    def test_empty_curve(self):
        m = PerformanceMetrics()
        result = m.calculate_all([], [])
        assert result["returns"] == {}
        assert result["trades"]["total_trades"] == 0

    def test_benchmark_comparison(self):
        curve = _make_equity_curve(annual_return=0.15, seed=1)
        bench = _make_equity_curve(annual_return=0.10, seed=2)
        m = PerformanceMetrics()
        result = m.calculate_all(curve, [], benchmark_curve=bench)
        assert "beta" in result["vs_benchmark"]
        assert "alpha_annual_pct" in result["vs_benchmark"]

    def test_consistency_metrics(self):
        curve = _make_equity_curve(n=504)  # ~2 years
        m = PerformanceMetrics()
        result = m.calculate_all(curve, [])
        c = result["consistency"]
        assert "profitable_months" in c
        assert "longest_win_streak" in c

    def test_var_cvar(self):
        curve = _make_equity_curve()
        m = PerformanceMetrics()
        result = m.calculate_all(curve, [])
        assert result["risk"]["var_95_pct"] < 0  # VaR is negative (loss)
        assert result["risk"]["cvar_95_pct"] <= result["risk"]["var_95_pct"]


def _assert_no_nan_or_inf(obj, path="result"):
    """Recursively assert no float in `obj` is NaN or +/-Infinity - both
    are invalid JSON per RFC 8259 and throw on strict client-side
    JSON.parse, even though Python's json module emits them by default."""
    if isinstance(obj, float):
        assert not math.isnan(obj), f"{path} is NaN"
        assert not math.isinf(obj), f"{path} is Infinity"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_nan_or_inf(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_nan_or_inf(v, f"{path}[{i}]")


class TestSharpeRatioFloor:
    """Regression tests for audit bug 3.6: Sharpe (and Sortino/Calmar)
    previously guarded only against exactly-zero volatility/drawdown
    (`vol > 0`), so a near-zero-but-nonzero denominator produced a
    meaningless-magnitude ratio (reproduced by the audit: ~1.2e14 on a
    synthetic near-constant-return series) instead of failing safely.
    _MIN_RATIO_DENOMINATOR now floors all three ratios consistently.
    """

    def test_near_constant_returns_does_not_blow_up_sharpe(self):
        """A near-flat equity curve (tiny but real day-to-day noise) must
        not produce an astronomically large Sharpe ratio."""
        m = PerformanceMetrics()
        rng = np.random.RandomState(7)
        n = 252
        # Returns on the order of 1e-9 - far below any realistic asset's
        # volatility, but not exactly zero (floating point noise, the
        # exact scenario the old `vol > 0` guard let through).
        values = [100_000.0]
        for _ in range(n):
            values.append(values[-1] * (1 + rng.normal(1e-9, 1e-9)))
        dates = pd.bdate_range("2023-01-01", periods=n + 1)
        curve = [{"date": str(d.date()), "value": v} for d, v in zip(dates, values)]

        result = m.calculate_all(curve, [])
        sharpe = result["risk"]["sharpe_ratio"]
        vol = result["risk"]["volatility_annual_pct"]

        assert (
            abs(sharpe) < 1000
        ), f"Sharpe blew up to a meaningless magnitude: {sharpe}"
        # Internal consistency the audit specifically flagged as missing:
        # a near-zero volatility must not be paired with a huge Sharpe.
        assert round(vol, 1) == 0.0
        assert sharpe == 0.0

    def test_normal_volatility_sharpe_unaffected(self):
        """Sanity check the floor doesn't suppress ordinary, real Sharpe
        ratios on a normal (non-degenerate) equity curve."""
        m = PerformanceMetrics()
        result = m.calculate_all(_make_equity_curve(annual_return=0.15), [])
        assert result["risk"]["sharpe_ratio"] != 0.0
        assert abs(result["risk"]["sharpe_ratio"]) < 100


class TestNaNInfinitySanitization:
    """Regression tests for audit bug 3.5: thin/early-backtest equity
    curves produced NaN for mean_daily_return/skewness/etc. (too few return
    observations), and an all-winning-trade backtest produced
    profit_factor=Infinity with no cap anywhere in the Flask path (one of
    two standalone export scripts capped it at 999, the other didn't -
    inconsistent). calculate_all() now sanitizes its entire return value at
    the boundary: NaN -> None, +/-Infinity -> +/-999.0.
    """

    def test_all_winning_trades_caps_profit_factor_instead_of_infinity(self):
        """Zero gross loss (every trade a winner) previously produced
        profit_factor=Infinity."""
        m = PerformanceMetrics()
        trades = [
            {
                "side": "buy",
                "status": "filled",
                "filled_price": 100,
                "shares": 10,
                "commission": 0,
            },
            {
                "side": "sell",
                "status": "filled",
                "filled_price": 110,
                "shares": 10,
                "commission": 0,
            },
        ]
        result = m.calculate_all(_make_equity_curve(), trades)
        assert result["trades"]["profit_factor"] == 999.0
        assert not math.isinf(result["trades"]["profit_factor"])

    def test_thin_equity_curve_does_not_produce_nan_return_metrics(self):
        """A 2-bar equity curve (1 return observation) can't support
        skewness/kurtosis (need >=3-4 points) - these must come back as
        None, not a bare NaN float."""
        m = PerformanceMetrics()
        curve = [
            {"date": "2024-01-01", "value": 10_000.0},
            {"date": "2024-01-02", "value": 10_050.0},
        ]
        result = m.calculate_all(curve, [])
        _assert_no_nan_or_inf(result, "result")
        # skewness/kurtosis genuinely can't be computed from 1 observation -
        # None (JSON null) is the honest representation, not a silent 0.0.
        assert result["returns"]["skewness"] is None
        assert result["returns"]["kurtosis"] is None

    def test_single_bar_equity_curve_fully_sanitized(self):
        """A single-bar curve (0 return observations - the most extreme
        thin-curve case) must not leak NaN anywhere in the response."""
        m = PerformanceMetrics()
        curve = [{"date": "2024-01-01", "value": 10_000.0}]
        result = m.calculate_all(curve, [])
        _assert_no_nan_or_inf(result, "result")

    def test_normal_backtest_result_has_no_nan_or_inf(self):
        """Sanity check the sanitizer doesn't corrupt ordinary finite
        values in a normal, non-degenerate backtest result."""
        m = PerformanceMetrics()
        result = m.calculate_all(_make_equity_curve(), _make_trades())
        _assert_no_nan_or_inf(result, "result")
        assert result["trades"]["profit_factor"] == 1.0  # unchanged, not capped

    def test_sanitized_result_is_valid_json(self):
        """End-to-end proof: json.dumps(..., allow_nan=False) - the RFC
        8259-strict mode - must not raise on a degenerate result that used
        to contain NaN/Infinity."""
        m = PerformanceMetrics()
        trades = [
            {
                "side": "buy",
                "status": "filled",
                "filled_price": 100,
                "shares": 10,
                "commission": 0,
            },
            {
                "side": "sell",
                "status": "filled",
                "filled_price": 110,
                "shares": 10,
                "commission": 0,
            },
        ]
        curve = [
            {"date": "2024-01-01", "value": 10_000.0},
            {"date": "2024-01-02", "value": 10_050.0},
        ]
        result = m.calculate_all(curve, trades)
        json.dumps(result, allow_nan=False)  # raises ValueError if NaN/Infinity present
