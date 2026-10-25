#!/usr/bin/env python3
"""Generate AlphaLab-oracle signal fixtures for AlphaLive's parity test.

AlphaLab is the independent oracle: this runs AlphaLab's REAL
FeatureEngineer + strategy classes over AlphaLive's fixed OHLCV fixtures
(tests/fixtures/{spy,msft}_fixture_500bars.csv in the AlphaLive repo) and
writes, into that fixtures directory:

  expected_signals_{TICKER}_{strategy}.csv   bar_index,timestamp,signal
  signal_parity_manifest.json                per strategy: the AlphaLab
                                             parameters used AND the
                                             AlphaLive parameters the export
                                             contract translates them to
                                             (alphalab.api.helpers.
                                             _translate_params_for_export)

AlphaLive's tests/test_multi_ticker_parity.py loads the manifest's
`alphalive_params` - exactly what an exported config would carry - so the
two engines are compared on identical inputs and exported parameters.
AlphaLive output is never used to produce these files.

Signals are the strategy's own decisions at each bar's close (the backtest
engine then fills at the next bar's open - an execution convention both
engines share and which is not part of this comparison).

Usage (from the AlphaLab repo root):
    backend/venv/bin/python scripts/generate_signal_parity_fixtures.py \
        --fixtures ../AlphaLive/tests/fixtures
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from alphalab.api.blueprints.backtest import STRATEGY_MAP  # noqa: E402
from alphalab.api.helpers import (  # noqa: E402
    _build_export_json,
    _translate_params_for_export,
)
from alphalab.utils.config import load_config  # noqa: E402
from strategy_schema import StrategyExportSchema  # noqa: E402
from alphalab.data.processor import FeatureEngineer  # noqa: E402

# AlphaLab-side parameters per parity case. Non-default values are used
# where a strategy has parameters the old parity test never exercised, so a
# parameter that is accepted but ignored cannot pass vacuously.
CASES = {
    "ma_crossover": {"short_window": 20, "long_window": 50},
    "rsi_mean_reversion": {"rsi_period": 14, "oversold": 30, "overbought": 70},
    "momentum_breakout": {
        "lookback": 20,
        "volume_surge_pct": 130,
        "rsi_min": 55,
        "stop_loss_atr_mult": 2.0,
        "trailing_stop_atr_mult": 2.5,
        "cooldown_days": 3,
    },
    "bollinger_breakout": {
        "bb_period": 20,
        "bb_std_dev": 2.0,
        "confirmation_bars": 1,
        "volume_filter": True,
        "volume_threshold": 1.2,
        "cooldown_days": 2,
    },
    "bollinger_rsi_combo": {
        "bb_period": 18,
        "bb_std": 2.2,
        "rsi_period": 10,
        "rsi_oversold": 40,
        "rsi_overbought": 60,
    },
    "trend_adaptive_rsi": {"rsi_period": 10, "trend_sma": 20, "trend_lookback": 3},
    "vwap_reversion": {
        "vwap_period": 15,
        "deviation_threshold": 1.8,
        "rsi_period": 10,
        "cooldown_days": 2,
    },
}
TICKERS = ["SPY", "MSFT"]


def _git_rev() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(BACKEND.parent), "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fixtures", required=True, help="AlphaLive tests/fixtures directory"
    )
    out = Path(ap.parse_args().fixtures)

    manifest = {
        "generated_by": "AlphaLab scripts/generate_signal_parity_fixtures.py",
        "alphalab_commit": _git_rev() + " (+ uncommitted working tree)",
        "signal_convention": "decision at bar close; fills at next open are not compared",
        "strategies": {},
    }
    for name, overrides in CASES.items():
        strat = STRATEGY_MAP[name](dict(overrides))
        lab_params = dict(strat.params)  # defaults filled in by validate_params
        # The exact API export path: build -> StrategyExportSchema validate ->
        # dump. The AlphaLive side gets precisely what an exported file carries.
        if name == "vwap_reversion":
            # Not exportable on daily bars (the export schema requires an
            # intraday timeframe); compared as a research strategy using the
            # export-contract name mapping only.
            live_params = _translate_params_for_export(name, dict(lab_params))
            exportable = False
        else:
            export = _build_export_json(
                "parity",
                "SPY",
                name,
                dict(lab_params),
                "2022-01-01",
                "2023-12-31",
                100_000.0,
                {"metrics": {}},
                load_config(),
                interval="1wk" if name == "greenblatt_weekly" else "1d",
            )
            export = StrategyExportSchema.model_validate(export).model_dump(
                mode="json", exclude_none=True
            )
            live_params = export["strategy"]["parameters"]
            exportable = True
        manifest["strategies"][name] = {
            "alphalab_params": lab_params,
            "alphalive_params": live_params,
            "exportable_daily": exportable,
        }
        for ticker in TICKERS:
            raw = pd.read_csv(out / f"{ticker.lower()}_fixture_500bars.csv")
            raw.columns = [c.capitalize() for c in raw.columns]
            raw = raw.set_index(pd.to_datetime(raw.pop("Timestamp")))
            featured = FeatureEngineer().process(
                raw[["Open", "High", "Low", "Close", "Volume"]]
            )
            sig = STRATEGY_MAP[name](dict(overrides)).generate_signals(featured)[
                "signal"
            ]
            rows = pd.DataFrame(
                {
                    "bar_index": range(len(sig)),
                    "timestamp": [str(t.date()) for t in sig.index],
                    "signal": [{1: "BUY", -1: "SELL"}.get(int(v), "HOLD") for v in sig],
                }
            )
            rows.to_csv(out / f"expected_signals_{ticker}_{name}.csv", index=False)
            print(f"{ticker} {name}: {int((sig != 0).sum())} decisions")
    (out / "signal_parity_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"wrote manifest for {len(CASES)} strategies")


if __name__ == "__main__":
    main()
