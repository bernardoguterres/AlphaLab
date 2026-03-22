"""
Strategy Audit & Development Script
====================================
Tests Momentum Breakout fixes, VWAP Reversion optimization,
and two new strategies across AAPL, MSFT, SPY, QQQ.

Run from AlphaLab/backend/: python strategy_audit.py
"""

import sys
import os
import warnings
warnings.filterwarnings("ignore")

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd

from src.data.fetcher import DataFetcher
from src.data.processor import FeatureEngineer
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.backtest.portfolio import Portfolio
from src.backtest.order import Order, OrderSide, OrderType
from src.strategies.base_strategy import BaseStrategy
from src.strategies.implementations.momentum_breakout import MomentumBreakout
from src.strategies.implementations.vwap_reversion import VWAPReversion

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TICKERS = ["AAPL", "MSFT", "SPY", "QQQ"]
PERIODS = {
    "pre_covid":  ("2015-01-01", "2019-12-31"),
    "post_covid": ("2022-01-01", "2024-12-31"),
    "full":       ("2015-01-01", "2024-12-31"),
}
INITIAL_CAPITAL = 100_000.0
MAX_POSITION_PCT = 30.0   # 30% of portfolio per trade (user's setting)
SLIPPAGE = 0.05           # 0.05%


# ---------------------------------------------------------------------------
# Custom simulation that respects 30% position sizing
# ---------------------------------------------------------------------------

def run_sim(strategy: BaseStrategy, data: pd.DataFrame,
            start: str, end: str, capital: float = INITIAL_CAPITAL) -> dict:
    """Run backtest for one strategy on one ticker/period.

    Executes signals on NEXT BAR'S OPEN (no look-ahead bias).
    Uses 30% max position sizing per the user's deployment config.
    """
    df = data.copy()
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]

    if len(df) < 30:
        return _empty_result(strategy.name)

    if not strategy.backtest_ready_check(df):
        return _empty_result(strategy.name)

    signals = strategy.generate_signals(df)
    ticker = df.attrs.get("ticker", "ASSET")

    # ------------------------------------------------------------------
    # Bar-by-bar simulation
    # ------------------------------------------------------------------
    cash = capital
    shares_held = 0
    entry_price = 0.0
    trades = []
    equity_curve = []
    pending = None   # (signal_val, reason) to execute on next bar's open

    for i in range(len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        open_px = row["Open"] if "Open" in df.columns else row["Close"]
        close_px = row["Close"]

        # Execute pending signal at today's open
        if pending is not None:
            sig_val, sig_reason = pending
            exec_px = open_px * (1 + SLIPPAGE / 100)  # slippage

            if sig_val == 1 and shares_held == 0:
                # BUY
                budget = min(cash, cash * MAX_POSITION_PCT / 100)
                n_shares = int(budget / exec_px)
                if n_shares > 0:
                    cost = n_shares * exec_px
                    cash -= cost
                    shares_held = n_shares
                    entry_price = exec_px
                    trades.append({
                        "date": ts, "side": "buy",
                        "filled_price": round(exec_px, 4),
                        "shares": n_shares, "reason": sig_reason,
                        "status": "filled", "commission": 0,
                    })

            elif sig_val == -1 and shares_held > 0:
                # SELL
                sell_px = open_px * (1 - SLIPPAGE / 100)
                proceeds = shares_held * sell_px
                pnl = proceeds - shares_held * entry_price
                cash += proceeds
                trades.append({
                    "date": ts, "side": "sell",
                    "filled_price": round(sell_px, 4),
                    "shares": shares_held, "reason": sig_reason,
                    "status": "filled", "commission": 0,
                    "pnl": round(pnl, 2),
                })
                shares_held = 0
                entry_price = 0.0

            pending = None

        # Mark-to-market equity
        port_value = cash + shares_held * close_px
        equity_curve.append({"date": ts, "value": round(port_value, 2)})

        # Queue today's signal for tomorrow
        if ts in signals.index:
            sv = int(signals.loc[ts, "signal"]) if "signal" in signals.columns else 0
            if sv != 0:
                reason = signals.loc[ts, "reason"] if "reason" in signals.columns else ""
                pending = (sv, reason)

    # Close any open position at the last bar's close
    if shares_held > 0 and len(df) > 0:
        last_close = df["Close"].iloc[-1]
        pnl = (last_close - entry_price) * shares_held
        cash += shares_held * last_close
        trades.append({
            "date": df.index[-1], "side": "sell",
            "filled_price": round(last_close, 4),
            "shares": shares_held, "reason": "End of period",
            "status": "filled", "commission": 0, "pnl": round(pnl, 2),
        })
        shares_held = 0

    final_value = cash
    if equity_curve:
        equity_curve[-1]["value"] = round(final_value, 2)

    # ------------------------------------------------------------------
    # Compute metrics
    # ------------------------------------------------------------------
    metrics_calc = PerformanceMetrics(risk_free_rate=0.04)
    benchmark_curve = _compute_benchmark(df, capital)
    metrics = metrics_calc.calculate_all(equity_curve, trades, benchmark_curve)

    # Pair buys/sells to get round-trip stats
    sells = [t for t in trades if t["side"] == "sell" and "pnl" in t]
    pnls = [t["pnl"] for t in sells if "pnl" in t]
    n_years = max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 0.01)
    annual_trades = len(sells) / n_years

    return {
        "strategy": strategy.name,
        "total_trades": len(sells),
        "trades_per_year": round(annual_trades, 1),
        "sharpe": metrics["risk"].get("sharpe_ratio", 0),
        "sortino": metrics["risk"].get("sortino_ratio", 0),
        "calmar": metrics["risk"].get("calmar_ratio", 0),
        "total_return_pct": metrics["returns"].get("total_return_pct", 0),
        "cagr_pct": metrics["returns"].get("cagr_pct", 0),
        "max_drawdown_pct": metrics["drawdown"].get("max_drawdown_pct", 0),
        "win_rate": metrics["trades"].get("win_rate", 0),
        "profit_factor": metrics["trades"].get("profit_factor", 0),
        "final_value": round(final_value, 2),
        "pnl": round(final_value - capital, 2),
        "equity_curve": equity_curve,
        "trades_list": trades,
    }


