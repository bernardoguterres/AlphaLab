"""Portfolio optimization using Modern Portfolio Theory."""

from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..utils.logger import setup_logger
from .metrics import PerformanceMetrics, TRADING_DAYS

logger = setup_logger("alphalab.portfolio_optimizer")
WEIGHT_TOLERANCE = 1e-8
_PERIODS_PER_YEAR = {"1d": TRADING_DAYS, "1wk": 52, "1mo": 12}
_PERIOD_CALENDARS = {52: "W-SUN", 12: "M"}


class PortfolioOptimizer:
    """Optimize portfolio weights across multiple strategies."""

    def __init__(self, returns_matrix: pd.DataFrame, risk_free_rate: float = 0.04):
        """Initialize optimizer.

        Args:
            returns_matrix: Aligned period returns for each strategy. Daily
                annualization applies if the matrix has no cadence metadata.
            risk_free_rate: Annual risk-free rate (default 4%)
        """
        if len(returns_matrix) < 2:
            raise ValueError(
                "Portfolio optimization requires at least two shared returns"
            )
        periods_per_year = returns_matrix.attrs.get("periods_per_year", TRADING_DAYS)
        self.returns = returns_matrix
        self.mean_returns = returns_matrix.mean() * periods_per_year
        self.cov_matrix = returns_matrix.cov() * periods_per_year
        self.risk_free_rate = risk_free_rate
        self.n_strategies = len(returns_matrix.columns)

    def optimize(
        self,
        method: str,
        max_weight: float | None = None,
        min_weight: float = 0.05,
        target_return: float | None = None,
    ) -> dict:
        """Optimize portfolio weights.

        Args:
            method: Optimization method (max_sharpe, min_variance, equal_weight, risk_parity)
            max_weight: Maximum weight per strategy (0-1). If omitted,
                defaults to 40% or the equal share, whichever is larger.
            min_weight: Minimum weight per strategy (0-1)
            target_return: Target annual return (only used for min_variance with target)

        Returns:
            Dict with optimal_weights, expected_return, expected_risk, sharpe_ratio
        """
        max_weight = self._resolve_weight_bounds(min_weight, max_weight)
        if method == "equal_weight":
            weights = self._equal_weight()
        elif method == "max_sharpe":
            weights = self._max_sharpe(max_weight, min_weight)
        elif method == "min_variance":
            weights = self._min_variance(max_weight, min_weight, target_return)
        elif method == "risk_parity":
            weights = self._risk_parity(max_weight, min_weight)
        else:
            raise ValueError(f"Unknown optimization method: {method}")

        # Calculate portfolio metrics
        portfolio_return = np.dot(weights, self.mean_returns)
        portfolio_std = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        sharpe_ratio = (
            (portfolio_return - self.risk_free_rate) / portfolio_std
            if portfolio_std > 0
            else 0
        )

        return {
            "optimal_weights": weights.tolist(),
            "expected_return": float(portfolio_return),
            "expected_risk": float(portfolio_std),
            "sharpe_ratio": float(sharpe_ratio),
        }

    def efficient_frontier(
        self,
        n_points: int = 20,
        max_weight: float | None = None,
        min_weight: float = 0.05,
    ) -> list[dict]:
        """Calculate efficient frontier points.

        Args:
            n_points: Number of points to calculate
            max_weight: Maximum weight per strategy
            min_weight: Minimum weight per strategy

        Returns:
            List of dicts with return, risk, sharpe_ratio for each point
        """
        max_weight = self._resolve_weight_bounds(min_weight, max_weight)
        min_return, max_return = self._return_bounds(min_weight, max_weight)
        if np.isclose(min_return, max_return, atol=WEIGHT_TOLERANCE, rtol=0):
            # Fixed weights or identical returns give just one possible return.
            target_returns = [min_return]
        else:
            target_returns = np.linspace(min_return, max_return, n_points)

        frontier_points = []
        for target_return in target_returns:
            try:
                weights = self._min_variance(max_weight, min_weight, target_return)
                portfolio_return = np.dot(weights, self.mean_returns)
                portfolio_std = np.sqrt(
                    np.dot(weights.T, np.dot(self.cov_matrix, weights))
                )
                sharpe = (
                    (portfolio_return - self.risk_free_rate) / portfolio_std
                    if portfolio_std > 0
                    else 0
                )

                frontier_points.append(
                    {
                        "return": float(portfolio_return),
                        "risk": float(portfolio_std),
                        "sharpe_ratio": float(sharpe),
                    }
                )
            except ValueError as e:
                logger.debug(f"Skipping frontier point at return {target_return}: {e}")
                continue

        return frontier_points

    def _resolve_weight_bounds(
        self, min_weight: float, max_weight: float | None
    ) -> float:
        if not self.n_strategies:
            raise ValueError("At least one strategy is required")
        equal_share = 1 / self.n_strategies
        if max_weight is None:
            max_weight = max(0.4, equal_share)
        if not 0 <= min_weight <= equal_share <= max_weight <= 1:
            raise ValueError(
                "Strategy weight bounds cannot produce a fully invested portfolio "
                f"with {self.n_strategies} strategies"
            )
        return max_weight

    def _return_bounds(
        self, min_weight: float, max_weight: float
    ) -> tuple[float, float]:
        # Start each strategy at the floor, then assign the remaining weight
        # to strategies in order of return until their caps are reached.
        remaining = max(0.0, 1 - self.n_strategies * min_weight)
        excess = np.clip(
            remaining - np.arange(self.n_strategies) * (max_weight - min_weight),
            0,
            max_weight - min_weight,
        )
        weights = min_weight + excess
        returns = np.sort(self.mean_returns)
        return float(weights @ returns), float(weights @ returns[::-1])

    def _equal_weight(self) -> np.ndarray:
        """Equal weight allocation (1/N)."""
        return np.ones(self.n_strategies) / self.n_strategies

    def _max_sharpe(self, max_weight: float, min_weight: float) -> np.ndarray:
        """Maximize Sharpe ratio."""

        def neg_sharpe(weights):
            port_return = np.dot(weights, self.mean_returns)
            port_std = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            sharpe = (
                (port_return - self.risk_free_rate) / port_std if port_std > 0 else 0
            )
            return -sharpe  # Negative because we minimize

        return self._optimize_weights(neg_sharpe, max_weight, min_weight)

    def _min_variance(
        self,
        max_weight: float,
        min_weight: float,
        target_return: float | None = None,
    ) -> np.ndarray:
        """Minimize portfolio variance."""

        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(self.cov_matrix, weights))

        constraints = []
        if target_return is not None:
            min_return, max_return = self._return_bounds(min_weight, max_weight)
            if (
                not min_return - WEIGHT_TOLERANCE
                <= target_return
                <= max_return + WEIGHT_TOLERANCE
            ):
                raise ValueError(
                    "Target return is outside the feasible range for these bounds"
                )
            if max_return - min_return > WEIGHT_TOLERANCE:
                constraints.append(
                    {
                        "type": "eq",
                        "fun": lambda w: np.dot(w, self.mean_returns) - target_return,
                    }
                )

        return self._optimize_weights(
            portfolio_variance, max_weight, min_weight, constraints
        )

    def _risk_parity(self, max_weight: float, min_weight: float) -> np.ndarray:
        """Equal risk contribution from each strategy."""

        def risk_parity_objective(weights):
            # Calculate marginal risk contribution
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            marginal_contrib = (
                np.dot(self.cov_matrix, weights) / portfolio_std
                if portfolio_std > 0
                else np.zeros_like(weights)
            )
            risk_contrib = weights * marginal_contrib

            # We want all risk contributions to be equal
            # Minimize sum of squared differences from equal risk
            target_risk = risk_contrib.sum() / self.n_strategies
            return np.sum((risk_contrib - target_risk) ** 2)

        return self._optimize_weights(risk_parity_objective, max_weight, min_weight)

    def _optimize_weights(
        self,
        objective_func,
        max_weight: float,
        min_weight: float,
        extra_constraints: list | None = None,
    ) -> np.ndarray:
        """Generic weight optimization with constraints."""
        # Initial guess: equal weights
        x0 = np.ones(self.n_strategies) / self.n_strategies
        if min_weight == x0[0] or max_weight == x0[0]:
            return x0  # The bounds leave no other feasible weight vector.

        # Constraints
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1}  # Weights sum to 1
        ]
        if extra_constraints:
            constraints.extend(extra_constraints)

        # Bounds: each weight between min_weight and max_weight
        bounds = tuple((min_weight, max_weight) for _ in range(self.n_strategies))

        # Optimize
        result = minimize(
            objective_func,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9},
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
            raise ValueError("Portfolio optimizer did not converge")

        weights = result.x
        if (
            not np.isfinite(weights).all()
            or np.any(weights < min_weight - WEIGHT_TOLERANCE)
            or np.any(weights > max_weight + WEIGHT_TOLERANCE)
            or any(
                not np.isclose(
                    constraint["fun"](weights), 0, atol=WEIGHT_TOLERANCE, rtol=0
                )
                for constraint in constraints
            )
        ):
            raise ValueError("Portfolio optimizer returned an infeasible allocation")
        return weights


