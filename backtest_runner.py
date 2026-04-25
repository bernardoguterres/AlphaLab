#!/usr/bin/env python3
"""
Comprehensive Backtest Runner - Tests all 3 new strategies on multiple tickers.

This script properly uses the AlphaLab API to run backtests and generate reports.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.strategies.implementations.rsi_simple import RSISimple
from src.strategies.implementations.bollinger_rsi_combo import BollingerRSICombo
from src.strategies.implementations.trend_adaptive_rsi import TrendAdaptiveRSI
from src.data.processor import FeatureEngineer

def fetch_data(ticker, years=5):
    """Fetch historical data."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*years)

    print(f"📥 Fetching {ticker} data ({start_date.date()} to {end_date.date()})...")

    data = yf.download(ticker, start=start_date, end=end_date, progress=False)

    # Flatten MultiIndex if needed
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    print(f"   ✅ {len(data)} bars fetched")
    return data

def add_features(data):
    """Add technical indicators."""
    print("🔧 Adding technical indicators...")
    engineer = FeatureEngineer()
    data_with_features = engineer.process(data)
    print(f"   ✅ {len(data_with_features.columns)} features added")
    return data_with_features

def calculate_simple_metrics(data, signals):
    """Calculate basic performance metrics."""
    # Simulate simple backtest
    trades = []
    in_position = False
    entry_price = 0
    entry_date = None

    for i in range(len(signals)):
        if signals['signal'].iloc[i] == 1 and not in_position:
            # Entry
            entry_price = data['Close'].iloc[i]
            entry_date = data.index[i]
            in_position = True

        elif signals['signal'].iloc[i] == -1 and in_position:
            # Exit
            exit_price = data['Close'].iloc[i]
            exit_date = data.index[i]
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            trades.append({
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'win': pnl_pct > 0
            })

            in_position = False

    if len(trades) == 0:
        return None

    trades_df = pd.DataFrame(trades)

    # Calculate metrics
    total_trades = len(trades_df)
    wins = trades_df['win'].sum()
    losses = total_trades - wins
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    avg_win = trades_df[trades_df['win']]['pnl_pct'].mean() if wins > 0 else 0
    avg_loss = trades_df[~trades_df['win']]['pnl_pct'].mean() if losses > 0 else 0

    total_return = trades_df['pnl_pct'].sum()

    # Simple Sharpe (not accurate but gives idea)
    returns_std = trades_df['pnl_pct'].std()
    sharpe_approx = (trades_df['pnl_pct'].mean() / returns_std * (252/total_trades)**0.5) if returns_std > 0 else 0

    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate_pct': win_rate,
        'avg_win_pct': avg_win,
        'avg_loss_pct': avg_loss,
        'total_return_pct': total_return,
        'sharpe_approx': sharpe_approx
    }

