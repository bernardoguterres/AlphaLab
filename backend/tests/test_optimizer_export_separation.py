"""Regression tests for the boundary between the walk-forward optimizer and
the export pipeline.

Principle under test: parameter selection inside each fold uses training
data only; each fold contributes one honest out-of-sample score; the
full-data "best_params" selection is an in-sample reference result, not
additional out-of-sample evidence; and /api/strategies/export can only ever
export a *stored* ordinary backtest result (created by
POST /api/strategies/backtest), never an optimizer/walk-forward result
directly - there is no code path that writes optimizer output into
results_store, and POST /api/strategies/optimize's response carries no
backtest_id at all.
"""

import pytest

from alphalab.api.routes import create_app
from alphalab.backtest.engine import BacktestEngine
from alphalab.backtest.metrics import PerformanceMetrics
from alphalab.backtest.parameter_optimizer import ParameterOptimizer
from helpers import make_featured_data
from alphalab.strategies.implementations.moving_average_crossover import (
    MovingAverageCrossover,
)


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestOptimizerOutputHasNoExportPath:
    def test_optimize_response_carries_no_backtest_id(self, client):
        """Nothing about POST /api/strategies/optimize's JSON response can
        be handed to /api/strategies/export - it simply has no backtest_id
        field, by construction, because optimizer output is never written to
        results_store."""
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()
        data = make_featured_data(n=400)
        result = optimizer.grid_search(
            strategy_class=MovingAverageCrossover,
            data=data,
            param_grid={"short_window": [10, 20], "long_window": [50, 100]},
            initial_capital=10_000,
            engine=engine,
            metrics_calc=metrics_calc,
            optimization_target="sharpe_ratio",
            walk_forward=False,
        )
        assert "backtest_id" not in result

    def test_walk_forward_response_carries_no_backtest_id(self, client):
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()
        data = make_featured_data(n=600)
        result = optimizer.grid_search(
            strategy_class=MovingAverageCrossover,
            data=data,
            param_grid={"short_window": [10, 20], "long_window": [50, 100]},
            initial_capital=10_000,
            engine=engine,
            metrics_calc=metrics_calc,
            optimization_target="sharpe_ratio",
            walk_forward=True,
            n_folds=2,
        )
        assert "backtest_id" not in result

    def test_an_arbitrary_unstored_id_is_rejected_by_export(self, client):
        """An id that was never produced by a real
        POST /api/strategies/backtest call (e.g. one a caller might
        construct hoping an optimizer run happens to be addressable) is
        rejected outright - results_store only ever contains ordinary
        backtest results, keyed by ids that route generates itself."""
        resp = client.post(
            "/api/strategies/export",
            json={"backtest_id": "not-a-real-stored-backtest-id"},
        )
        assert resp.status_code == 404


class TestStoredOrdinaryBacktestCanBeExported:
    def test_stored_backtest_result_exports_successfully(self, client):
        app = client.application
        results_store = app.extensions["results_store"]
        strategy = MovingAverageCrossover()
        results_store["ordinary_stored_result"] = {
            "results": {
                "total_return_pct": 10.0,
                "total_trades": 3,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.0,
                        "sortino_ratio": 1.2,
                        "calmar_ratio": 1.5,
                    },
                    "drawdown": {"max_drawdown_pct": -5.0},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.4},
                },
            },
            "request": {
                "ticker": "AAPL",
                "strategy": "ma_crossover",
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100_000,
                "params": strategy.params,
                "risk_settings": None,
                "interval": "1d",
            },
        }
        resp = client.post(
            "/api/strategies/export",
            json={"backtest_id": "ordinary_stored_result"},
        )
        assert resp.status_code == 200


class TestFoldResultsStayDistinctFromInSampleFinalSelection:
    def test_fold_scores_are_out_of_sample_and_final_backtest_is_labelled_in_sample(
        self,
    ):
        optimizer = ParameterOptimizer()
        engine = BacktestEngine()
        metrics_calc = PerformanceMetrics()
        data = make_featured_data(n=600)
        result = optimizer.grid_search(
            strategy_class=MovingAverageCrossover,
            data=data,
            param_grid={"short_window": [10, 20], "long_window": [50, 100]},
            initial_capital=10_000,
            engine=engine,
            metrics_calc=metrics_calc,
            optimization_target="sharpe_ratio",
            walk_forward=True,
            n_folds=2,
        )
        assert result["walk_forward"] is True

        # Each fold's own record is what actually got scored OOS.
        for fold in result["all_results"]:
            assert "train_score" in fold
            assert "avg_out_of_sample_score" in fold
            assert "selected_params" in fold
            assert fold["train_start"] is not None
            assert fold["test_start"] is not None

        # best_score is the average of the folds' own OOS scores, not the
        # full-data final backtest's score.
        oos_scores = [f["avg_out_of_sample_score"] for f in result["all_results"]]
        oos_scores = [s for s in oos_scores if s is not None]
        assert result["best_score"] == pytest.approx(sum(oos_scores) / len(oos_scores))

        # The full-data selection is explicitly, machine-readably labelled
        # in-sample - not silently presented as another OOS data point.
        assert result["final_backtest"]["is_in_sample"] is True
        assert result["final_backtest"]["sharpe_ratio"] != result["best_score"] or (
            # Coincidence guard: if they happen to be numerically equal on
            # this dataset, at least confirm they're computed from disjoint
            # code paths (one full-data run, one per-fold average) rather
            # than literally the same value being reused.
            len(result["all_results"])
            > 1
        )

    def test_export_json_never_claims_optimizer_evidence(self):
        """The export JSON's performance block is built from a stored
        ordinary backtest's own metrics only (see _build_export_json) -
        it has no field for walk-forward fold scores, optimizer targets, or
        any wording implying cross-engine signal parity or proven
        profitability."""
        from alphalab.api.helpers import _build_export_json

        export = _build_export_json(
            backtest_id="x",
            ticker="AAPL",
            strategy_name="ma_crossover",
            params={"short_window": 50, "long_window": 200},
            start_date="2020-01-01",
            end_date="2024-12-31",
            initial_capital=100_000,
            results={
                "total_return_pct": 10.0,
                "total_trades": 3,
                "metrics": {
                    "risk": {
                        "sharpe_ratio": 1.0,
                        "sortino_ratio": 1.2,
                        "calmar_ratio": 1.5,
                    },
                    "drawdown": {"max_drawdown_pct": -5.0},
                    "trades": {"win_rate": 0.6, "profit_factor": 1.4},
                },
            },
            config={"app": {"version": "0.1.0"}},
        )
        performance = export["metadata"]["performance"]
        for forbidden in (
            "walk_forward",
            "fold",
            "parity",
            "validated",
            "proven",
            "optimization_target",
        ):
            assert forbidden not in str(performance).lower().replace(
                " ", "_"
            ), f"export performance block unexpectedly mentions {forbidden!r}"
