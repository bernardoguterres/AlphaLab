from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from alphalab.api.routes import create_app


@pytest.mark.parametrize("training_entry", [False, True], ids=["flat", "training-buy"])
def test_greenblatt_walk_forward_warms_indicators_without_training_positions(
    training_entry,
):
    fold_size = 24 if training_entry else 16
    dates = pd.date_range("2024-01-05", periods=3 * fold_size, freq="W-FRI")
    close = np.full(len(dates), 100.0)
    if training_entry:
        # Trigger an earlier cross without triggering an exit before the
        # held-out window. The fold still needs its own flat starting state.
        close[12] = 110.0
    close[fold_size : fold_size + 2] = 110.0
    close[fold_size + 2 :] = 130.0
    bars = pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=dates,
    )
    fetcher = Mock()
    fetcher.fetch.return_value = {"data": bars}
    with patch("alphalab.api.routes.DataFetcher", return_value=fetcher):
        client = create_app().test_client()

    response = client.post(
        "/api/strategies/optimize",
        json={
            "ticker": "AAPL",
            "strategy": "greenblatt_weekly",
            "interval": "1wk",
            "start_date": dates[0].date().isoformat(),
            "end_date": dates[-1].date().isoformat(),
            "param_grid": {"fast_sma": [7], "slow_sma": [12]},
            "risk_settings": {"stop_loss_pct": 25.0, "take_profit_pct": 100.0},
            "drawdown_halt_enabled": False,
            "optimization_target": "total_return_pct",
            "walk_forward": True,
            "n_folds": 2,
        },
    )
    assert response.status_code == 200, response.get_json()
    fold = response.get_json()["data"]["all_results"][0]
    assert pd.Timestamp(fold["test_start"]) == dates[fold_size]
    assert pd.Timestamp(fold["test_end"]) == dates[2 * fold_size - 1]
    # The first test close crosses up, buys on the next open and marks at
    # 130. No signal or portfolio state from the training fold carries over.
    assert fold["avg_out_of_sample_score"] == pytest.approx(1.79505)
