import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { BacktestResult } from "@/types";
import { DEFAULT_RISK_SETTINGS } from "@/types";
import Compare from "./Compare";
import * as api from "@/services/api";

// Compare used to send no risk or sizing settings, so the backend ran its
// engine defaults and the numbers disagreed with a Backtest of the same
// strategy, ticker and window. It now sends the Backtest page's defaults
// and shows what the results were simulated with.

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof api>("@/services/api");
  return { ...actual, fetchData: vi.fn(), compareStrategies: vi.fn() };
});

// The chart is not under test, and Recharts needs a layout engine jsdom lacks.
vi.mock("@/components/comparison/OverlayEquityChart", () => ({ OverlayEquityChart: () => null }));

function result(totalReturn: number): BacktestResult {
  const curve = [
    { date: "2020-01-02", value: 100_000 },
    { date: "2024-12-31", value: 100_000 * (1 + totalReturn / 100) },
  ];
  return {
    total_return_pct: totalReturn,
    total_trades: 12,
    equity_curve: curve,
    benchmark: { total_return_pct: 50, equity_curve: curve },
    metrics: {
      risk: { sharpe_ratio: 0.5 },
      drawdown: { max_drawdown_pct: -5 },
      trades: { win_rate: 0.6, profit_factor: 2 },
    },
  } as unknown as BacktestResult;
}

describe("Compare run settings", () => {
  it("sends the Backtest defaults and lists them above the results", async () => {
    vi.mocked(api.fetchData).mockResolvedValue({ status: "ok", data: {}, errors: [] });
    vi.mocked(api.compareStrategies).mockResolvedValue({
      status: "ok",
      data: { ma_crossover: result(10), rsi_mean_reversion: result(5) },
    } as Awaited<ReturnType<typeof api.compareStrategies>>);

    render(<Compare />);
    fireEvent.click(screen.getByRole("button", { name: "Run comparison" }));

    await waitFor(() => expect(api.compareStrategies).toHaveBeenCalledTimes(1));
    expect(api.compareStrategies).toHaveBeenCalledWith(
      expect.objectContaining({
        position_sizing: "equal_weight",
        risk_settings: DEFAULT_RISK_SETTINGS,
        drawdown_halt_enabled: true,
      }),
    );
    expect(
      await screen.findByText(
        "Simulated with: Position 10% · stop 2% · target 5% · no trailing stop · equal weight · halt after a 10% drawdown",
      ),
    ).toBeInTheDocument();
  });

  it("sends the drawdown halt switched off when it is unticked", async () => {
    vi.mocked(api.compareStrategies).mockClear();
    render(<Compare />);
    fireEvent.click(screen.getByLabelText("Halt new entries after a 10% drawdown"));
    fireEvent.click(screen.getByRole("button", { name: "Run comparison" }));

    await waitFor(() => expect(api.compareStrategies).toHaveBeenCalledTimes(1));
    expect(api.compareStrategies).toHaveBeenCalledWith(expect.objectContaining({ drawdown_halt_enabled: false }));
  });
});
