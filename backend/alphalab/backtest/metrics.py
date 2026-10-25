"""Performance metrics calculator - industry-standard backtesting analytics."""

import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.metrics")

# Finite ceiling substituted for +/-Infinity (audit bug 3.5). Matches the
# cap scripts/export_greenblatt_configs.py already applied to profit_factor
# alone, inconsistently - now applied uniformly to every metric, everywhere
# they're computed (this module is the single source both Flask endpoints
# and both standalone export scripts read metrics from).
_INF_CAP = 999.0


def _sanitize_for_json(obj):
    """Recursively replace NaN with None and +/-Infinity with a large
    finite sentinel.

    NaN and Infinity are not valid JSON per RFC 8259, even though Python's
    json module emits the literal tokens NaN/Infinity/-Infinity by default
    and neither Flask's jsonify nor json.dumps reject them - they throw on
    strict client-side JSON.parse instead. Thin/early equity curves produce
    NaN for mean_daily_return/skewness/etc. (too few return observations);
    an all-winning-trade backtest produces profit_factor=Infinity (zero
    gross loss). Applied once here, at calculate_all()'s return boundary,
    so every metric group is covered uniformly rather than patching each
    NaN-prone field individually.
    """
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return _INF_CAP if obj > 0 else -_INF_CAP
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


# Historical default / fallback only - do NOT use this directly for
# annualization. Every annualized metric below infers the actual number of
# return observations per year from the equity curve's own date spacing
# (see _infer_periods_per_year), because this class is used for daily AND
# weekly bar strategies (e.g. GreenblattWeekly) alike. Hardcoding 252 here
# previously caused weekly-bar CAGR/Sharpe to be wildly overstated - a
# 3-year weekly backtest (~157 bars) was annualized as if it spanned
# 157/252 = 0.62 years instead of ~3.02 years. Fixed 2026-07-12; see
# docs/STRATEGY_RESEARCH_PLAN.md and the AlphaLab CLAUDE.md changelog for
# the discovery and its implications for previously-reported weekly results.
TRADING_DAYS = 252

