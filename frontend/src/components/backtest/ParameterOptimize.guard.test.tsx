import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("ParameterOptimize step validation (bug 3.11)", () => {
  it("rejects step=0 before starting the grid-generation loop, without calling the API", async () => {
    renderWithQueryClient(
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
