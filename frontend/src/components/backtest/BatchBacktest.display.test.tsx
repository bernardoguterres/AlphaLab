import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BatchBacktest } from "./BatchBacktest";
import * as api from "@/services/api";

// Regression test for audit bug 3.10: BatchBacktest.tsx divided
// already-percentage-point backend values (total_return_pct,
// max_drawdown_pct, profitable_pct) by 100 again before formatting, and
// passed win_rate (a 0-1 fraction) straight through the percent formatter
// without multiplying by 100 - both produce numbers off by a factor of 100
// in opposite directions. This renders the real component end-to-end
// against a mocked API response shaped exactly like the backend actually
// returns it, and asserts the displayed strings are correct - a
// regression in either direction (reintroducing /100 or dropping *100)
// would fail this test.

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof api>("@/services/api");
  return {
    ...actual,
    getAvailableData: vi.fn().mockResolvedValue([]),
    runBatchBacktest: vi.fn(),
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

describe("BatchBacktest percentage display (bug 3.10)", () => {
  it("renders total_return_pct, max_drawdown_pct, win_rate, and profitable_pct at the correct scale", async () => {
    vi.mocked(api.runBatchBacktest).mockResolvedValue({
      status: "ok",
      data: {
        results: [
          {
            ticker: "AAPL",
            total_return_pct: 12.5, // already a percentage point (backend convention)
            sharpe_ratio: 1.2,
            max_drawdown_pct: -8.3, // already a percentage point
            win_rate: 0.6, // a 0-1 fraction (backend convention)
            total_trades: 10,
          },
        ],
        batch_summary: {
          profitable_count: 1,
          profitable_pct: 100, // already a percentage point
          avg_return_pct: 12.5,
          best_ticker: "AAPL",
          worst_ticker: "AAPL",
        },
        errors: [],
      },
    } as never);

    renderWithQueryClient(<BatchBacktest />);

    fireEvent.change(screen.getByPlaceholderText(/enter ticker/i), {
      target: { value: "AAPL" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText(/enter ticker/i), { key: "Enter" });

    fireEvent.click(screen.getByRole("button", { name: /run batch backtest/i }));

    await waitFor(() => {
      expect(api.runBatchBacktest).toHaveBeenCalled();
    });

    // total_return_pct=12.5 must render as "+12.50%", NOT "+0.13%" (the
    // old /100 bug) or "12.50%" without conversion issues.
    await waitFor(() => {
      expect(screen.getByText("+12.50%")).toBeInTheDocument();
    });
    // max_drawdown_pct=-8.3 must render as "-8.30%", not "-0.08%".
    expect(screen.getByText("-8.30%")).toBeInTheDocument();
    // win_rate=0.6 (a fraction) must render as "+60.00%", not "+0.60%".
    expect(screen.getByText("+60.00%")).toBeInTheDocument();
    // profitable_pct=100 must render as "+100.00%", not "+1.00%".
    expect(screen.getByText(/\+100\.00%/)).toBeInTheDocument();
  });
});
