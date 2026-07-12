"""Sector rotation strategy: Levy (1967) relative strength on the 11 SPDR
sector ETFs, using PortfolioConstructor's dynamic rank_fn mode (added
2026-07-12 specifically for this - see portfolio_constructor.py docstring).

Shortlist item 2, docs/STRATEGY_RESEARCH_PLAN.md section C. Price-only, no
point-in-time fundamentals problem (unlike Greenblatt) - genuinely re-ranks
the sector universe at every rebalance using only trailing data.

Signal: rank sectors by price / 26-week trailing SMA (Levy's original
ratio), hold the top N, equal-weight, rebalance ~monthly (every 4 weeks on
weekly bars - practitioner sector-rotation convention per the research doc).

Usage:
    cd AlphaLab/backend && source venv/bin/activate && cd ..
    python scripts/sector_rotation_backtest.py
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

from src.screener.relative_strength_ranker import RelativeStrengthRanker, SPDR_SECTOR_ETFS
from src.backtest.portfolio_constructor import PortfolioConstructor
from src.backtest.metrics import PerformanceMetrics
from src.backtest.deflated_sharpe import deflated_sharpe_ratio
from src.backtest.faber_overlay import faber_overlay_returns

TOP_N = 4
REBALANCE_WEEKS = 4  # ~monthly on weekly bars
SMA_WEEKS = 26
N_TRIALS = 6  # locked roster - this is trial #2 (sector rotation)

WINDOWS = [
    {"label": "Window 1", "start": "2018-07-01", "end": "2020-12-31"},  # after XLC inception
    {"label": "Window 2", "start": "2021-01-01", "end": "2024-12-31"},
]

WARMUP_WEEKS = SMA_WEEKS + 5  # extra weekly bars of lookback so the SMA is warm at window start


def fetch_weekly_close(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    warmup_start = (pd.Timestamp(start) - pd.Timedelta(weeks=WARMUP_WEEKS)).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=warmup_start, end=end, interval="1wk", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    close = raw[["Close"]].dropna()
    return close if len(close) >= SMA_WEEKS else None


def fetch_monthly_close(ticker: str, start: str, end: str, warmup_months: int = 12) -> pd.Series | None:
    warmup_start = (pd.Timestamp(start) - pd.DateOffset(months=warmup_months)).strftime("%Y-%m-%d")
    raw = yf.download(ticker, start=warmup_start, end=end, interval="1mo", auto_adjust=True, progress=False)
    if raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    return raw["Close"].dropna()


def main():
    print("=" * 80)
    print("  AlphaLab - Sector Rotation (Levy 1967 relative strength, dynamic re-ranking)")
    print(f"  Universe: {len(SPDR_SECTOR_ETFS)} SPDR sector ETFs, Top N: {TOP_N}, "
          f"Rebalance: every {REBALANCE_WEEKS}w, SMA: {SMA_WEEKS}w")
    print("=" * 80)

    ranker = RelativeStrengthRanker(sma_weeks=SMA_WEEKS)
    results = {}

    for window in WINDOWS:
        label = window["label"]
        print(f"\n[{label}] {window['start']} -> {window['end']}")

        price_data = {}
        for t in SPDR_SECTOR_ETFS:
            df = fetch_weekly_close(t, window["start"], window["end"])
            if df is not None:
                price_data[t] = df
            else:
                print(f"    SKIP {t}: no usable weekly data in window (likely pre-inception)")

        # Trim to the actual window (warmup data stays available to rank_fn
        # via its own trailing slice, but the backtest LOOP should only
        # visit bars inside the requested window).
        window_start_ts = pd.Timestamp(window["start"])

        pc = PortfolioConstructor(top_n=TOP_N, rebalance_period_bars=REBALANCE_WEEKS)
        result = pc.run(price_data=price_data, rank_fn=ranker.rank)

        # Restrict equity curve to the requested window (drop warmup bars).
        in_window_curve = [p for p in result.equity_curve if p["date"] >= window_start_ts]
        calc = PerformanceMetrics(risk_free_rate=0.04)
        metrics = calc.calculate_all(equity_curve=in_window_curve, trades=result.final_portfolio.ledger)
        ret, risk = metrics["returns"], metrics["risk"]

        n_obs = len(in_window_curve)
        sharpe = risk.get("sharpe_ratio", 0.0) or 0.0
        skew = ret.get("skewness", 0.0) or 0.0
        kurtosis_pearson = (ret.get("kurtosis", 0.0) or 0.0) + 3.0

        dsr = None
        if n_obs >= 2:
            dsr = deflated_sharpe_ratio(
                sharpe_annualized=sharpe, skewness=skew, kurtosis_pearson=kurtosis_pearson,
                n_observations=n_obs, n_trials=N_TRIALS, periods_per_year=52,
            )

        print(f"    Portfolio: CAGR={fmt(ret.get('cagr_pct'), '.1f')}%  Sharpe={fmt(sharpe, '.3f')}  "
              f"N={n_obs} weekly obs, {len(result.tickers_used)} distinct sectors held over the window")
        if dsr:
            print(f"    Deflated Sharpe Ratio: {dsr.deflated_sharpe_ratio:.4f} -> "
                  f"{'SIGNIFICANT (>0.95)' if dsr.significant_at_95pct else 'not significant at 95%'}")

        spy_monthly = fetch_monthly_close("SPY", window["start"], window["end"])
        faber_metrics = None
        if spy_monthly is not None:
            overlay_rets = faber_overlay_returns(spy_monthly, sma_months=10).dropna()
            overlay_in_window = overlay_rets[overlay_rets.index >= window_start_ts]
            if len(overlay_in_window) > 1:
                equity = (1 + overlay_in_window).cumprod()
                years = len(overlay_in_window) / 12.0
                cagr = (equity.iloc[-1] ** (1 / years) - 1) * 100 if years > 0 else None
                ann_vol = overlay_in_window.std() * (12 ** 0.5)
                ann_ret = overlay_in_window.mean() * 12
                faber_sharpe = (ann_ret - 0.04) / ann_vol if ann_vol > 0 else None
                faber_metrics = {"cagr_pct": round(cagr, 2), "sharpe": round(faber_sharpe, 3)}
                print(f"    Faber 10mo-SMA overlay (SPY): CAGR={fmt(faber_metrics['cagr_pct'], '.1f')}%  "
                      f"Sharpe={fmt(faber_metrics['sharpe'], '.3f')}")

        beats_faber = faber_metrics is not None and faber_metrics["sharpe"] is not None and sharpe > faber_metrics["sharpe"]
        print(f"    Beats Faber overlay (risk-adjusted): {beats_faber}")

        results[label] = {
            "cagr_pct": ret.get("cagr_pct"), "sharpe": sharpe, "skewness": skew,
            "kurtosis_pearson": kurtosis_pearson, "n_obs": n_obs,
            "sectors_held": result.tickers_used,
            "deflated_sharpe_ratio": dsr.deflated_sharpe_ratio if dsr else None,
            "significant_at_95pct": dsr.significant_at_95pct if dsr else None,
            "faber_overlay_spy": faber_metrics,
            "beats_faber_overlay": beats_faber,
        }

    out_path = "scripts/sector_rotation_backtest_result.json"
    with open(out_path, "w") as f:
        json.dump({"run_date": datetime.now().strftime("%Y-%m-%d"), "n_trials": N_TRIALS, "windows": results}, f, indent=2, default=str)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
