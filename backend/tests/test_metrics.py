"""Tests for PerformanceMetrics calculator."""

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
    return [{"date": str(d.date()), "value": round(v, 2)} for d, v in zip(dates, values)]


def _make_trades():
    """Generate sample trade log."""
    return [
        {"side": "buy", "status": "filled", "filled_price": 100, "shares": 10, "commission": 0},
        {"side": "sell", "status": "filled", "filled_price": 110, "shares": 10, "commission": 0},
        {"side": "buy", "status": "filled", "filled_price": 105, "shares": 10, "commission": 0},
        {"side": "sell", "status": "filled", "filled_price": 95, "shares": 10, "commission": 0},
    ]


class TestPerformanceMetrics:
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