def extract_daily_returns(equity_curve: list[dict[str, Any]]) -> pd.Series:
    """Extract daily returns from equity curve.

    Args:
        equity_curve: List of dicts with 'date' and 'value' keys

    Returns:
        Series of daily returns (percentage)
    """
    return _equity_levels(equity_curve).pct_change(fill_method=None).dropna()


def _equity_levels(equity_curve: list[dict[str, Any]]) -> pd.Series:
    df = pd.DataFrame(equity_curve)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["value"].sort_index()


def build_returns_matrix(
    strategies: list[dict],
    backtest_results: dict[str, dict],
) -> tuple[pd.DataFrame, list[str]]:
    """Build returns matrix from multiple backtest results.

    Args:
        strategies: List of dicts with backtest_id, ticker, strategy
        backtest_results: Backtest IDs mapped to saved results, with optional
            request details for newer runs.

    Returns:
        Aligned returns with annualization metadata, and strategy labels.
    """
    backtest_ids = [strategy["backtest_id"] for strategy in strategies]
    if len(set(backtest_ids)) != len(backtest_ids):
        raise ValueError("Each backtest can appear only once in a portfolio")

    equity_by_label = {}
    frequencies = set()

    for strat_info in strategies:
        backtest_id = strat_info["backtest_id"]

        if backtest_id not in backtest_results:
            raise ValueError(f"Backtest {backtest_id} not found")

        saved = backtest_results[backtest_id]
        result = saved.get("results", saved)
        equity_curve = result.get("equity_curve", [])

        if not equity_curve:
            raise ValueError(f"Backtest {backtest_id} has no equity curve")

        equity = _equity_levels(equity_curve)
        index = pd.DatetimeIndex(equity.index).tz_localize(None).normalize()
        if index.hasnans:
            raise ValueError(f"Backtest {backtest_id} has invalid equity dates")

        saved_request = saved.get("request") or {}
        interval = saved_request.get("interval")
        if interval is None:
            periods = PerformanceMetrics._infer_periods_per_year(index)
        elif interval in _PERIODS_PER_YEAR:
            periods = _PERIODS_PER_YEAR[interval]
        else:
            raise ValueError(f"Backtest {backtest_id} has an unsupported interval")
        frequencies.add(periods)

        calendar = _PERIOD_CALENDARS.get(periods)
        equity.index = index.to_period(calendar) if calendar else index
        if not equity.index.is_unique:
            raise ValueError(f"Backtest {backtest_id} has duplicate equity periods")

        ticker = saved_request.get("ticker") or strat_info.get("ticker", "Unknown")
        strategy_name = saved_request.get("strategy") or strat_info.get(
            "strategy", "Unknown"
        )
        base_label = f"{ticker}_{strategy_name}"
        label = base_label
        suffix = 2
        while label in equity_by_label:
            label = f"{base_label} ({suffix})"
            suffix += 1
        equity_by_label[label] = equity

    if not equity_by_label:
        raise ValueError("No valid backtest results found")
    if len(frequencies) != 1:
        raise ValueError("Portfolio backtests must use the same bar frequency")
    (periods_per_year,) = frequencies

    start = max(equity.index[0] for equity in equity_by_label.values())
    end = min(equity.index[-1] for equity in equity_by_label.values())
    if start >= end:
        raise ValueError(
            "Portfolio backtests have insufficient overlapping equity dates"
        )

    # Carry the last known equity mark within the shared window. A missing bar
    # is flat until a new mark arrives; it never repeats the previous return.
    # Forward-fill before slicing so a mark predating the common start is
    # available as a baseline, but its earlier return is not sampled.
    marks = pd.concat(equity_by_label, axis=1).sort_index()
    if isinstance(marks.index, pd.PeriodIndex):
        # Different date labels for the same week/month are one period. Keep
        # the period grid regular even if every strategy missed the same bar.
        periods = pd.period_range(
            marks.index[0], marks.index[-1], freq=marks.index.freq
        )
        marks = marks.reindex(periods)
    marks = marks.ffill().loc[start:end]
    returns = marks.pct_change(fill_method=None).iloc[1:]
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Portfolio equity curves produced invalid returns")
    returns.attrs["periods_per_year"] = periods_per_year
    return returns, list(equity_by_label)
