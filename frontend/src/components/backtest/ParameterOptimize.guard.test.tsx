import { describe, it, expect, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import ParameterOptimize from "./ParameterOptimize";
import * as api from "@/services/api";

// Regression test for audit bug 3.11: ParameterOptimize.tsx's grid-
// generation loop (`for (let val = range.min; val <= range.max; val +=
// range.step)`) had no guard against step <= 0 - with step=0, val never
// advances, so the loop runs forever and hangs the browser tab BEFORE any
// network request is sent. handleOptimize/handleGenerateHeatmap now
// validate step > 0 up front and show a toast error instead of entering
// the loop.

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof api>("@/services/api");
  return {
    ...actual,
    getAvailableData: vi.fn().mockResolvedValue([]),
    optimizeParameters: vi.fn(),
    generateHeatmap: vi.fn(),
  };
});

describe("ParameterOptimize step validation (bug 3.11)", () => {
  it("rejects step=0 before starting the grid-generation loop, without calling the API", async () => {
    render(
      <ParameterOptimize
        ticker="AAPL"
        strategy="ma_crossover"
        startDate="2020-01-01"
        endDate="2024-12-31"
        initialCapital={100000}
        onApplyParams={() => {}}
      />
    );

    // Set short_window's step (default 10, the only field with this value -
    // min=20/max=50 don't clash) to 0 - the exact input that used to hang
    // the browser tab.
    const stepInput = screen.getByDisplayValue("10") as HTMLInputElement;
    fireEvent.change(stepInput, { target: { value: "0" } });

    const runButton = screen.getByRole("button", { name: /optimize parameters|run optimization/i });
    fireEvent.click(runButton);

    // If the old bug were present, this click would hang the JS main
    // thread indefinitely (val += 0 never advances past range.max) and
    // this test would time out rather than reach this assertion.
    await waitFor(() => {
      expect(api.optimizeParameters).not.toHaveBeenCalled();
    });
  });
});

it("includes an exact decimal endpoint in the optimizer request", async () => {
  vi.mocked(api.optimizeParameters).mockClear();
  render(
    <ParameterOptimize
      ticker="SPY"
      strategy="bollinger_breakout"
      startDate="2020-01-01"
      endDate="2024-12-31"
      initialCapital={100000}
      onApplyParams={() => {}}
    />
  );
  for (const [field, value] of [["min", "1.1"], ["max", "1.3"], ["step", "0.1"]]) {
    fireEvent.change(screen.getByRole("spinbutton", { name: new RegExp(`Band width.* ${field}$`) }), {
      target: { value },
    });
  }
  fireEvent.click(screen.getByRole("button", { name: /run optimization/i }));
  await waitFor(() => {
    expect(api.optimizeParameters).toHaveBeenCalledWith(expect.objectContaining({
      param_grid: expect.objectContaining({ bb_std_dev: [1.1, 1.2, 1.3] }),
    }));
  });
});

it("discards an optimization response after the ticker changes", async () => {
  let complete: (response: Awaited<ReturnType<typeof api.optimizeParameters>>) => void;
  vi.mocked(api.optimizeParameters).mockImplementationOnce(() => new Promise((resolve) => {
    complete = resolve;
  }));
  const props = {
    strategy: "ma_crossover" as const,
    startDate: "2020-01-01",
    endDate: "2024-12-31",
    initialCapital: 100000,
    onApplyParams: vi.fn(),
  };
  const { rerender } = render(<ParameterOptimize {...props} ticker="AAPL" />);
  fireEvent.click(screen.getByRole("button", { name: /run optimization/i }));
  rerender(<ParameterOptimize {...props} ticker="MSFT" />);
  await act(async () => {
    complete({
      status: "ok",
      data: {
        best_params: { short_window: 20, long_window: 100 },
        best_score: 1,
        all_results: [],
        optimization_target: "sharpe_ratio",
        walk_forward: false,
      },
    });
  });
  expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
});
