import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MetricsTabs } from "@/components/metrics/MetricsTabs";
import { formatCurrency } from "@/utils/formatters";
import type { BacktestMetrics } from "@/types";

// Regression test, same class of bug as MonteCarloResult (audit bug 3.12):
//
// 1. metrics.trades.avg_win/avg_loss/expectancy/best_trade/worst_trade are
//    raw dollar P&L per the backend's _trade_metrics() (metrics.py), not
//    percentages - but MetricsTabs.tsx rendered all five through
//    formatPercent(), producing outputs like "+245.30%" for a $245.30
//    average win.
//
// 2. metrics.vs_benchmark declared alpha/tracking_error/up_capture/
//    down_capture, but the backend's _benchmark_metrics() actually returns
//    alpha_annual_pct/tracking_error_pct/up_capture_pct/down_capture_pct -
//    the mismatched keys were always undefined, silently rendering as "-"
//    in the vs Benchmark tab for every real backtest.

const SAMPLE_METRICS: BacktestMetrics = {
  returns: {
    total_return_pct: 25.5,
    cagr_pct: 12.3,
    mean_daily_return: 0.05,
    skewness: -0.2,
    kurtosis: 3.1,
  },
  risk: {
    volatility_annual_pct: 18.2,
    sharpe_ratio: 1.35,
    sortino_ratio: 1.8,
    calmar_ratio: 2.1,
    var_95_pct: -2.5,
    cvar_95_pct: -3.8,
  },
  drawdown: {
    max_drawdown_pct: -11.2,
    avg_drawdown_pct: -3.4,
    max_drawdown_duration_days: 45,
    recovery_days: 30,
  },
  trades: {
    win_rate: 0.55,
    avg_win: 245.3,
    avg_loss: -132.75,
    profit_factor: 1.8,
    expectancy: 61.2,
    best_trade: 980.5,
    worst_trade: -410.25,
  },
  consistency: {
    profitable_months_pct: 62.5,
    longest_win_streak: 5,
    longest_loss_streak: 2,
    ulcer_index: 1.2,
  },
  vs_benchmark: {
    beta: 0.85,
    alpha_annual_pct: 4.2,
    alpha_t_stat: 2.1,
    alpha_p_value: 0.03,
    alpha_significant: true,
    tracking_error_pct: 6.5,
    information_ratio: 0.65,
    up_capture_pct: 105.0,
    down_capture_pct: 88.0,
  },
};

describe("MetricsTabs trade dollar-value rendering", () => {
  it("renders avg_win/avg_loss/expectancy/best_trade/worst_trade as currency, not percentages", () => {
    render(<MetricsTabs metrics={SAMPLE_METRICS} />);
    const tradesTab = screen.getByRole("tab", { name: "Trades" });
    fireEvent.mouseDown(tradesTab);
    fireEvent.click(tradesTab);

    // The old bug: formatPercent(245.3) -> "+245.30%". Must not appear.
    expect(screen.queryByText(/245\.30%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/-132\.75%/)).not.toBeInTheDocument();

    expect(screen.getByText(formatCurrency(SAMPLE_METRICS.trades.avg_win))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_METRICS.trades.avg_loss))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_METRICS.trades.expectancy))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_METRICS.trades.best_trade))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_METRICS.trades.worst_trade))).toBeInTheDocument();
  });
});

describe("MetricsTabs vs-benchmark field names", () => {
  it("reads the real backend field names, not the stale alpha/tracking_error/up_capture/down_capture ones", () => {
    render(<MetricsTabs metrics={SAMPLE_METRICS} />);
    const benchmarkTab = screen.getByRole("tab", { name: "vs Benchmark" });
    fireEvent.mouseDown(benchmarkTab);
    fireEvent.click(benchmarkTab);

    // Old bug: these fields didn't exist on the real API response, so
    // formatPercent(undefined) -> "-" for all four rows below.
    expect(screen.getByText("+4.20%")).toBeInTheDocument(); // alpha_annual_pct
    expect(screen.getByText("+6.50%")).toBeInTheDocument(); // tracking_error_pct
    expect(screen.getByText("+105.00%")).toBeInTheDocument(); // up_capture_pct
    expect(screen.getByText("+88.00%")).toBeInTheDocument(); // down_capture_pct
  });
});