# Minimum denominator (as a fraction, e.g. 0.0001 = 0.01%) below which
# volatility/drawdown is treated as "no meaningful signal to divide by"
# rather than computing a ratio (audit bug 3.6). A near-zero-but-nonzero
# volatility (e.g. a backtest that's flat cash for all but a couple of
# bars) previously passed the old `vol > 0` guard and produced a Sharpe
# ratio of ~1.2e14 on a real reproduction - meaningless at any magnitude,
# not just "large". Below this floor there genuinely isn't enough signal
# to compute a ratio; 0.0 (the same fallback already used for the exact-
# zero case) is the honest answer, not an astronomically large number.
_MIN_RATIO_DENOMINATOR = 1e-4


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
        eq["return"] = eq["value"].pct_change(fill_method=None)

        periods_per_year = self._infer_periods_per_year(eq.index)

        result = {
            "returns": self._return_metrics(eq, periods_per_year),
            "risk": self._risk_metrics(eq, periods_per_year),
            "drawdown": self._drawdown_metrics(eq),
            "trades": self._trade_metrics(trades),
            "consistency": self._consistency_metrics(eq, periods_per_year),
        }

        result["assumptions"] = {
            "cash_return_pct": 0.0,
            "risk_free_rate_pct": round(self.rf * 100, 4),
            "periods_per_year": periods_per_year,
            "note": (
                "Uninvested cash earns 0%. sharpe_ratio/sortino_ratio subtract "
                "the risk-free rate (opportunity cost of capital), so a "
                "partially invested strategy is charged the hurdle on cash it "
                "never invests; sharpe_ratio_zero_rf is the same ratio with a "
                "zero hurdle. Both are reported; neither is a default change."
            ),
        }
        if trades:
            result["assumptions"]["average_exposure_pct"] = self._average_exposure(
                eq, trades
            )

        if benchmark_curve:
            bm = pd.DataFrame(benchmark_curve)
            bm["date"] = pd.to_datetime(bm["date"])
            bm = bm.set_index("date").sort_index()
            bm["return"] = bm["value"].pct_change(fill_method=None)
            result["vs_benchmark"] = self._benchmark_metrics(eq, bm, periods_per_year)
        else:
            result["vs_benchmark"] = {}

        return _sanitize_for_json(result)

    @staticmethod
    def _infer_periods_per_year(index: pd.DatetimeIndex) -> float:
        """Infer return observations per year from the equity curve's own
        date spacing, instead of assuming daily bars.

        Uses the median gap between consecutive timestamps (robust to a few
        irregular gaps, e.g. holidays) and snaps to the nearest common
        trading calendar (daily=252, weekly=52, monthly=12, quarterly=4,
        annual=1) within 20% tolerance; falls back to a raw 365.25/gap
        estimate for anything else.
        """
        if len(index) < 2:
            return TRADING_DAYS
        median_days = index.to_series().diff().dropna().dt.days.median()
        if not median_days or median_days <= 0:
            return TRADING_DAYS
        calendars = {1: TRADING_DAYS, 7: 52, 30: 12, 91: 4, 365: 1}
        for cal_days, periods in calendars.items():
            if abs(median_days - cal_days) / cal_days < 0.2:
                return periods
        return 365.25 / median_days

    # ------------------------------------------------------------------
    # Return metrics
    # ------------------------------------------------------------------

    def _return_metrics(self, eq: pd.DataFrame, periods_per_year: float) -> dict:
        total = (
            eq["value"].iloc[-1] / eq["value"].iloc[0] - 1 if eq["value"].iloc[0] else 0
        )
        # Calendar time (first to last timestamp), not bar count: a bar
        # count over-states the span by one bar and ignores calendar gaps.
        span_days = (eq.index[-1] - eq.index[0]).days
        if span_days > 0:
            years = span_days / 365.25
        else:
            years = max((len(eq) - 1) / periods_per_year, 1 / periods_per_year)
        cagr = (1 + total) ** (1 / years) - 1 if total > -1 else -1

        rets = eq["return"].dropna()
        monthly = self._period_returns(eq["value"], "ME")
        yearly = self._period_returns(eq["value"], "YE")

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

    @staticmethod
    def _period_returns(values: pd.Series, rule: str) -> pd.Series:
        """Calendar-period returns INCLUDING the first (partial) period,
        measured from the starting value (it was previously dropped)."""
        ends = values.resample(rule).last().dropna()
        if ends.empty:
            return ends
        end_arr = ends.to_numpy(dtype=float)
        starts = np.empty_like(end_arr)
        starts[0] = float(values.iloc[0])
        starts[1:] = end_arr[:-1]
        return pd.Series(end_arr / starts - 1, index=ends.index)

    # ------------------------------------------------------------------
    # Risk metrics
    # ------------------------------------------------------------------

    def _risk_metrics(self, eq: pd.DataFrame, periods_per_year: float) -> dict:
        rets = eq["return"].dropna()
        if len(rets) < 2:
            return {"sharpe": 0, "sortino": 0, "calmar": 0}

        vol = float(rets.std()) * np.sqrt(periods_per_year)
        annual_ret = float(rets.mean()) * periods_per_year
        excess = annual_ret - self.rf

        # audit bug 3.6: `vol > 0` alone let a near-zero-but-nonzero
        # volatility through, blowing Sharpe up to a meaningless magnitude
        # (reproduced: ~1.2e14 on a synthetic near-constant-return series)
        # instead of failing safely. See _MIN_RATIO_DENOMINATOR above.
        sharpe = excess / vol if vol > _MIN_RATIO_DENOMINATOR else 0.0

        # Sortino (Sortino & Price 1994): downside deviation below the
        # per-period minimum acceptable return (the risk-free rate, matching
        # the Sharpe numerator), root-mean-square over ALL observations.
        # Previously: sample std of the negative returns around their own
        # mean - a different (and smaller-sample) quantity.
        mar = self.rf / periods_per_year
        shortfall = np.minimum(rets.to_numpy() - mar, 0.0)
        down_std = float(np.sqrt(np.mean(shortfall**2))) * np.sqrt(periods_per_year)
        sortino = excess / down_std if down_std > _MIN_RATIO_DENOMINATOR else 0.0

        # Calmar: CAGR / |max drawdown| (standard definition; it used the
        # arithmetic annualised mean)
        dd_info = self._compute_drawdown(eq)
        max_dd = dd_info["max_drawdown_pct"] / 100
        cagr = self._return_metrics(eq, periods_per_year)["cagr_pct"] / 100
        calmar = cagr / abs(max_dd) if abs(max_dd) > _MIN_RATIO_DENOMINATOR else 0.0
        # Same ratio with a zero hurdle - a DISTINCT modelling choice that
        # matches the engine's zero-yield cash (see "assumptions").
        sharpe_zero_rf = annual_ret / vol if vol > _MIN_RATIO_DENOMINATOR else 0.0

        # VaR and CVaR
        var_95 = float(rets.quantile(0.05)) * 100
        var_99 = float(rets.quantile(0.01)) * 100
        cvar_95 = (
            float(rets[rets <= rets.quantile(0.05)].mean()) * 100
            if (rets <= rets.quantile(0.05)).any()
            else var_95
        )

        return {
            "volatility_annual_pct": round(vol * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "sharpe_ratio_zero_rf": round(sharpe_zero_rf, 4),
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

        # Duration analysis in CALENDAR days (from the last peak before the
        # drawdown to the first bar back at/above it, or the last bar if
        # unrecovered). It was a bar count labelled "days" - weeks on
        # weekly data.
        underwater = dd < 0
        durations = []
        if underwater.any():
            idx = values.index
            start = None
            for i, uw in enumerate(underwater.to_numpy()):
                if uw and start is None:
                    start = idx[i - 1] if i > 0 else idx[i]
                elif not uw and start is not None:
                    durations.append((idx[i] - start).days)
                    start = None
            if start is not None:
                durations.append((idx[-1] - start).days)
        max_duration = max(durations) if durations else 0
        avg_duration = np.mean(durations) if durations else 0

        # Recovery from max drawdown
        max_dd_idx = dd.idxmin()
        post_dd = values.loc[max_dd_idx:]
        pre_dd_peak = peak.loc[max_dd_idx]
        recovered = post_dd[post_dd >= pre_dd_peak]
        recovery_days = (
            (recovered.index[0] - max_dd_idx).days if len(recovered) > 0 else None
        )

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
    def round_trips(trades: list[dict]) -> list[float]:
        """Completed round trips (flat -> long -> flat), FIFO by quantity.

        Each round trip's P&L sums every lot bought and sold while the
        position was open, net of all commissions. Handles add-on buys and
        partial sells (the previous pairing popped one buy per sell and
        mis-paired anything but strict buy/sell alternation)."""
        filled = [t for t in trades if t.get("status") == "filled"]
        trips: list[float] = []
        lots: list[list[float]] = []  # [qty, price]
        pnl = 0.0
        for t in filled:
            qty = float(t.get("shares", 0) or 0)
            px = float(t.get("filled_price", 0) or 0)
            pnl -= float(t.get("commission", 0) or 0)
            if t.get("side") == "buy":
                lots.append([qty, px])
            elif t.get("side") == "sell" and lots:
                remaining = qty
                while remaining > 1e-9 and lots:
                    take = min(remaining, lots[0][0])
                    pnl += (px - lots[0][1]) * take
                    lots[0][0] -= take
                    remaining -= take
                    if lots[0][0] <= 1e-9:
                        lots.pop(0)
                if not lots:
                    trips.append(pnl)
                    pnl = 0.0
        return trips

    @staticmethod
    def _trade_metrics(trades: list[dict]) -> dict:
        if not trades:
            return {
                "total_trades": 0,
                "round_trips": 0,
                "filled_orders": 0,
                "win_rate": 0,
            }

        filled = [t for t in trades if t.get("status") == "filled"]
        rejected = [t for t in trades if t.get("status") == "rejected"]
        pnls = PerformanceMetrics.round_trips(trades)

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(pnls) if pnls else 0

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf") if gross_profit > 0 else 0
        )

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        return {
            # total_trades = completed round trips (it counted orders: one
            # round trip showed as 2, and rejected orders inflated the
            # exported figure)
            "total_trades": len(pnls),
            "round_trips": len(pnls),
            "filled_orders": len(filled),
            "rejected_orders": len(rejected),
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
    def _consistency_metrics(eq: pd.DataFrame, periods_per_year: float) -> dict:
        monthly = PerformanceMetrics._period_returns(eq["value"], "ME")
        yearly = PerformanceMetrics._period_returns(eq["value"], "YE")

        profitable_months = (monthly > 0).sum()
        total_months = len(monthly)
        profitable_years = (yearly > 0).sum()
        total_years = len(yearly)

        # Winning/losing streaks
        signs = (eq["return"].dropna() > 0).astype(int)
        streaks = signs.groupby((signs != signs.shift()).cumsum())
        win_streaks = [len(g) for _, g in streaks if g.iloc[0] == 1]
        loss_streaks = [len(g) for _, g in streaks if g.iloc[0] == 0]

        # Rolling Sharpe (trailing 1 year, in bar-count terms for this
        # equity curve's own frequency - e.g. a 52-bar window on weekly
        # data, a 252-bar window on daily data).
        window = max(int(round(periods_per_year)), 2)
        rolling_ret = eq["return"].rolling(window).mean() * periods_per_year
        rolling_vol = eq["return"].rolling(window).std() * np.sqrt(periods_per_year)
        rolling_sharpe = (rolling_ret / rolling_vol.replace(0, np.nan)).dropna()

        # Ulcer Index (Martin 1987) over the WHOLE period: RMS of the
        # percentage drawdown from the running peak (it was the last value
        # of a 14-bar rolling window).
        drawdown = (eq["value"] / eq["value"].cummax() - 1) * 100
        ulcer = pd.Series([float(np.sqrt((drawdown**2).mean()))])

        return {
            "profitable_months": int(profitable_months),
            "total_months": int(total_months),
            "profitable_months_pct": round(
                profitable_months / max(total_months, 1) * 100, 1
            ),
            "profitable_years": int(profitable_years),
            "total_years": int(total_years),
            "longest_win_streak": max(win_streaks) if win_streaks else 0,
            "longest_loss_streak": max(loss_streaks) if loss_streaks else 0,
            "ulcer_index": (
                round(float(ulcer.iloc[-1]), 4)
                if len(ulcer) > 0 and not np.isnan(ulcer.iloc[-1])
                else 0
            ),
            "rolling_sharpe_latest": (
                round(float(rolling_sharpe.iloc[-1]), 4)
                if len(rolling_sharpe) > 0
                else 0
            ),
        }

    # ------------------------------------------------------------------
    # Benchmark comparison
    # ------------------------------------------------------------------

    def _benchmark_metrics(
        self, eq: pd.DataFrame, bm: pd.DataFrame, periods_per_year: float
    ) -> dict:
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
        alpha_annual = (
            float(strat_ret.mean()) - beta * float(bench_ret.mean())
        ) * periods_per_year

        # Tracking error
        active_ret = strat_ret - bench_ret
        tracking_error = float(active_ret.std()) * np.sqrt(periods_per_year)

        # Information ratio
        ir = (
            float(active_ret.mean()) * periods_per_year / tracking_error
            if tracking_error > 0
            else 0
        )

        # Up/Down capture
        up_market = bench_ret > 0
        down_market = bench_ret < 0
        up_capture = (
            float(strat_ret[up_market].mean())
            / float(bench_ret[up_market].mean())
            * 100
            if up_market.any() and bench_ret[up_market].mean() != 0
            else 0
        )
        down_capture = (
            float(strat_ret[down_market].mean())
            / float(bench_ret[down_market].mean())
            * 100
            if down_market.any() and bench_ret[down_market].mean() != 0
            else 0
        )

        # One-sample t-test of the mean ACTIVE return (strategy - benchmark)
        # against 0. This is not a test of the regression alpha above (it
        # was labelled alpha_t_stat/alpha_significant).
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
            "active_return_t_stat": round(float(t_stat), 4),
            "active_return_p_value": round(float(p_value), 4),
            "active_return_significant": float(p_value) < 0.05,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _average_exposure(eq: pd.DataFrame, trades: list[dict]) -> float:
        """Mean fraction of equity held in the position, from the order
        ledger (shares held after each bar's fills x cash-implied price)."""
        filled = [
            t for t in trades if t.get("status") == "filled" and t.get("timestamp")
        ]
        if not filled:
            return 0.0
        held = pd.Series(0.0, index=eq.index)
        pos = 0.0
        events = sorted(filled, key=lambda t: pd.Timestamp(t["timestamp"]))
        cash_after = pd.Series(np.nan, index=eq.index)
        for t in events:
            ts = pd.Timestamp(t["timestamp"])
            pos += float(t["shares"]) * (1 if t["side"] == "buy" else -1)
            if ts in held.index:
                held.loc[ts:] = pos
                cash_after.loc[ts] = t.get("portfolio_cash", np.nan)
        cash = cash_after.ffill().fillna(eq["value"].iloc[0])
        exposure = (1 - cash / eq["value"]).clip(lower=0, upper=1)
        exposure[held == 0] = 0.0
        return round(float(exposure.mean() * 100), 2)

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
