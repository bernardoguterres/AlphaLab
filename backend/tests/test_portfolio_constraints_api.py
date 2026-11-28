import pandas as pd
import pytest

from alphalab.api.routes import create_app


def portfolio_request(assets, constraints, method="max_sharpe", backtest_ids=None):
    app = create_app()
    with app.test_client() as client:
        dates = pd.bdate_range("2024-01-02", periods=6)
        store = app.extensions["results_store"]
        for i, prices in enumerate(
            ([100, 102, 101, 104, 103, 105], [100, 101, 103, 102, 104, 108])
        ):
            store[str(i)] = {
                "results": {
                    "equity_curve": [
                        {"date": date.isoformat(), "value": value}
                        for date, value in zip(dates, prices)
                    ]
                }
            }
        store["empty"] = {"results": {"equity_curve": []}}
        return client.post(
            "/api/portfolio/optimize",
            json={
                "strategies": [
                    {
                        "backtest_id": backtest_ids[i] if backtest_ids else str(i),
                        "ticker": ticker,
                        "strategy": "ma_crossover",
                    }
                    for i, ticker in enumerate(assets)
                ],
                "method": method,
                "constraints": constraints,
            },
        )


def test_portfolio_rejects_infeasible_strategy_weight_cap():
    response = portfolio_request(
        ["SPY", "QQQ"], {"max_weight_per_strategy": 0.4}, method="equal_weight"
    )
    assert response.status_code == 400, response.json
    assert "fully invested" in response.json["message"]


@pytest.mark.parametrize("assets", [["SPY"], ["SPY", "QQQ"]])
def test_portfolio_defaults_remain_feasible_for_small_portfolios(assets):
    response = portfolio_request(assets, None)
    assert response.status_code == 200, response.json
    data = response.json["data"]
    assert data["optimal_weights"] == [1 / len(assets)] * len(assets)
    assert data["strategy_labels"] == [f"{asset}_ma_crossover" for asset in assets]
    assert len(data["efficient_frontier"]) == 1


def test_portfolio_preserves_distinct_runs_with_same_ticker_and_strategy():
    response = portfolio_request(
        ["SPY", "SPY"], {"max_weight_per_strategy": 1.0}, method="equal_weight"
    )
    assert response.status_code == 200, response.json
    data = response.json["data"]
    assert len(data["optimal_weights"]) == len(data["strategy_labels"]) == 2, data
    assert len(set(data["strategy_labels"])) == 2, data
    assert data["optimal_weights"] == [0.5, 0.5]


def test_portfolio_rejects_repeated_backtest_ids():
    response = portfolio_request(
        ["SPY", "SPY", "SPY"],
        {"max_weight_per_strategy": 0.4},
        method="equal_weight",
        backtest_ids=["0", "0", "0"],
    )
    assert response.status_code == 400, response.json
    assert "only once" in response.json["message"]


@pytest.mark.parametrize("unusable_id", ["missing", "empty"])
def test_portfolio_rejects_a_missing_or_empty_component(unusable_id):
    response = portfolio_request(
        ["SPY", "QQQ"], None, method="equal_weight", backtest_ids=["0", unusable_id]
    )
    assert response.status_code == 400, response.json
    assert unusable_id in response.json["message"]


def test_portfolio_rejects_unreachable_target():
    response = portfolio_request(
        ["SPY", "QQQ"],
        {"max_weight_per_strategy": 0.6, "target_return": 1.0},
        method="min_variance",
    )
    assert response.status_code == 400, response.json
    assert "outside the feasible range" in response.json["message"]


def test_portfolio_frontier_does_not_publish_fallback_points():
    response = portfolio_request(
        ["SPY", "QQQ"], {"max_weight_per_strategy": 0.6}, method="equal_weight"
    )
    assert response.status_code == 200, response.json
    frontier = response.json["data"]["efficient_frontier"]
    assert len(frontier) >= 2
    returns = [p["return"] for p in frontier]
    assert all(before < after for before, after in zip(returns, returns[1:])), returns
