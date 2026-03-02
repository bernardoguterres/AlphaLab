"""Performance metrics calculator — industry-standard backtesting analytics."""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.metrics")

TRADING_DAYS = 252


class PerformanceMetrics:
    """Calculate comprehensive performance metrics from backtest results.

    Includes return, risk, drawdown, trade, consistency, and benchmark
    comparison metrics following quantitative-finance conventions.
    """

    def __init__(self, risk_free_rate: float = 0.04):
        self.rf = risk_free_rate

    def calculate_all(
        self,
        equity_curve: list[dict],
        trades: list[dict],
        benchmark_curve: Optional[list[dict]] = None,
    ) -> dict:
        """Compute all metric groups from equity curve and trade log.

        Args:
            equity_curve: List of {"date": ..., "value": ...} dicts.
            trades: Portfolio ledger entries.
            benchmark_curve: Optional benchmark equity curve for comparison.

        Returns:
            Nested dict with keys: returns, risk, drawdown, trades,
            consistency, vs_benchmark.
        """
        if not equity_curve:
            return self._empty_metrics()

        eq = pd.DataFrame(equity_curve)
        eq["date"] = pd.to_datetime(eq["date"])
        eq = eq.set_index("date").sort_index()
        eq["return"] = eq["value"].pct_change()

        result = {
            "returns": self._return_metrics(eq),
            "risk": self._risk_metrics(eq),
            "drawdown": self._drawdown_metrics(eq),
            "trades": self._trade_metrics(trades),
            "consistency": self._consistency_metrics(eq),
        }

        if benchmark_curve:
            bm = pd.DataFrame(benchmark_curve)
            bm["date"] = pd.to_datetime(bm["date"])
            bm = bm.set_index("date").sort_index()
            bm["return"] = bm["value"].pct_change()
            result["vs_benchmark"] = self._benchmark_metrics(eq, bm)
        else:
            result["vs_benchmark"] = {}

        return result

    # ------------------------------------------------------------------
    # Return metrics
    # ------------------------------------------------------------------

    def _return_metrics(self, eq: pd.DataFrame) -> dict:
        total = eq["value"].iloc[-1] / eq["value"].iloc[0] - 1 if eq["value"].iloc[0] else 0
        n_days = len(eq)
        years = max(n_days / TRADING_DAYS, 1 / TRADING_DAYS)
        cagr = (1 + total) ** (1 / years) - 1 if total > -1 else -1

        rets = eq["return"].dropna()
        monthly = eq["value"].resample("ME").last().pct_change().dropna()
        yearly = eq["value"].resample("YE").last().pct_change().dropna()

        return {
            "total_return_pct": round(total * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "mean_daily_return": round(float(rets.mean()) * 100, 4),
            "std_daily_return": round(float(rets.std()) * 100, 4),
            "skewness": round(float(rets.skew()), 4),
            "kurtosis": round(float(rets.kurt()), 4),
            "best_day_pct": round(float(rets.max()) * 100, 2),
            "worst_day_pct": round(float(rets.min()) * 100, 2),
            "monthly_returns": [round(float(m) * 100, 2) for m in monthly.values],
            "yearly_returns": [round(float(y) * 100, 2) for y in yearly.values],
        }

    # ------------------------------------------------------------------
    # Risk metrics
    # ------------------------------------------------------------------

    def _risk_metrics(self, eq: pd.DataFrame) -> dict:
        rets = eq["return"].dropna()
        if len(rets) < 2:
            return {"sharpe": 0, "sortino": 0, "calmar": 0}

        vol = float(rets.std()) * np.sqrt(TRADING_DAYS)
        annual_ret = float(rets.mean()) * TRADING_DAYS
        excess = annual_ret - self.rf

        sharpe = excess / vol if vol > 0 else 0.0

        # Sortino: downside deviation only
        downside = rets[rets < 0]
        down_std = float(downside.std()) * np.sqrt(TRADING_DAYS) if len(downside) > 1 else 0
        sortino = excess / down_std if down_std > 0 else 0.0

        # Calmar
        dd_info = self._compute_drawdown(eq)
        max_dd = dd_info["max_drawdown_pct"] / 100
        calmar = annual_ret / abs(max_dd) if max_dd != 0 else 0.0

        # VaR and CVaR
        var_95 = float(rets.quantile(0.05)) * 100
        var_99 = float(rets.quantile(0.01)) * 100
        cvar_95 = float(rets[rets <= rets.quantile(0.05)].mean()) * 100 if (rets <= rets.quantile(0.05)).any() else var_95

        return {
            "volatility_annual_pct": round(vol * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            "var_95_pct": round(var_95, 4),
            "var_99_pct": round(var_99, 4),
            "cvar_95_pct": round(cvar_95, 4),
        }

    # ------------------------------------------------------------------
    # Drawdown
    # ------------------------------------------------------------------

    def _drawdown_metrics(self, eq: pd.DataFrame) -> dict:
        return self._compute_drawdown(eq)

    @staticmethod
    def _compute_drawdown(eq: pd.DataFrame) -> dict:
        values = eq["value"]
        peak = values.cummax()
        dd = (values - peak) / peak

        max_dd = float(dd.min()) * 100
        avg_dd = float(dd[dd < 0].mean()) * 100 if (dd < 0).any() else 0

        # Duration analysis
        underwater = dd < 0
        if underwater.any():
            groups = (~underwater).cumsum()
            uw_groups = underwater.groupby(groups)
            durations = [g.sum() for _, g in uw_groups if g.any()]
            max_duration = max(durations) if durations else 0
            avg_duration = np.mean(durations) if durations else 0
        else:
            max_duration = 0
            avg_duration = 0

        # Recovery from max drawdown
        max_dd_idx = dd.idxmin()
        post_dd = values.loc[max_dd_idx:]
        pre_dd_peak = peak.loc[max_dd_idx]
        recovered = post_dd[post_dd >= pre_dd_peak]
        recovery_days = (recovered.index[0] - max_dd_idx).days if len(recovered) > 0 else None

        return {
            "max_drawdown_pct": round(max_dd, 2),
            "avg_drawdown_pct": round(avg_dd, 2),
            "max_drawdown_duration_days": int(max_duration),
            "avg_drawdown_duration_days": round(float(avg_duration), 1),
            "recovery_days": recovery_days,
            "drawdown_series": [round(float(d) * 100, 2) for d in dd.values],
        }

    # ------------------------------------------------------------------
    # Trade statistics
    # ------------------------------------------------------------------

    @staticmethod
    def _trade_metrics(trades: list[dict]) -> dict:
        if not trades:
            return {"total_trades": 0, "win_rate": 0}

        filled = [t for t in trades if t.get("status") == "filled"]
        buys = [t for t in filled if t.get("side") == "buy"]
        sells = [t for t in filled if t.get("side") == "sell"]

        # Pair buys and sells to compute per-trade P&L
        pnls = []
        buy_stack: list[dict] = []
        for t in filled:
            if t.get("side") == "buy":
                buy_stack.append(t)
            elif t.get("side") == "sell" and buy_stack:
                buy = buy_stack.pop(0)
                buy_price = buy.get("filled_price", 0) or 0
                sell_price = t.get("filled_price", 0) or 0
                shares = min(buy.get("shares", 0), t.get("shares", 0))
                pnl = (sell_price - buy_price) * shares
                pnl -= (buy.get("commission", 0) + t.get("commission", 0))
                pnls.append(pnl)

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(pnls) if pnls else 0

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        return {
            "total_trades": len(filled),
            "round_trips": len(pnls),
            "win_rate": round(win_rate, 4),
            "avg_win": round(float(avg_win), 2),
            "avg_loss": round(float(avg_loss), 2),
            "profit_factor": round(profit_factor, 4),
            "expectancy": round(float(expectancy), 2),
            "best_trade": round(max(pnls), 2) if pnls else 0,
            "worst_trade": round(min(pnls), 2) if pnls else 0,
            "total_commission": round(sum(t.get("commission", 0) for t in filled), 2),
        }

    # ------------------------------------------------------------------
    # Consistency
    # ------------------------------------------------------------------

    @staticmethod
    def _consistency_metrics(eq: pd.DataFrame) -> dict:
        monthly = eq["value"].resample("ME").last().pct_change().dropna()
        yearly = eq["value"].resample("YE").last().pct_change().dropna()

        profitable_months = (monthly > 0).sum()
        total_months = len(monthly)
        profitable_years = (yearly > 0).sum()
        total_years = len(yearly)

        # Winning/losing streaks
        signs = (eq["return"].dropna() > 0).astype(int)
        streaks = signs.groupby((signs != signs.shift()).cumsum())
        win_streaks = [len(g) for _, g in streaks if g.iloc[0] == 1]
        loss_streaks = [len(g) for _, g in streaks if g.iloc[0] == 0]

        # Rolling Sharpe (252-day)
        rolling_ret = eq["return"].rolling(TRADING_DAYS).mean() * TRADING_DAYS
        rolling_vol = eq["return"].rolling(TRADING_DAYS).std() * np.sqrt(TRADING_DAYS)
        rolling_sharpe = (rolling_ret / rolling_vol.replace(0, np.nan)).dropna()

        # Ulcer Index
        drawdown = (eq["value"] / eq["value"].cummax() - 1) * 100
        ulcer = np.sqrt((drawdown ** 2).rolling(14).mean())

        return {
            "profitable_months": int(profitable_months),
            "total_months": int(total_months),
            "profitable_months_pct": round(profitable_months / max(total_months, 1) * 100, 1),
            "profitable_years": int(profitable_years),
            "total_years": int(total_years),
            "longest_win_streak": max(win_streaks) if win_streaks else 0,
            "longest_loss_streak": max(loss_streaks) if loss_streaks else 0,
            "ulcer_index": round(float(ulcer.iloc[-1]), 4) if len(ulcer) > 0 and not np.isnan(ulcer.iloc[-1]) else 0,
            "rolling_sharpe_latest": round(float(rolling_sharpe.iloc[-1]), 4) if len(rolling_sharpe) > 0 else 0,
        }

    # ------------------------------------------------------------------
    # Benchmark comparison
    # ------------------------------------------------------------------

    def _benchmark_metrics(self, eq: pd.DataFrame, bm: pd.DataFrame) -> dict:
        # Align dates
        common = eq.index.intersection(bm.index)
        if len(common) < 20:
            return {"error": "Insufficient overlapping dates for benchmark comparison"}

        strat_ret = eq.loc[common, "return"].dropna()
        bench_ret = bm.loc[common, "return"].dropna()
        common_idx = strat_ret.index.intersection(bench_ret.index)
        strat_ret = strat_ret.loc[common_idx]
        bench_ret = bench_ret.loc[common_idx]

        if len(strat_ret) < 20:
            return {}

        # Beta and Alpha
        cov = np.cov(strat_ret, bench_ret)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0
        alpha_annual = (float(strat_ret.mean()) - beta * float(bench_ret.mean())) * TRADING_DAYS

        # Tracking error
        active_ret = strat_ret - bench_ret
        tracking_error = float(active_ret.std()) * np.sqrt(TRADING_DAYS)

        # Information ratio
        ir = float(active_ret.mean()) * TRADING_DAYS / tracking_error if tracking_error > 0 else 0

        # Up/Down capture
        up_market = bench_ret > 0
        down_market = bench_ret < 0
        up_capture = (
            float(strat_ret[up_market].mean()) / float(bench_ret[up_market].mean()) * 100
            if up_market.any() and bench_ret[up_market].mean() != 0 else 0
        )
        down_capture = (
            float(strat_ret[down_market].mean()) / float(bench_ret[down_market].mean()) * 100
            if down_market.any() and bench_ret[down_market].mean() != 0 else 0
        )

        # Statistical significance: is alpha > 0?
        if len(active_ret) > 30:
            t_stat, p_value = scipy_stats.ttest_1samp(active_ret, 0)
        else:
            t_stat, p_value = 0, 1

        return {
            "beta": round(beta, 4),
            "alpha_annual_pct": round(alpha_annual * 100, 2),
            "tracking_error_pct": round(tracking_error * 100, 2),
            "information_ratio": round(ir, 4),
            "up_capture_pct": round(up_capture, 2),
            "down_capture_pct": round(down_capture, 2),
            "alpha_t_stat": round(float(t_stat), 4),
            "alpha_p_value": round(float(p_value), 4),
            "alpha_significant": float(p_value) < 0.05,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_metrics() -> dict:
        return {
            "returns": {},
            "risk": {},
            "drawdown": {},
            "trades": {"total_trades": 0},
            "consistency": {},
            "vs_benchmark": {},
        }