def backtest_strategy(strategy_class, params, data, ticker, strategy_name):
    """Run backtest for a strategy."""
    print(f"\n{'='*80}")
    print(f"🧪 Testing {strategy_name} on {ticker}")
    print(f"{'='*80}")
    print(f"Parameters: {params}")

    # Initialize strategy
    try:
        strategy = strategy_class(params)
    except Exception as e:
        print(f"❌ Failed to initialize strategy: {e}")
        return None

    # Generate signals
    print("\n📊 Generating signals...")
    try:
        signals = strategy.generate_signals(data)
    except Exception as e:
        print(f"❌ Failed to generate signals: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Count signals
    total_signals = (signals['signal'] != 0).sum()
    buys = (signals['signal'] == 1).sum()
    sells = (signals['signal'] == -1).sum()

    print(f"\n📈 Signal Statistics:")
    print(f"   Total bars: {len(data)}")
    print(f"   Total signals: {total_signals}")
    print(f"   BUY signals: {buys}")
    print(f"   SELL signals: {sells}")
    print(f"   Signal rate: {100 * total_signals / len(data):.2f}%")
    print(f"   Trades/month (est): {total_signals / (len(data) / 21):.1f}")

    if total_signals < 10:
        print("\n   ⚠️  Very few signals - strategy may be too strict")
        return None

    # Calculate metrics
    print("\n💰 Performance Metrics:")
    metrics = calculate_simple_metrics(data, signals)

    if metrics is None:
        print("   ❌ No completed trades")
        return None

    print(f"   Total Trades: {metrics['total_trades']}")
    print(f"   Win Rate: {metrics['win_rate_pct']:.1f}%")
    print(f"   Avg Win: {metrics['avg_win_pct']:.2f}%")
    print(f"   Avg Loss: {metrics['avg_loss_pct']:.2f}%")
    print(f"   Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"   Sharpe (approx): {metrics['sharpe_approx']:.2f}")

    # Assessment
    print(f"\n✅ Assessment:")
    trades_ok = metrics['total_trades'] >= 30
    win_rate_ok = metrics['win_rate_pct'] >= 40
    sharpe_ok = metrics['sharpe_approx'] >= 0.8

    print(f"   Trades >= 30: {'✅' if trades_ok else '❌'} ({metrics['total_trades']})")
    print(f"   Win Rate >= 40%: {'✅' if win_rate_ok else '❌'} ({metrics['win_rate_pct']:.1f}%)")
    print(f"   Sharpe >= 0.8: {'✅' if sharpe_ok else '❌'} ({metrics['sharpe_approx']:.2f})")

    passed = trades_ok and win_rate_ok and sharpe_ok
    print(f"\n   Overall: {'✅ PASS - Ready for deployment!' if passed else '❌ NEEDS IMPROVEMENT'}")

    return {
        'strategy': strategy_name,
        'ticker': ticker,
        'signals': total_signals,
        'metrics': metrics,
        'passed': passed
    }

def main():
    print("="*80)
    print("COMPREHENSIVE BACKTEST - New Trading Strategies")
    print("="*80)
    print("\nTesting 3 strategies on 4 tickers (12 backtests total)")
    print("Test period: 2020-2024 (5 years)\n")

    # Tickers to test
    tickers = ['SPY', 'QQQ', 'AAPL', 'MSFT']

    # Strategy configurations
    strategies = [
        {
            'class': RSISimple,
            'name': 'RSI_Simple',
            'params': {
                'period': 14,
                'oversold': 40,
                'overbought': 60
            }
        },
        {
            'class': BollingerRSICombo,
            'name': 'Bollinger_RSI_Combo',
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
            'name': 'Trend_Adaptive_RSI',
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

    all_results = []

    # Test each ticker
    for ticker in tickers:
        print(f"\n{'#'*80}")
        print(f"# TICKER: {ticker}")
        print(f"{'#'*80}")

        # Fetch and prepare data
        try:
            raw_data = fetch_data(ticker, years=5)
            if len(raw_data) < 200:
                print(f"❌ Insufficient data for {ticker}")
                continue

            data = add_features(raw_data)
        except Exception as e:
            print(f"❌ Failed to fetch/process data for {ticker}: {e}")
            continue

        # Test each strategy
        for strategy_config in strategies:
            result = backtest_strategy(
                strategy_config['class'],
                strategy_config['params'],
                data,
                ticker,
                strategy_config['name']
            )

            if result:
                all_results.append(result)

    # Summary Report
    print("\n" + "="*80)
    print("SUMMARY REPORT")
    print("="*80)

    if len(all_results) == 0:
        print("\n❌ No successful backtests")
        return

    # Group by strategy
    print("\n📊 Results by Strategy:\n")

    for strategy_config in strategies:
        strategy_name = strategy_config['name']
        strategy_results = [r for r in all_results if r['strategy'] == strategy_name]

        if len(strategy_results) == 0:
            continue

        print(f"\n{strategy_name}:")
        print(f"{'─'*80}")

        passed_count = sum(1 for r in strategy_results if r['passed'])

        for r in strategy_results:
            status = "✅" if r['passed'] else "❌"
            m = r['metrics']
            print(f"  {status} {r['ticker']:<6} | Trades: {m['total_trades']:>3} | "
                  f"Win%: {m['win_rate_pct']:>5.1f}% | Sharpe: {m['sharpe_approx']:>5.2f} | "
                  f"Return: {m['total_return_pct']:>6.1f}%")

        print(f"\n  Summary: {passed_count}/{len(strategy_results)} tickers passed")

    # Best performers
    print("\n" + "="*80)
    print("🏆 BEST PERFORMERS")
    print("="*80)

    passing_results = [r for r in all_results if r['passed']]

    if len(passing_results) == 0:
        print("\n❌ No strategies passed all criteria")
        print("\n💡 Recommendations:")
        print("   1. Try relaxing thresholds further (RSI 35/65)")
        print("   2. Test on shorter timeframe (1Hour or 15Min)")
        print("   3. Adjust stop loss / take profit")
    else:
        # Sort by Sharpe ratio
        passing_results.sort(key=lambda x: x['metrics']['sharpe_approx'], reverse=True)

        print(f"\n✅ {len(passing_results)} strategy-ticker combinations passed!\n")

        for i, r in enumerate(passing_results[:5], 1):  # Top 5
            m = r['metrics']
            print(f"{i}. {r['strategy']} on {r['ticker']}")
            print(f"   Sharpe: {m['sharpe_approx']:.2f} | Return: {m['total_return_pct']:.1f}% | "
                  f"Win Rate: {m['win_rate_pct']:.1f}% | Trades: {m['total_trades']}")

        # Recommend deployment
        best = passing_results[0]
        print(f"\n🎯 RECOMMENDED FOR DEPLOYMENT:")
        print(f"   Strategy: {best['strategy']}")
        print(f"   Ticker: {best['ticker']}")
        print(f"   Expected: {best['metrics']['total_trades'] / 5:.0f} trades/year")
        print(f"   Win Rate: {best['metrics']['win_rate_pct']:.1f}%")
        print(f"   Sharpe: {best['metrics']['sharpe_approx']:.2f}")
        print(f"\n   ✅ Ready to export to AlphaLive!")

    # Save results
    results_file = Path(__file__).parent / 'backtest_results.json'
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': all_results
        }, f, indent=2, default=str)

    print(f"\n💾 Results saved to: {results_file}")
    print()

if __name__ == "__main__":
    main()
