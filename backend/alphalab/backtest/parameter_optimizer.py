"""Parameter optimization with walk-forward validation."""

import numpy as np
import pandas as pd
from itertools import product

from ..utils.logger import setup_logger

logger = setup_logger("alphalab.param_optimizer")


class ParameterOptimizer:
    """Optimize strategy parameters using grid search with optional walk-forward."""

    def grid_search(
        self,
        strategy_class,
        data: pd.DataFrame,
        param_grid: dict[str, list],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str = "sharpe_ratio",
        walk_forward: bool = False,
        n_folds: int = 5,
    ) -> dict:
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

        logger.info("Testing %d parameter combinations", len(all_combinations))

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
        param_names: list[str],
        combinations: list[tuple],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str,
    ) -> dict:
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
                    backtest_result.equity_curve, backtest_result.trades
                )

                # Extract target metric
                score = self._extract_metric(
                    metrics, backtest_result, optimization_target
                )

                results.append(
                    {
                        "params": params,
                        "score": score,
                        "total_return_pct": backtest_result.total_return_pct,
                        "sharpe_ratio": metrics["risk"]["sharpe_ratio"],
                        "max_drawdown_pct": metrics["drawdown"]["max_drawdown_pct"],
                        "total_trades": len(backtest_result.trades),
                    }
                )

            except Exception as e:
                logger.warning("Failed to test params %s: %s", params, e)
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

    def _is_better(self, score: float, best_score: float, target: str) -> bool:
        """Comparator matching _extract_metric's convention: lower is
        better for max_drawdown_pct (already returned as abs()), higher is
        better for everything else."""
        if target == "max_drawdown_pct":
            return score < best_score
        return score > best_score

    def _grid_search_best(
        self,
        strategy_class,
        data: pd.DataFrame,
        param_names: list[str],
        combinations: list[tuple],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str,
    ) -> dict | None:
        """Run every combination against `data` and return the single
        best-scoring one, or None if every combination failed.

        This is the one place "which parameter combination wins on a given
        dataset" is decided - used both for each walk-forward fold's
        train-only selection and for the final full-data parameter choice
        (see _walk_forward_optimize). It never touches held-out test data
        itself; the caller controls what `data` is, which is what keeps
        fold-level selection leakage-free.
        """
        best = None
        for combo in combinations:
            params = dict(zip(param_names, combo))
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
                score = self._score_fold_result(
                    result, metrics_calc, optimization_target
                )
            except Exception as e:
                logger.debug("Grid search failed for %s: %s", params, e)
                continue

            if best is None or self._is_better(
                score, best["score"], optimization_target
            ):
                best = {"params": params, "score": score}

        return best

    def _walk_forward_optimize(
        self,
        strategy_class,
        data: pd.DataFrame,
        param_names: list[str],
        combinations: list[tuple],
        initial_capital: float,
        engine,
        metrics_calc,
        optimization_target: str,
        n_folds: int,
    ) -> dict:
        """True walk-forward optimization (audit bug 3.3 fix, 2026-07-14).

        The previous implementation computed train_data per fold and never
        used it - every parameter combination was scored directly against
        every TEST fold, and best_params was whichever combo scored best on
        test data. That is grid search on the test set wearing a
        walk-forward label, and it overstates confidence in whatever
        parameters happen to fit the test windows well.

        Fixed methodology: for each fold, select the best-scoring
        combination using ONLY that fold's train_data
        (_grid_search_best), then evaluate ONLY that selected combination
        on the fold's held-out test_data to get the fold's honest
        out-of-sample score. Test-fold performance never influences which
        combination is chosen for that fold.

        Response shape change: `all_results` is now one entry PER FOLD, not
        per parameter combination. Each fold can legitimately select a
        different "best" combination (each fold trains on a different,
        progressively larger window), so there is no longer a single
        meaningful "this combo's average OOS score" table across folds -
        only each fold's own winner ever touches that fold's test data.
        `best_score` is the average of the folds' honest OOS scores (this
        number will typically look worse than the old leaky version - that
        is the fix working, not a regression).

        `best_params` (the one parameter set actually returned for the
        caller to apply) comes from a separate train-only selection over
        the ENTIRE dataset - this never touches any held-out test split, so
        it is not leakage, it's simply "what a train-only search recommends
        given everything available." `final_backtest` reports that choice's
        performance on the full dataset for reference only; it is an
        in-sample figure, not additional out-of-sample validation evidence.
        """
        folds = self._create_folds(data, n_folds)
        if not folds:
            raise ValueError("Not enough data to create walk-forward folds")

        fold_results = []
        for fold_idx, (train_data, test_data) in enumerate(folds):
            train_winner = self._grid_search_best(
                strategy_class,
                train_data,
                param_names,
                combinations,
                initial_capital,
                engine,
                metrics_calc,
                optimization_target,
            )
            if train_winner is None:
                logger.warning(
                    "Fold %d: no parameter combination succeeded on train_data",
                    fold_idx,
                )
                continue

            oos_score = None
            try:
                strategy = strategy_class(train_winner["params"])
                test_result = engine.run_backtest(
                    strategy=strategy,
                    data=test_data,
                    initial_capital=initial_capital,
                    start_date=None,
                    end_date=None,
                    position_sizing="equal_weight",
                    monte_carlo_runs=0,
                )
                oos_score = self._score_fold_result(
                    test_result, metrics_calc, optimization_target
                )
            except Exception as e:
                logger.debug(
                    "Fold %d: test evaluation failed for %s: %s",
                    fold_idx,
                    train_winner["params"],
                    e,
                )

            fold_results.append(
                {
                    "fold": fold_idx,
                    "train_start": (
                        str(train_data.index[0]) if len(train_data) else None
                    ),
                    "train_end": str(train_data.index[-1]) if len(train_data) else None,
                    "test_start": str(test_data.index[0]) if len(test_data) else None,
                    "test_end": str(test_data.index[-1]) if len(test_data) else None,
                    "selected_params": train_winner["params"],
                    "train_score": train_winner["score"],
                    "avg_out_of_sample_score": oos_score,
                }
            )

        valid_oos_scores = [
            f["avg_out_of_sample_score"]
            for f in fold_results
            if f["avg_out_of_sample_score"] is not None
        ]
        if not valid_oos_scores:
            raise ValueError("Walk-forward optimization failed for all folds")

        avg_oos_score = float(np.mean(valid_oos_scores))

        # Final params: train-only selection over the ENTIRE dataset - see
        # docstring above for why this is not leakage.
        full_data_winner = self._grid_search_best(
            strategy_class,
            data,
            param_names,
            combinations,
            initial_capital,
            engine,
            metrics_calc,
            optimization_target,
        )
        if full_data_winner is None:
            raise ValueError(
                "Walk-forward optimization failed to select final parameters"
            )
        best_params = full_data_winner["params"]

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
            final_result.equity_curve, final_result.trades
        )

        return {
            "best_params": best_params,
            "best_score": avg_oos_score,
            "all_results": fold_results,
            "optimization_target": optimization_target,
            "walk_forward": True,
            "n_folds": len(fold_results),
            "final_backtest": {
                "total_return_pct": final_result.total_return_pct,
                "sharpe_ratio": final_metrics["risk"]["sharpe_ratio"],
                "max_drawdown_pct": final_metrics["drawdown"]["max_drawdown_pct"],
            },
        }

    def _create_folds(
        self, data: pd.DataFrame, n_folds: int
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
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

    def _extract_metric(self, metrics: dict, backtest_result, target: str) -> float:
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

    def _score_fold_result(self, backtest_result, metrics_calc, target: str) -> float:
        """Score a single fold backtest result against the optimization target.

        Avoids calling calculate_all (5 metric groups) when the target is
        directly available on the backtest result object. calculate_all is
        called only when the target metric requires it.
        """
        if target == "total_return_pct":
            return backtest_result.total_return_pct
        metrics = metrics_calc.calculate_all(
            backtest_result.equity_curve, backtest_result.trades
        )
        return self._extract_metric(metrics, backtest_result, target)

    def generate_heatmap(
        self,
        strategy_class,
        data: pd.DataFrame,
        param1_name: str,
        param1_values: list[float],
        param2_name: str,
        param2_values: list[float],
        fixed_params: dict,
        initial_capital: float,
        engine,
        metrics_calc,
    ) -> dict:
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

                    metrics = metrics_calc.calculate_all(
                        result.equity_curve, result.trades
                    )
                    sharpe = metrics["risk"]["sharpe_ratio"]
                    row.append(float(sharpe))

                except Exception as e:
                    logger.debug(
                        "Heatmap cell failed at %s=%s, %s=%s: %s",
                        param1_name,
                        p1_val,
                        param2_name,
                        p2_val,
                        e,
                    )
                    row.append(None)

            heatmap_data.append(row)

        return {
            "param1_name": param1_name,
            "param1_values": param1_values,
            "param2_name": param2_name,
            "param2_values": param2_values,
            "heatmap_data": heatmap_data,
        }
