import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TradeTable } from "@/components/charts/TradeTable";
import type { Trade } from "@/types";

// Regression test: TradeTable's `page` state was never reset when the
// `trades` prop changed. Paging into page 2 on one backtest, then loading a
// different backtest result with fewer trades, left `page` pointing past
// the end of the new array. `paged` became an empty slice, and since
// `totalPages` shrank too, the pagination controls (the only way to click
// back to page 0) disappeared - the table silently rendered with zero rows.

function makeTrades(n: number): Trade[] {
  return Array.from({ length: n }, (_, i) => ({
    entry_date: `2020-01-${String(i + 1).padStart(2, "0")}`,
    exit_date: `2020-02-${String(i + 1).padStart(2, "0")}`,
    action: "BUY" as const,
    shares: 10,
    entry_price: 100,
    exit_price: 110,
    pnl: 100,
    pnl_pct: 10,
  }));
}

describe("TradeTable", () => {
  it("resets to page 0 when the trades prop changes to a shorter list", () => {
    const { rerender } = render(<TradeTable trades={makeTrades(20)} />);

    fireEvent.click(screen.getByText("2"));
    expect(screen.getAllByRole("row")).toHaveLength(6); // header + 5 trades on page 2

    rerender(<TradeTable trades={makeTrades(3)} />);

    expect(screen.getAllByRole("row")).toHaveLength(4); // header + 3 trades, not empty
  });
});
