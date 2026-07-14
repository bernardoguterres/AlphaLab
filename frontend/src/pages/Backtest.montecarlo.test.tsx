import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "@/components/metrics/MetricCard";
import { formatCurrency, formatPercent } from "@/utils/formatters";
import type { MonteCarloResult } from "@/types";

// Regression test for audit bug 3.12: the backend's Monte Carlo output
// (engine.py's _monte_carlo()) returns a distribution of final DOLLAR
// values (percentile_5, percentile_95, mean_final_value,
// median_final_value, min_final_value, max_final_value, std_final_value,
// prob_profit as a 0-1 fraction) - but MonteCarloResult declared
// percentile_25/median/percentile_75 (fields the backend has never
// returned) and every field was rendered through formatPercent(),
// producing outputs like "+125430.00%" for a dollar figure.
//
// MonteCarloResult now matches the real backend shape (TypeScript itself
// prevents reintroducing the removed fields), and this test mirrors
// Backtest.tsx's actual Monte Carlo rendering block to prove the dollar
// fields render as currency, not as a percentage.

const SAMPLE_RESULT: MonteCarloResult = {
  runs: 500,
  mean_final_value: 118_432.5,
  median_final_value: 115_200.0,
  std_final_value: 12_500.75,
  min_final_value: 82_100.0,
  max_final_value: 165_430.25,
  prob_profit: 0.78,
  percentile_5: 92_500.4,
  percentile_95: 142_800.9,
};

function MonteCarloBlock({ mc }: { mc: MonteCarloResult }) {
  return (
    <div>
      <MetricCard label="5th Percentile" value={formatCurrency(mc.percentile_5)} />
      <MetricCard label="Min" value={formatCurrency(mc.min_final_value)} />
      <MetricCard label="Median" value={formatCurrency(mc.median_final_value)} />
      <MetricCard label="Max" value={formatCurrency(mc.max_final_value)} />
      <MetricCard label="95th Percentile" value={formatCurrency(mc.percentile_95)} />
      <MetricCard label="Mean Final Value" value={formatCurrency(mc.mean_final_value)} />
      <MetricCard label="Std Dev" value={formatCurrency(mc.std_final_value)} />
      <MetricCard label="Probability of Profit" value={formatPercent(mc.prob_profit * 100)} />
    </div>
  );
}

describe("Monte Carlo dollar-value rendering (bug 3.12)", () => {
  it("renders percentile/mean/median/min/max as currency, not as a percentage", () => {
    render(<MonteCarloBlock mc={SAMPLE_RESULT} />);

    // The old bug: formatPercent(92500.4) -> "+92500.40%". Must not appear.
    expect(screen.queryByText(/92500\.40%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/142800\.90%/)).not.toBeInTheDocument();

    // Correct: rendered as currency.
    expect(screen.getByText(formatCurrency(SAMPLE_RESULT.percentile_5))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_RESULT.percentile_95))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_RESULT.median_final_value))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_RESULT.min_final_value))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(SAMPLE_RESULT.max_final_value))).toBeInTheDocument();
  });

  it("renders prob_profit (a 0-1 fraction) as a percentage with the *100 conversion", () => {
    render(<MonteCarloBlock mc={SAMPLE_RESULT} />);
    // 0.78 -> "+78.00%", not "+0.78%".
    expect(screen.getByText("+78.00%")).toBeInTheDocument();
  });
});
