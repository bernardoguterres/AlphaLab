"""Complete the evidence checklist (STRATEGY_RESEARCH_PLAN.md section I) for
the faithful Greenblatt portfolio result (EXP-2026-07-12-M02).

Adds the two pieces that were explicitly missing from M01/M02's verdicts:
  1. Deflated Sharpe Ratio (deflated_sharpe.py) against the locked N=6 trial
     roster, using the REAL PortfolioConstructor order-level backtest's
     actual weekly returns (skewness/kurtosis-aware, not just raw Sharpe).
  2. Faber 10-month-SMA overlay on SPY (faber_overlay.py) as the second
     required benchmark, alongside SPY buy-and-hold (already computed in
     M01/M02).

Does NOT re-run the backtest with different parameters (that would open a
new experiment, not complete this one) - reuses the exact same
PortfolioConstructor call as scripts/greenblatt_portfolio_backtest.py.

Usage:
    cd AlphaLab/backend && source venv/bin/activate && cd ..
    python scripts/greenblatt_evidence_checklist.py
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from wf_common import setup_backend_path, fmt

setup_backend_path()

import pandas as pd
import yfinance as yf

from src.screener.fundamental_screener import FundamentalScreener
from src.backtest.portfolio_constructor import PortfolioConstructor
from src.backtest.metrics import PerformanceMetrics
from src.backtest.deflated_sharpe import deflated_sharpe_ratio
from src.backtest.faber_overlay import faber_overlay_returns

UNIVERSE = [
    "MSFT", "AAPL", "GOOGL", "AMZN", "META", "NVDA", "JPM", "JNJ",
    "V", "MA", "UNH", "HD", "MCD", "KO", "PEP", "WMT", "BAC",
    "XOM", "CVX", "LLY", "ABBV", "TMO", "BRK-B",
]
TOP_N = 6
REBALANCE_WEEKS = 52
N_TRIALS = 6  # locked roster, EXPERIMENT_REGISTRY_SCHEMA.md

WINDOWS = [
    {"label": "Window 1", "start": "2018-01-01", "end": "2020-12-31"},
    {"label": "Window 2", "start": "2021-01-01", "end": "2024-12-31"},
]


def fetch_weekly_close(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    raw = yf.download(ticker, start=start, end=end, interval="1wk", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw[["Close"]].dropna()
    return close if len(close) >= 10 else None


def fetch_monthly_close(ticker: str, start: str, end: str, warmup_months: int = 12) -> pd.Series | None:
    """Fetch monthly close with extra warmup lookback for the 10-month SMA."""
    warmup_start = (pd.Timestamp(start) - pd.DateOffset(months=warmup_months)).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=warmup_start, end=end, interval="1mo", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    return raw["Close"].dropna()


def main():
    print("=" * 80)
    print("  Evidence checklist completion: Greenblatt faithful portfolio (EXP-2026-07-12-M02)")
    print("=" * 80)

    screener = FundamentalScreener(universe=UNIVERSE, min_market_cap_b=10.0, max_debt_to_equity=2.0, request_delay=0.4)
    candidates = screener.screen(top_n=TOP_N)
    print(f"\nCandidates: {[c.ticker for c in candidates]}\n")

    results = {}

    for window in WINDOWS:
        label = window["label"]
        print(f"[{label}] {window['start']} -> {window['end']}")

        price_data = {}
        for c in candidates:
            df = fetch_weekly_close(c.ticker, window["start"], window["end"])
            if df is not None:
                price_data[c.ticker] = df

        pc = PortfolioConstructor(top_n=TOP_N, rebalance_period_bars=REBALANCE_WEEKS)
        result = pc.run(candidates, price_data)

        calc = PerformanceMetrics(risk_free_rate=0.04)
        metrics = calc.calculate_all(equity_curve=result.equity_curve, trades=result.final_portfolio.ledger)
        ret = metrics["returns"]
        risk = metrics["risk"]

        n_obs = len(result.equity_curve)
        sharpe = risk["sharpe_ratio"]
        skew = ret["skewness"]
        kurtosis_pearson = ret["kurtosis"] + 3.0  # pandas .kurt() is EXCESS kurtosis

        dsr = deflated_sharpe_ratio(
            sharpe_annualized=sharpe,
            skewness=skew,
            kurtosis_pearson=kurtosis_pearson,
            n_observations=n_obs,
            n_trials=N_TRIALS,
            periods_per_year=52,
        )

        print(f"    Portfolio: CAGR={fmt(ret['cagr_pct'], '.1f')}%  Sharpe={fmt(sharpe, '.3f')}  "
              f"Skew={fmt(skew, '.2f')}  Kurtosis(Pearson)={fmt(kurtosis_pearson, '.2f')}  N={n_obs}")
        print(f"    Deflated Sharpe Ratio: {dsr.deflated_sharpe_ratio:.4f} "
              f"(SR_0={dsr.expected_max_sharpe_under_null_annualized:.3f} annualized, "
              f"N_trials={N_TRIALS}) -> {'SIGNIFICANT (>0.95)' if dsr.significant_at_95pct else 'not significant at 95%'}")

        # Faber 10-month SMA overlay on SPY, same window
        spy_monthly = fetch_monthly_close("SPY", window["start"], window["end"])
        faber_metrics = None
        if spy_monthly is not None:
            overlay_rets = faber_overlay_returns(spy_monthly, sma_months=10).dropna()
            overlay_rets_in_window = overlay_rets[overlay_rets.index >= pd.Timestamp(window["start"])]
            if len(overlay_rets_in_window) > 1:
                equity = (1 + overlay_rets_in_window).cumprod()
                years = len(overlay_rets_in_window) / 12.0
                cagr = (equity.iloc[-1] ** (1 / years) - 1) * 100 if years > 0 else None
                ann_ret = overlay_rets_in_window.mean() * 12
                ann_vol = overlay_rets_in_window.std() * (12 ** 0.5)
                faber_sharpe = (ann_ret - 0.04) / ann_vol if ann_vol > 0 else None
                faber_metrics = {"cagr_pct": round(cagr, 2), "sharpe": round(faber_sharpe, 3), "n_obs": len(overlay_rets_in_window)}
                print(f"    Faber 10mo-SMA overlay (SPY): CAGR={fmt(faber_metrics['cagr_pct'], '.1f')}%  "
                      f"Sharpe={fmt(faber_metrics['sharpe'], '.3f')}  N={faber_metrics['n_obs']} monthly obs")

        beats_faber = (
            faber_metrics is not None
            and faber_metrics["sharpe"] is not None
            and sharpe > faber_metrics["sharpe"]
        )
        print(f"    Beats Faber overlay (risk-adjusted): {beats_faber}\n")

        results[label] = {
            "cagr_pct": ret["cagr_pct"],
            "sharpe": sharpe,
            "skewness": skew,
            "kurtosis_pearson": kurtosis_pearson,
            "n_obs": n_obs,
            "deflated_sharpe_ratio": dsr.deflated_sharpe_ratio,
            "sr_0_annualized": dsr.expected_max_sharpe_under_null_annualized,
            "significant_at_95pct": dsr.significant_at_95pct,
            "faber_overlay_spy": faber_metrics,
            "beats_faber_overlay": beats_faber,
        }

    out_path = "scripts/greenblatt_evidence_checklist_result.json"
    with open(out_path, "w") as f:
        json.dump({"run_date": datetime.now().strftime("%Y-%m-%d"), "n_trials": N_TRIALS, "windows": results}, f, indent=2, default=str)
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
