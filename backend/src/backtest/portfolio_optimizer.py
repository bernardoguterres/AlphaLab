"""Portfolio optimization using Modern Portfolio Theory."""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import List, Dict, Tuple, Optional

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.portfolio_optimizer")


class PortfolioOptimizer:
    """Optimize portfolio weights across multiple strategies."""

    def __init__(self, returns_matrix: pd.DataFrame, risk_free_rate: float = 0.04):
        """Initialize optimizer.

        Args:
            returns_matrix: DataFrame with daily returns for each strategy (columns = strategies)
            risk_free_rate: Annual risk-free rate (default 4%)
        """
        self.returns = returns_matrix
        self.mean_returns = returns_matrix.mean() * 252  # Annualized
        self.cov_matrix = returns_matrix.cov() * 252  # Annualized
        self.risk_free_rate = risk_free_rate
        self.n_strategies = len(returns_matrix.columns)

    def optimize(
        self,
        method: str,
        max_weight: float = 0.4,
        min_weight: float = 0.05,
        target_return: Optional[float] = None,
    ) -> Dict:
        """Optimize portfolio weights.

        Args:
            method: Optimization method (max_sharpe, min_variance, equal_weight, risk_parity)
            max_weight: Maximum weight per strategy (0-1)
            min_weight: Minimum weight per strategy (0-1)
            target_return: Target annual return (only used for min_variance with target)

        Returns:
            Dict with optimal_weights, expected_return, expected_risk, sharpe_ratio
        """
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
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_std if portfolio_std > 0 else 0

        return {
            "optimal_weights": weights.tolist(),
            "expected_return": float(portfolio_return),
            "expected_risk": float(portfolio_std),
            "sharpe_ratio": float(sharpe_ratio),
        }

    def efficient_frontier(
        self,
        n_points: int = 20,
        max_weight: float = 0.4,
        min_weight: float = 0.05,
    ) -> List[Dict]:
        """Calculate efficient frontier points.

        Args:
            n_points: Number of points to calculate
            max_weight: Maximum weight per strategy
            min_weight: Minimum weight per strategy

        Returns:
            List of dicts with return, risk, sharpe_ratio for each point
        """
        min_return = self.mean_returns.min()
        max_return = self.mean_returns.max()
        target_returns = np.linspace(min_return, max_return, n_points)

        frontier_points = []
        for target_return in target_returns:
            try:
                weights = self._min_variance(max_weight, min_weight, target_return)
                portfolio_return = np.dot(weights, self.mean_returns)
                portfolio_std = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
                sharpe = (portfolio_return - self.risk_free_rate) / portfolio_std if portfolio_std > 0 else 0

                frontier_points.append({
                    "return": float(portfolio_return),
                    "risk": float(portfolio_std),
                    "sharpe_ratio": float(sharpe),
                })
            except Exception as e:
                logger.debug(f"Skipping frontier point at return {target_return}: {e}")
                continue

        return frontier_points

    def _equal_weight(self) -> np.ndarray:
        """Equal weight allocation (1/N)."""
        return np.ones(self.n_strategies) / self.n_strategies

    def _max_sharpe(self, max_weight: float, min_weight: float) -> np.ndarray:
        """Maximize Sharpe ratio."""
        def neg_sharpe(weights):
            port_return = np.dot(weights, self.mean_returns)
            port_std = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            sharpe = (port_return - self.risk_free_rate) / port_std if port_std > 0 else 0
            return -sharpe  # Negative because we minimize

        return self._optimize_weights(neg_sharpe, max_weight, min_weight)

    def _min_variance(
        self,
        max_weight: float,
        min_weight: float,
        target_return: Optional[float] = None,
    ) -> np.ndarray:
        """Minimize portfolio variance."""
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(self.cov_matrix, weights))

        constraints = []
        if target_return is not None:
            # Add return constraint
            constraints.append({
                'type': 'eq',
                'fun': lambda w: np.dot(w, self.mean_returns) - target_return
            })

        return self._optimize_weights(portfolio_variance, max_weight, min_weight, constraints)

    def _risk_parity(self, max_weight: float, min_weight: float) -> np.ndarray:
        """Equal risk contribution from each strategy."""
        def risk_parity_objective(weights):
            # Calculate marginal risk contribution
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            marginal_contrib = np.dot(self.cov_matrix, weights) / portfolio_std if portfolio_std > 0 else np.zeros_like(weights)
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
        extra_constraints: Optional[List] = None,
    ) -> np.ndarray:
        """Generic weight optimization with constraints."""
        # Initial guess: equal weights
        x0 = np.ones(self.n_strategies) / self.n_strategies

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Weights sum to 1
        ]
        if extra_constraints:
            constraints.extend(extra_constraints)

        # Bounds: each weight between min_weight and max_weight
        bounds = tuple((min_weight, max_weight) for _ in range(self.n_strategies))

        # Optimize
        result = minimize(
            objective_func,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
            # Return equal weights as fallback
            return self._equal_weight()

        return result.x


def extract_daily_returns(equity_curve: List[Dict[str, any]]) -> pd.Series:
    """Extract daily returns from equity curve.

    Args:
        equity_curve: List of dicts with 'date' and 'value' keys

    Returns:
        Series of daily returns (percentage)
    """
    df = pd.DataFrame(equity_curve)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()

    # Calculate daily returns
    returns = df['value'].pct_change().dropna()
    return returns


def build_returns_matrix(
    strategies: List[Dict],
    backtest_results: Dict[str, Dict],
) -> Tuple[pd.DataFrame, List[str]]:
    """Build returns matrix from multiple backtest results.

    Args:
        strategies: List of dicts with backtest_id, ticker, strategy
        backtest_results: Dict mapping backtest_id to backtest result dict

    Returns:
        Tuple of (returns_matrix DataFrame, strategy_labels list)
    """
    returns_dict = {}
    labels = []

    for strat_info in strategies:
        backtest_id = strat_info['backtest_id']
        ticker = strat_info.get('ticker', 'Unknown')
        strategy_name = strat_info.get('strategy', 'Unknown')

        if backtest_id not in backtest_results:
            logger.warning(f"Backtest {backtest_id} not found, skipping")
            continue

        result = backtest_results[backtest_id]
        equity_curve = result.get('equity_curve', [])

        if not equity_curve:
            logger.warning(f"No equity curve for {backtest_id}, skipping")
            continue

        # Extract daily returns
        returns = extract_daily_returns(equity_curve)

        label = f"{ticker}_{strategy_name}"
        returns_dict[label] = returns
        labels.append(label)

    if not returns_dict:
        raise ValueError("No valid backtest results found")

    # Combine into DataFrame (align dates)
    returns_df = pd.DataFrame(returns_dict)
    returns_df = returns_df.fillna(0)  # Fill missing dates with 0 return

    return returns_df, labels
