"""Parameter optimization with walk-forward validation."""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from itertools import product

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.param_optimizer")


class ParameterOptimizer:
    """Optimize strategy parameters using grid search with optional walk-forward."""

    def __init__(self):
        self.logger = logger

    def grid_search(
        self,
        strategy_class,
        data: pd.DataFrame,
        param_grid: Dict[str, List],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str = "sharpe_ratio",
        walk_forward: bool = False,
        n_folds: int = 5,
    ) -> Dict:
        """Run parameter grid search.

        Args:
            strategy_class: Strategy class to optimize
            data: Feature-engineered DataFrame
            param_grid: Dict of param_name -> list of values to try
            initial_capital: Starting capital
            engine: BacktestEngine instance
            metrics_calc: PerformanceMetrics instance
            optimization_target: Metric to optimize (sharpe_ratio, total_return_pct, etc.)
            walk_forward: Use walk-forward validation
            n_folds: Number of folds for walk-forward

        Returns:
            Dict with best_params, best_score, all_results, walk_forward_results (if enabled)
        """
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        all_combinations = list(product(*param_values))

        self.logger.info(f"Testing {len(all_combinations)} parameter combinations")

        if walk_forward:
            return self._walk_forward_optimize(
                strategy_class,
                data,
                param_names,
                all_combinations,
                initial_capital,
                engine,
                metrics_calc,
                optimization_target,
                n_folds,
            )
        else:
            return self._simple_optimize(
                strategy_class,
                data,
                param_names,
                all_combinations,
                initial_capital,
                engine,
                metrics_calc,
                optimization_target,
            )

    def _simple_optimize(
        self,
        strategy_class,
        data: pd.DataFrame,
        param_names: List[str],
        combinations: List[Tuple],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str,
    ) -> Dict:
        """Simple grid search without walk-forward."""
        results = []

        for combo in combinations:
            params = dict(zip(param_names, combo))

            try:
                strategy = strategy_class(params)
                backtest_result = engine.run_backtest(
                    strategy=strategy,
                    data=data,
                    initial_capital=initial_capital,
                    start_date=None,
                    end_date=None,
                    position_sizing="equal_weight",
                    monte_carlo_runs=0,
                )

                metrics = metrics_calc.calculate_all(
                    backtest_result.equity_curve,
                    backtest_result.trades
                )

                # Extract target metric
                score = self._extract_metric(metrics, backtest_result, optimization_target)

                results.append({
                    "params": params,
                    "score": score,
                    "total_return_pct": backtest_result.total_return_pct,
                    "sharpe_ratio": metrics["risk"]["sharpe_ratio"],
                    "max_drawdown_pct": metrics["drawdown"]["max_drawdown_pct"],
                    "total_trades": len(backtest_result.trades),
                })

            except Exception as e:
                self.logger.warning(f"Failed to test params {params}: {e}")
                continue

        if not results:
            raise ValueError("No valid parameter combinations found")

        # Sort by score (descending for most metrics, ascending for drawdown)
        reverse = optimization_target != "max_drawdown_pct"
        results.sort(key=lambda x: x["score"], reverse=reverse)

        return {
            "best_params": results[0]["params"],
            "best_score": results[0]["score"],
            "all_results": results,
            "optimization_target": optimization_target,
            "walk_forward": False,
        }

    def _walk_forward_optimize(
        self,
        strategy_class,
        data: pd.DataFrame,
        param_names: List[str],
        combinations: List[Tuple],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str,
        n_folds: int,
    ) -> Dict:
        """Walk-forward optimization to prevent overfitting."""
        # Create time-based folds
        folds = self._create_folds(data, n_folds)

        # For each parameter combination, test on all folds
        combination_scores = []

        for combo in combinations:
            params = dict(zip(param_names, combo))
            fold_scores = []

            for fold_idx, (train_data, test_data) in enumerate(folds):
                try:
                    # Optimize on training data
                    strategy = strategy_class(params)

                    # Test on out-of-sample data
                    test_result = engine.run_backtest(
                        strategy=strategy,
                        data=test_data,
                        initial_capital=initial_capital,
                        start_date=None,
                        end_date=None,
                        position_sizing="equal_weight",
                        monte_carlo_runs=0,
                    )

                    test_metrics = metrics_calc.calculate_all(
                        test_result.equity_curve,
                        test_result.trades
                    )

                    score = self._extract_metric(test_metrics, test_result, optimization_target)
                    fold_scores.append(score)

                except Exception as e:
                    self.logger.debug(f"Fold {fold_idx} failed for {params}: {e}")
                    fold_scores.append(float('-inf'))

            # Average out-of-sample score
            avg_score = np.mean([s for s in fold_scores if s != float('-inf')])

            combination_scores.append({
                "params": params,
                "avg_out_of_sample_score": avg_score,
                "fold_scores": fold_scores,
            })

        if not combination_scores:
            raise ValueError("Walk-forward optimization failed for all parameters")

        # Sort by average out-of-sample score
        reverse = optimization_target != "max_drawdown_pct"
        combination_scores.sort(key=lambda x: x["avg_out_of_sample_score"], reverse=reverse)

        best_params = combination_scores[0]["params"]

        # Run final backtest on full data with best params
        strategy = strategy_class(best_params)
        final_result = engine.run_backtest(
            strategy=strategy,
            data=data,
            initial_capital=initial_capital,
            start_date=None,
            end_date=None,
            position_sizing="equal_weight",
            monte_carlo_runs=0,
        )

        final_metrics = metrics_calc.calculate_all(
            final_result.equity_curve,
            final_result.trades
        )

        return {
            "best_params": best_params,
            "best_score": combination_scores[0]["avg_out_of_sample_score"],
            "all_results": combination_scores,
            "optimization_target": optimization_target,
            "walk_forward": True,
            "n_folds": n_folds,
            "final_backtest": {
                "total_return_pct": final_result.total_return_pct,
                "sharpe_ratio": final_metrics["risk"]["sharpe_ratio"],
                "max_drawdown_pct": final_metrics["drawdown"]["max_drawdown_pct"],
            },
        }

    def _create_folds(self, data: pd.DataFrame, n_folds: int) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """Create time-based train/test folds.

        Each fold uses progressively more data for training and tests on the next segment.
        """
        n = len(data)
        fold_size = n // (n_folds + 1)  # Leave room for final test segment

        folds = []
        for i in range(n_folds):
            train_end = fold_size * (i + 1)
            test_start = train_end
            test_end = train_end + fold_size

            train_data = data.iloc[:train_end]
            test_data = data.iloc[test_start:test_end]

            if len(test_data) > 0:
                folds.append((train_data, test_data))

        return folds

    def _extract_metric(self, metrics: Dict, backtest_result, target: str) -> float:
        """Extract target metric from results."""
        if target == "total_return_pct":
            return backtest_result.total_return_pct
        elif target == "sharpe_ratio":
            return metrics["risk"]["sharpe_ratio"]
        elif target == "max_drawdown_pct":
            return abs(metrics["drawdown"]["max_drawdown_pct"])  # Lower is better
        elif target == "win_rate":
            return metrics["trades"]["win_rate"]
        else:
            return metrics["risk"]["sharpe_ratio"]  # Default to Sharpe

    def generate_heatmap(
        self,
        strategy_class,
        data: pd.DataFrame,
        param1_name: str,
        param1_values: List[float],
        param2_name: str,
        param2_values: List[float],
        fixed_params: Dict,
        initial_capital: float,
        engine,
        metrics_calc,
    ) -> Dict:
        """Generate 2D heatmap data for parameter visualization.

        Args:
            strategy_class: Strategy class
            data: Feature-engineered data
            param1_name: First parameter name (X-axis)
            param1_values: Values for param1
            param2_name: Second parameter name (Y-axis)
            param2_values: Values for param2
            fixed_params: Other parameters to keep fixed
            initial_capital: Starting capital
            engine: BacktestEngine
            metrics_calc: PerformanceMetrics

        Returns:
            Dict with heatmap data (2D array of Sharpe ratios)
        """
        heatmap_data = []

        for p2_val in param2_values:
            row = []
            for p1_val in param1_values:
                params = {**fixed_params, param1_name: p1_val, param2_name: p2_val}

                try:
                    strategy = strategy_class(params)
                    result = engine.run_backtest(
                        strategy=strategy,
                        data=data,
                        initial_capital=initial_capital,
                        start_date=None,
                        end_date=None,
                        position_sizing="equal_weight",
                        monte_carlo_runs=0,
                    )

                    metrics = metrics_calc.calculate_all(result.equity_curve, result.trades)
                    sharpe = metrics["risk"]["sharpe_ratio"]
                    row.append(float(sharpe))

                except Exception as e:
                    self.logger.debug(f"Heatmap cell failed at {param1_name}={p1_val}, {param2_name}={p2_val}: {e}")
                    row.append(None)

            heatmap_data.append(row)

        return {
            "param1_name": param1_name,
            "param1_values": param1_values,
            "param2_name": param2_name,
            "param2_values": param2_values,
            "heatmap_data": heatmap_data,
        }