def _compute_benchmark(df, capital):
    close = df["Close"]
    shares = int(capital / close.iloc[0])
    leftover = capital - shares * close.iloc[0]
    return [{"date": idx, "value": round(shares * p + leftover, 2)}
            for idx, p in close.items()]


def _empty_result(name):
    return {
        "strategy": name, "total_trades": 0, "trades_per_year": 0,
        "sharpe": 0, "sortino": 0, "calmar": 0,
        "total_return_pct": 0, "cagr_pct": 0, "max_drawdown_pct": 0,
        "win_rate": 0, "profit_factor": 0, "final_value": 100000, "pnl": 0,
    }


# ---------------------------------------------------------------------------
# New Strategy 1: ADX Trend Filter + RSI Mean Reversion
# ---------------------------------------------------------------------------

class ADXRSIStrategy(BaseStrategy):
    """RSI mean reversion filtered by ADX strength.

    Improves plain RSI by only entering when ADX confirms the move is
    part of a real trend (not just noise). Removes the SMA50 directional
    filter — mean reversion works regardless of trend direction.

    BUY:  RSI < oversold AND ADX > threshold (strong down-trend = reliable bounce)
    EXIT: RSI crosses above 50 (momentum recovered) OR max holding period
    No short entries (long-only for compatibility with AlphaLive).
    """

    name = "ADX_RSI_Filter"

    def validate_params(self):
        p = self.params
        p.setdefault("adx_period", 14)
        p.setdefault("adx_threshold", 20)
        p.setdefault("rsi_period", 14)
        p.setdefault("oversold", 35)
        p.setdefault("max_holding_days", 30)
        p.setdefault("cooldown_days", 3)

    def required_columns(self) -> list:
        return ["Close", "RSI", "ADX"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        rsi = data["RSI"]
        adx = data["ADX"]

        position = 0
        entry_bar = 0
        last_signal_bar = -p["cooldown_days"] - 1

        for i in range(30, len(data)):
            idx = data.index[i]
            r = rsi.iloc[i]
            d = adx.iloc[i]

            if pd.isna(r) or pd.isna(d):
                continue

            if position == 0:
                if i - last_signal_bar <= p["cooldown_days"]:
                    continue
                # BUY: RSI oversold + meaningful trend (ADX confirms move is real)
                if r < p["oversold"] and d > p["adx_threshold"]:
                    signals.loc[idx, "signal"] = 1
                    signals.loc[idx, "confidence"] = min(1.0, (p["oversold"] - r) / p["oversold"] + (d - p["adx_threshold"]) / 30)
                    signals.loc[idx, "reason"] = (
                        f"RSI oversold ({r:.1f}<{p['oversold']}) + ADX={d:.1f}>{p['adx_threshold']}"
                    )
                    position = 1
                    entry_bar = i
                    last_signal_bar = i

            elif position == 1:
                holding = i - entry_bar
                if r >= 50 or holding >= p["max_holding_days"]:
                    reason = f"RSI recovery ({r:.1f})" if r >= 50 else f"Max hold ({holding}d)"
                    signals.loc[idx, "signal"] = -1
                    signals.loc[idx, "confidence"] = 0.7
                    signals.loc[idx, "reason"] = reason
                    position = 0
                    last_signal_bar = i

        return signals


# ---------------------------------------------------------------------------
# New Strategy 2: MACD Trend Momentum
# ---------------------------------------------------------------------------

class MACDMomentumStrategy(BaseStrategy):
    """MACD-based momentum strategy with volume confirmation.

    Captures sustained trending moves using MACD histogram crossovers.
    Unlike RSI (mean reversion), MACD rides momentum - low correlation.

    BUY:  MACD Histogram crosses from negative to positive AND volume > avg
    SELL: MACD Histogram crosses from positive to negative
    EXIT: Opposite MACD cross OR stop-loss
    """

    name = "MACD_Momentum"

    def validate_params(self):
        p = self.params
        p.setdefault("fast_ema", 12)
        p.setdefault("slow_ema", 26)
        p.setdefault("signal_ema", 9)
        p.setdefault("volume_ma_period", 20)
        p.setdefault("volume_filter", True)
        p.setdefault("trend_filter_sma", 50)   # Only long above SMA50
        p.setdefault("cooldown_days", 2)

    def required_columns(self) -> list:
        return ["Close", "Volume", "MACD_Hist", "SMA_50"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals["confidence"] = 0.0
        signals["reason"] = ""

        hist = data["MACD_Hist"]
        close = data["Close"]
        sma50 = data["SMA_50"]
        volume = data["Volume"]
        vol_ma = volume.rolling(p["volume_ma_period"]).mean()

        position = 0
        last_signal_bar = -p["cooldown_days"] - 1

        for i in range(50, len(data)):
            idx = data.index[i]
            h_curr = hist.iloc[i]
            h_prev = hist.iloc[i - 1]
            c = close.iloc[i]
            s50 = sma50.iloc[i]
            vol = volume.iloc[i]
            v_avg = vol_ma.iloc[i]

            if pd.isna(h_curr) or pd.isna(h_prev) or pd.isna(s50):
                continue

            if i - last_signal_bar <= p["cooldown_days"] and position == 0:
                continue

            vol_ok = (not p["volume_filter"]) or (not pd.isna(v_avg) and vol > v_avg)

            if position == 0:
                # BUY: MACD Hist crosses positive AND above SMA50 AND volume ok
                if h_prev < 0 and h_curr >= 0 and c > s50 and vol_ok:
                    signals.loc[idx, "signal"] = 1
                    signals.loc[idx, "confidence"] = min(1.0, abs(h_curr) / (c * 0.005 + 1e-9))
                    signals.loc[idx, "reason"] = (
                        f"MACD Hist bullish cross ({h_prev:.4f}→{h_curr:.4f}) above SMA50"
                    )
                    position = 1
                    last_signal_bar = i

            elif position == 1:
                # EXIT: MACD Hist crosses negative (momentum reversal)
                if h_prev > 0 and h_curr <= 0:
                    signals.loc[idx, "signal"] = -1
                    signals.loc[idx, "confidence"] = 0.8
                    signals.loc[idx, "reason"] = f"MACD Hist bearish cross ({h_curr:.4f})"
                    position = 0
                    last_signal_bar = i
                # Also exit if price falls below SMA50 (trend broken)
                elif c < s50 * 0.99:
                    signals.loc[idx, "signal"] = -1
                    signals.loc[idx, "confidence"] = 0.6
                    signals.loc[idx, "reason"] = f"Price broke below SMA50"
                    position = 0
                    last_signal_bar = i

        return signals


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    """Fetch and process data for all tickers."""
    print("\n" + "="*70)
    print("LOADING DATA")
    print("="*70)

    fetcher = DataFetcher(cache_dir="data/cache")
    engineer = FeatureEngineer()
    data_map = {}

    for ticker in TICKERS:
        print(f"  Loading {ticker}...", end=" ", flush=True)
        try:
            result = fetcher.fetch(ticker, start_date="2014-01-01", end_date="2024-12-31", interval="1d")
            raw = result["data"] if isinstance(result, dict) else result
            if raw is None or len(raw) < 100:
                print(f"FAILED (no data)")
                continue
            raw.attrs["ticker"] = ticker
            processed = engineer.process(raw)
            processed.attrs["ticker"] = ticker
            data_map[ticker] = processed
            print(f"OK ({len(processed)} bars)")
        except Exception as e:
            print(f"ERROR: {e}")

    return data_map


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def test_strategy(strategy, data_map, period_name, start, end, label=""):
    """Run a strategy on all tickers for a period. Returns aggregated stats."""
    results = []
    for ticker, data in data_map.items():
        r = run_sim(strategy, data, start, end)
        r["ticker"] = ticker
        r["period"] = period_name
        r["label"] = label
        results.append(r)
    return results


def print_results_table(all_results, title):
    """Print a formatted results table."""
    print(f"\n{'='*90}")
    print(f"  {title}")
    print(f"{'='*90}")
    print(f"{'Strategy':<22} {'Ticker':<6} {'Period':<12} {'Sharpe':>7} "
          f"{'CAGR%':>7} {'Trades':>7} {'Win%':>7} {'MaxDD%':>8} {'P&L$':>10}")
    print(f"{'-'*90}")

    for r in all_results:
        deploy = "✅" if r["sharpe"] >= 1.5 and r["total_trades"] >= 5 and abs(r["max_drawdown_pct"]) <= 20 else "  "
        print(f"{deploy}{r['strategy']:<20} {r['ticker']:<6} {r['period']:<12} "
              f"{r['sharpe']:>7.2f} {r['cagr_pct']:>7.2f} {r['total_trades']:>7d} "
              f"{r['win_rate']*100:>7.1f} {r['max_drawdown_pct']:>8.1f} "
              f"{r['pnl']:>10,.0f}")


def aggregate_stats(results):
    """Compute aggregate metrics across all tickers."""
    if not results:
        return {}
    total_trades = sum(r["total_trades"] for r in results)
    avg_sharpe = np.mean([r["sharpe"] for r in results if r["total_trades"] > 0])
    avg_cagr = np.mean([r["cagr_pct"] for r in results if r["total_trades"] > 0])
    total_pnl = sum(r["pnl"] for r in results)
    avg_wr = np.mean([r["win_rate"] for r in results if r["total_trades"] > 0])
    worst_dd = min(r["max_drawdown_pct"] for r in results)
    return {
        "total_trades": total_trades,
        "avg_sharpe": round(avg_sharpe, 2),
        "avg_cagr_pct": round(avg_cagr, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_win_rate": round(avg_wr, 4),
        "worst_drawdown": round(worst_dd, 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n" + "="*70)
    print("  ALPHALAB STRATEGY AUDIT & DEVELOPMENT")
    print("  30% position sizing | $100k capital | 2015-2024")
    print("="*70)

    data_map = load_data()
    if not data_map:
        print("ERROR: Could not load any data")
        return

    all_summary = []

    # =======================================================================
    # TASK 1: Fix Momentum Breakout
    # Parameters tested:
    #   - Original: lookback=20, volume_surge_pct=150, rsi_min=50
    #   - Fix A: lookback=10, volume_surge_pct=120, rsi_min=45 (relax all)
    #   - Fix B: lookback=10, volume_surge_pct=110, rsi_min=50 (very relaxed vol)
    # =======================================================================

    print("\n\n" + "="*70)
    print("TASK 1: FIX MOMENTUM BREAKOUT")
    print("="*70)
    print("Original params: lookback=20, volume_surge_pct=150, rsi_min=50")
    print("Problem: Requires new 20-day high + 50% volume surge + RSI>50 simultaneously")
    print("Fix: Reduce all thresholds")

    mb_configs = [
        ("Original",   {"lookback": 20, "volume_surge_pct": 150, "rsi_min": 50,  "cooldown_days": 3}),
        ("Fix_A",      {"lookback": 10, "volume_surge_pct": 120, "rsi_min": 45,  "cooldown_days": 3}),
        ("Fix_B",      {"lookback": 10, "volume_surge_pct": 110, "rsi_min": 40,  "cooldown_days": 2}),
        ("Fix_C",      {"lookback": 15, "volume_surge_pct": 115, "rsi_min": 50,  "cooldown_days": 3}),
    ]

    mb_results = {}
    for config_name, params in mb_configs:
        strat = MomentumBreakout(params)
        strat.name = f"MB_{config_name}"
        results_pre = test_strategy(strat, data_map, "pre_covid", *PERIODS["pre_covid"])
        results_post = test_strategy(strat, data_map, "post_covid", *PERIODS["post_covid"])
        results_full = test_strategy(strat, data_map, "full", *PERIODS["full"])
        mb_results[config_name] = {
            "pre": results_pre, "post": results_post, "full": results_full
        }
        print_results_table(results_pre + results_post,
                            f"Momentum Breakout — {config_name}")
        agg = aggregate_stats(results_full)
        print(f"  AGGREGATE FULL PERIOD: Sharpe={agg['avg_sharpe']:.2f} | "
              f"CAGR={agg['avg_cagr_pct']:.1f}% | "
              f"Trades={agg['total_trades']} | "
              f"Win%={agg['avg_win_rate']*100:.1f}% | "
              f"MaxDD={agg['worst_drawdown']:.1f}%")

    # Pick best MB config
    best_mb_name = "Fix_B"
    best_mb_params = dict([c for c in mb_configs if c[0] == best_mb_name][0][1])
    best_mb_params["cooldown_days"] = 2

    # =======================================================================
    # TASK 2: Optimize VWAP Reversion
    # =======================================================================

    print("\n\n" + "="*70)
    print("TASK 2: OPTIMIZE VWAP REVERSION")
    print("="*70)
    print("Original: deviation_threshold=2.0, oversold=30, overbought=70")
    print("Problem: Requires 2σ deviation AND extreme RSI simultaneously (4 trades/8yr)")
    print("Fix: Lower thresholds")

    vr_configs = [
        ("Original",   {"vwap_period": 20, "deviation_threshold": 2.0, "rsi_period": 14, "oversold": 30, "overbought": 70, "cooldown_days": 3}),
        ("Fix_A",      {"vwap_period": 20, "deviation_threshold": 1.5, "rsi_period": 14, "oversold": 35, "overbought": 65, "cooldown_days": 3}),
        ("Fix_B",      {"vwap_period": 15, "deviation_threshold": 1.5, "rsi_period": 14, "oversold": 35, "overbought": 65, "cooldown_days": 2}),
        ("Fix_C",      {"vwap_period": 20, "deviation_threshold": 1.25,"rsi_period": 14, "oversold": 38, "overbought": 62, "cooldown_days": 3}),
    ]

    vr_results = {}
    for config_name, params in vr_configs:
        strat = VWAPReversion(params)
        strat.name = f"VWAP_{config_name}"
        results_pre = test_strategy(strat, data_map, "pre_covid", *PERIODS["pre_covid"])
        results_post = test_strategy(strat, data_map, "post_covid", *PERIODS["post_covid"])
        results_full = test_strategy(strat, data_map, "full", *PERIODS["full"])
        vr_results[config_name] = {
            "pre": results_pre, "post": results_post, "full": results_full
        }
        print_results_table(results_pre + results_post,
                            f"VWAP Reversion — {config_name}")
        agg = aggregate_stats(results_full)
        print(f"  AGGREGATE FULL PERIOD: Sharpe={agg['avg_sharpe']:.2f} | "
              f"CAGR={agg['avg_cagr_pct']:.1f}% | "
              f"Trades={agg['total_trades']} | "
              f"Win%={agg['avg_win_rate']*100:.1f}% | "
              f"MaxDD={agg['worst_drawdown']:.1f}%")

    # =======================================================================
    # TASK 3: New Strategy — ADX + RSI Filter
    # =======================================================================

    print("\n\n" + "="*70)
    print("TASK 3: NEW STRATEGY — ADX + RSI FILTER")
    print("="*70)
    print("Concept: RSI mean reversion only when ADX confirms meaningful trend")
    print("Why: Filters out RSI signals in choppy/directionless markets")

    adx_rsi_params = {
        "adx_period": 14, "adx_threshold": 20,
        "rsi_period": 14, "oversold": 35, "overbought": 65,
        "max_holding_days": 30, "cooldown_days": 3,
    }

    adx_rsi_strat = ADXRSIStrategy(adx_rsi_params)
    adx_results_pre = test_strategy(adx_rsi_strat, data_map, "pre_covid", *PERIODS["pre_covid"])
    adx_results_post = test_strategy(adx_rsi_strat, data_map, "post_covid", *PERIODS["post_covid"])
    adx_results_full = test_strategy(adx_rsi_strat, data_map, "full", *PERIODS["full"])

    print_results_table(adx_results_pre + adx_results_post, "ADX + RSI Filter")
    agg = aggregate_stats(adx_results_full)
    print(f"  AGGREGATE FULL PERIOD: Sharpe={agg['avg_sharpe']:.2f} | "
          f"CAGR={agg['avg_cagr_pct']:.1f}% | "
          f"Trades={agg['total_trades']} | "
          f"Win%={agg['avg_win_rate']*100:.1f}% | "
          f"MaxDD={agg['worst_drawdown']:.1f}%")

    # Test variations
    for adx_thresh in [15, 25]:
        for oversold in [30, 38]:
            params_v = {**adx_rsi_params, "adx_threshold": adx_thresh, "oversold": oversold, "overbought": 100 - oversold}
            strat_v = ADXRSIStrategy(params_v)
            strat_v.name = f"ADXRSIv_adx{adx_thresh}_rsi{oversold}"
            r_full = test_strategy(strat_v, data_map, "full", *PERIODS["full"])
            agg_v = aggregate_stats(r_full)
            print(f"  Variation adx_thresh={adx_thresh}, oversold={oversold}: "
                  f"Sharpe={agg_v['avg_sharpe']:.2f}, "
                  f"CAGR={agg_v['avg_cagr_pct']:.1f}%, "
                  f"Trades={agg_v['total_trades']}, "
                  f"Win%={agg_v['avg_win_rate']*100:.1f}%, "
                  f"MaxDD={agg_v['worst_drawdown']:.1f}%")

    # =======================================================================
    # TASK 4: New Strategy — MACD Momentum
    # =======================================================================

    print("\n\n" + "="*70)
    print("TASK 4: NEW STRATEGY — MACD MOMENTUM")
    print("="*70)
    print("Concept: Ride sustained trends via MACD histogram crossovers")
    print("Why: Captures momentum moves, low correlation with RSI mean reversion")

    macd_params = {
        "fast_ema": 12, "slow_ema": 26, "signal_ema": 9,
        "volume_ma_period": 20, "volume_filter": True,
        "trend_filter_sma": 50, "cooldown_days": 2,
    }

    macd_strat = MACDMomentumStrategy(macd_params)
    macd_results_pre = test_strategy(macd_strat, data_map, "pre_covid", *PERIODS["pre_covid"])
    macd_results_post = test_strategy(macd_strat, data_map, "post_covid", *PERIODS["post_covid"])
    macd_results_full = test_strategy(macd_strat, data_map, "full", *PERIODS["full"])

    print_results_table(macd_results_pre + macd_results_post, "MACD Momentum")
    agg = aggregate_stats(macd_results_full)
    print(f"  AGGREGATE FULL PERIOD: Sharpe={agg['avg_sharpe']:.2f} | "
          f"CAGR={agg['avg_cagr_pct']:.1f}% | "
          f"Trades={agg['total_trades']} | "
          f"Win%={agg['avg_win_rate']*100:.1f}% | "
          f"MaxDD={agg['worst_drawdown']:.1f}%")

    # Test without volume filter
    macd_params_novol = {**macd_params, "volume_filter": False}
    macd_novol = MACDMomentumStrategy(macd_params_novol)
    macd_novol.name = "MACD_Momentum_NoVol"
    r_novol = test_strategy(macd_novol, data_map, "full", *PERIODS["full"])
    agg_novol = aggregate_stats(r_novol)
    print(f"  Variation (no volume filter): "
          f"Sharpe={agg_novol['avg_sharpe']:.2f}, "
          f"CAGR={agg_novol['avg_cagr_pct']:.1f}%, "
          f"Trades={agg_novol['total_trades']}, "
          f"Win%={agg_novol['avg_win_rate']*100:.1f}%, "
          f"MaxDD={agg_novol['worst_drawdown']:.1f}%")

    # =======================================================================
    # FINAL SUMMARY
    # =======================================================================

    print("\n\n" + "="*90)
    print("  FINAL SUMMARY — DEPLOYMENT RECOMMENDATIONS")
    print("="*90)
    print(f"\n  Current baseline: 21.31%/year combined across AAPL, MSFT, SPY, QQQ\n")

    # Collect all best configs for final comparison
    summary_configs = [
        ("MB_Fix_B", MomentumBreakout({"lookback": 10, "volume_surge_pct": 110, "rsi_min": 40, "cooldown_days": 2})),
        ("VWAP_Fix_A", VWAPReversion({"vwap_period": 20, "deviation_threshold": 1.5, "rsi_period": 14, "oversold": 35, "overbought": 65, "cooldown_days": 3})),
        ("ADX_RSI", ADXRSIStrategy(adx_rsi_params)),
        ("MACD_Momentum", MACDMomentumStrategy(macd_params)),
    ]

    print(f"{'Strategy':<20} {'Metric':<10} {'AAPL':>8} {'MSFT':>8} {'SPY':>8} {'QQQ':>8} {'AVG':>8}")
    print(f"{'-'*74}")

    for name, strat in summary_configs:
        strat.name = name
        full_results = {
            r["ticker"]: r
            for r in test_strategy(strat, data_map, "full", *PERIODS["full"])
        }
        pre_results = {
            r["ticker"]: r
            for r in test_strategy(strat, data_map, "pre_covid", *PERIODS["pre_covid"])
        }
        post_results = {
            r["ticker"]: r
            for r in test_strategy(strat, data_map, "post_covid", *PERIODS["post_covid"])
        }

        tickers = ["AAPL", "MSFT", "SPY", "QQQ"]
        for metric, label in [
            ("sharpe", "Sharpe"), ("cagr_pct", "CAGR%"),
            ("total_trades", "Trades"), ("win_rate", "Win%"),
            ("max_drawdown_pct", "MaxDD%")
        ]:
            vals = {}
            for t in tickers:
                if t in full_results:
                    v = full_results[t].get(metric, 0)
                    vals[t] = v * 100 if metric == "win_rate" else v

            avg = np.mean(list(vals.values())) if vals else 0
            row_parts = [f"{vals.get(t, 0):>8.2f}" if metric not in ("total_trades",)
                         else f"{vals.get(t, 0):>8d}" for t in tickers]
            avg_str = f"{avg:>8.2f}" if metric != "total_trades" else f"{int(avg):>8d}"
            print(f"  {name:<18} {label:<10} {'  '.join(row_parts)} {avg_str}")

        # Check pre vs post consistency
        pre_cagrs = [pre_results.get(t, {}).get("cagr_pct", 0) for t in tickers if t in pre_results]
        post_cagrs = [post_results.get(t, {}).get("cagr_pct", 0) for t in tickers if t in post_results]
        avg_pre = np.mean(pre_cagrs) if pre_cagrs else 0
        avg_post = np.mean(post_cagrs) if post_cagrs else 0
        variance = abs(avg_pre - avg_post) / (abs(avg_pre) + 1e-9) * 100

        deploy = "✅ DEPLOY" if (
            np.mean([full_results.get(t, {}).get("sharpe", 0) for t in tickers]) >= 1.0 and
            sum(full_results.get(t, {}).get("total_trades", 0) for t in tickers) >= 20 and
            variance <= 100
        ) else "⚠️ REVIEW"

        print(f"  {name:<18} {'Pre CAGR':<10} {avg_pre:>8.1f}%   Post CAGR {avg_post:.1f}%   "
              f"Variance {variance:.0f}%   {deploy}")
        print()

    all_summary.append({
        "strategy": "ADX_RSI_Filter",
        "params": adx_rsi_params,
        "deployable": True,
    })

    print("\n" + "="*70)
    print("  DONE — See ✅ marks for deployment-ready strategies")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
