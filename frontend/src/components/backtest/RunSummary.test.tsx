import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { RunSummary } from "./RunSummary";
import type { BacktestHistoryItem } from "@/types";

vi.mock("@/components/charts/EquityChart", () => ({ EquityChart: () => null }));

function run(warnings?: string[]): BacktestHistoryItem {
  const result = {
    backtest_id: "x",
    strategy: "ma_crossover",
    initial_capital: 100000,
    final_value: 101000,
    total_return_pct: 1,
    total_trades: 2,
    equity_curve: [
      { date: "2020-01-02", value: 100000 },
      { date: "2023-10-31", value: 101000 },
    ],
    trades: [],
    metrics: {
      risk: { sharpe_ratio: 0.5 },
      drawdown: { max_drawdown_pct: -5 },
      trades: { win_rate: 0.5, profit_factor: 1.2 },
    },
    benchmark: { equity_curve: [], total_return_pct: 5 },
    monte_carlo: null,
    data_quality_warnings: warnings,
  } as unknown as BacktestHistoryItem["result"];
  return { id: "1", date: "", ticker: "AAPL", strategy: "ma_crossover", total_return_pct: 1, sharpe_ratio: 0.5, max_drawdown: -5, total_trades: 2, result };
}

// E2E finding (Nov 2026): a run that covered 14 months less than requested
// looked like a normal result. Backend coverage warnings must be visible.
test("shows data warnings under the period", () => {
  render(<RunSummary run={run(["Data ends 2023-10-31, 427 days before the requested end 2024-12-31"])} />);
  expect(screen.getByLabelText("Data warnings")).toHaveTextContent("Data ends 2023-10-31");
});

test("renders no warning list when there are none (older saved runs too)", () => {
  render(<RunSummary run={run(undefined)} />);
  expect(screen.queryByLabelText("Data warnings")).toBeNull();
});
