#!/usr/bin/env python3
"""
Test New Strategies - Comprehensive Backtest

Tests the 3 new strategies designed for 1-3 trades/day:
1. RSI_Simple - Relaxed RSI 40/60 with no filters
2. Bollinger_RSI_Combo - BB lower touch + RSI confirmation
3. Trend_Adaptive_RSI - Adaptive thresholds based on market regime

Runs on SPY 2020-2024 (5 years) and recent data (last 60 days) to verify:
- Signal frequency (should be 10-20 trades/month on daily, 50-100/month on 15Min)
- Performance metrics (Sharpe > 1.2, win rate > 45%)
- Drawdown (< 15%)
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from src.data.processor import FeatureEngineer
from src.strategies.implementations.rsi_simple import RSISimple
from src.strategies.implementations.bollinger_rsi_combo import BollingerRSICombo
from src.strategies.implementations.trend_adaptive_rsi import TrendAdaptiveRSI
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.backtest.portfolio import Portfolio

def run_backtest(strategy_class, params, data, ticker, period_name):
    """Run backtest and return results."""
    print(f"\n{'='*80}")
    print(f"Testing {strategy_class.name} on {ticker} ({period_name})")
    print(f"Parameters: {params}")
    print(f"{'='*80}")

    # Initialize strategy
    strategy = strategy_class(params)

    # Generate signals
    signals = strategy.generate_signals(data)

    # Count signals
    total_signals = (signals["signal"] != 0).sum()
    buys = (signals["signal"] == 1).sum()
    sells = (signals["signal"] == -1).sum()
    days = len(data)

    print(f"\n📊 Signal Statistics:")
    print(f"   Total bars: {days}")
    print(f"   Total signals: {total_signals}")
    print(f"   BUY signals: {buys}")
    print(f"   SELL signals: {sells}")
    print(f"   Signal rate: {100 * total_signals / days:.2f}%")
    print(f"   Trades per month (est): {total_signals / (days / 21):.1f}")

    if total_signals == 0:
        print("   ⚠️  NO SIGNALS - Strategy too strict!")
        return None

    # Run backtest
    portfolio = Portfolio(
        initial_capital=100000,
        slippage_pct=0.05,
        commission_rate=0.0,
        max_position_pct=30.0  # 30% max position size
    )

    engine = BacktestEngine(portfolio)
    results = engine.run(data, signals)

    # Calculate metrics
    metrics_calc = PerformanceMetrics()
    metrics = metrics_calc.calculate_all(results)

    # Print key metrics
    print(f"\n📈 Performance Metrics:")
    print(f"   Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"   Sortino Ratio: {metrics['sortino_ratio']:.2f}")
    print(f"   Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"   Win Rate: {metrics['win_rate_pct']:.2f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Total Trades: {metrics['total_trades']}")

    # Assessment
    print(f"\n✅ Assessment:")
    sharpe_ok = metrics['sharpe_ratio'] > 1.2
    win_rate_ok = metrics['win_rate_pct'] > 45
    drawdown_ok = metrics['max_drawdown_pct'] > -15
    trades_ok = metrics['total_trades'] > 30  # At least 30 trades in 5 years

    print(f"   Sharpe > 1.2: {'✅' if sharpe_ok else '❌'} ({metrics['sharpe_ratio']:.2f})")
    print(f"   Win Rate > 45%: {'✅' if win_rate_ok else '❌'} ({metrics['win_rate_pct']:.1f}%)")
    print(f"   Drawdown > -15%: {'✅' if drawdown_ok else '❌'} ({metrics['max_drawdown_pct']:.1f}%)")
    print(f"   Trades > 30: {'✅' if trades_ok else '❌'} ({metrics['total_trades']})")

    passed = sharpe_ok and win_rate_ok and drawdown_ok and trades_ok
    print(f"\n   Overall: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        'strategy': strategy_class.name,
        'signals': total_signals,
        'metrics': metrics,
        'passed': passed
    }


def main():
    print("="*80)
    print("COMPREHENSIVE BACKTEST - New Trading Strategies")
    print("="*80)
    print("\nTarget: 1-3 trades/day (30-60 trades/month)")
    print("Testing on: SPY 2020-2024 (5 years)")
    print()

    # Initialize data fetcher (bypass cache to avoid datetime serialization issues)
    import yfinance as yf
    engineer = FeatureEngineer()

    # Fetch SPY data (5 years)
    ticker = "SPY"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)  # 5 years

    print(f"Fetching {ticker} data from {start_date.date()} to {end_date.date()}...")
    raw_data = yf.download(ticker, start=start_date, end=end_date, progress=False)

    # Flatten MultiIndex columns if needed
    if isinstance(raw_data.columns, pd.MultiIndex):
        raw_data.columns = raw_data.columns.get_level_values(0)

    # Standardize column names
    raw_data = raw_data.rename(columns={
        'Open': 'Open',
        'High': 'High',
        'Low': 'Low',
        'Close': 'Close',
        'Volume': 'Volume'
    })

    if raw_data is None or len(raw_data) < 200:
        print(f"❌ Failed to fetch sufficient data for {ticker}")
        return

    print(f"✅ Fetched {len(raw_data)} bars")

    # Add technical indicators
    print("Adding technical indicators...")
    data = engineer.process(raw_data)
    print(f"✅ Added features. Data shape: {data.shape}")

    # Strategy configurations
    strategies = [
        {
            'class': RSISimple,
            'params': {
                'period': 14,
                'oversold': 40,
                'overbought': 60
            }
        },
        {
            'class': BollingerRSICombo,
            'params': {
                'bb_period': 20,
                'bb_std': 2.0,
                'rsi_period': 14,
                'rsi_oversold': 45,
                'rsi_overbought': 55,
                'exit_at_middle': True
            }
        },
        {
            'class': TrendAdaptiveRSI,
            'params': {
                'rsi_period': 14,
                'trend_sma': 50,
                'trend_lookback': 5,
                'uptrend_buy': 45,
                'uptrend_sell': 65,
                'downtrend_buy': 35,
                'downtrend_sell': 55,
                'range_buy': 35,
                'range_sell': 65
            }
        }
    ]

    results = []

    # Test each strategy
    for config in strategies:
        result = run_backtest(
            config['class'],
            config['params'],
            data,
            ticker,
            "2020-2024"
        )
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print(f"\n{'Strategy':<25} {'Signals':<10} {'Sharpe':<8} {'Win%':<8} {'Drawdown':<10} {'Status'}")
    print("-"*80)

    for r in results:
        status = "✅ PASS" if r['passed'] else "❌ FAIL"
        print(f"{r['strategy']:<25} {r['signals']:<10} {r['metrics']['sharpe_ratio']:<8.2f} "
              f"{r['metrics']['win_rate_pct']:<8.1f} {r['metrics']['max_drawdown_pct']:<10.1f} {status}")

    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    passing_strategies = [r for r in results if r['passed']]

    if len(passing_strategies) == 0:
        print("\n❌ None of the strategies passed all criteria.")
        print("   Consider:")
        print("   1. Further relaxing RSI thresholds (35/65)")
        print("   2. Switching to 15Min or 1Hour timeframe for more signals")
        print("   3. Combining strategies in a portfolio")
    else:
        print(f"\n✅ {len(passing_strategies)} strategies passed!")

        # Find best by Sharpe
        best = max(passing_strategies, key=lambda x: x['metrics']['sharpe_ratio'])
        print(f"\n🏆 Best Strategy: {best['strategy']}")
        print(f"   Sharpe: {best['metrics']['sharpe_ratio']:.2f}")
        print(f"   Return: {best['metrics']['total_return_pct']:.1f}%")
        print(f"   Signals: {best['signals']} ({best['signals'] / (len(data) / 21):.1f}/month)")
        print(f"\n   ✅ READY FOR EXPORT TO ALPHALIVE")

    print()

if __name__ == "__main__":
    main()
