import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import DataManager from "@/pages/DataManager";
import { formatFetchError } from "@/types";
import { fetchData, getAvailableData } from "@/services/api";

// Exact shape POST /api/data/fetch returns for a ticker it can't fetch
// (backend/alphalab/api/blueprints/data.py): errors are {ticker, error}
// objects. Passing one to toast.error made React throw "Objects are not valid
// as a React child" and the whole app unmounted (B11, Nov 2026 audit).
vi.mock("@/services/api", () => ({
  errorMessage: (e: unknown) => String(e),
  getAvailableData: vi.fn().mockResolvedValue([]),
  fetchData: vi.fn().mockResolvedValue({
    status: "ok",
    data: {},
    errors: [{ ticker: "ZZZZZ", error: "Ticker 'ZZZZZ' not found or delisted" }],
  }),
}));

test("formatFetchError renders error objects as text", () => {
  expect(formatFetchError({ ticker: "ZZZZZ", error: "not found" })).toBe("ZZZZZ: not found");
  expect(formatFetchError("plain message")).toBe("plain message");
});

test("a per-ticker fetch error shows a toast instead of unmounting the page", async () => {
  const { container } = render(
    <>
      <Toaster />
      <DataManager />
    </>,
  );
  fireEvent.change(screen.getByLabelText(/Tickers, comma-separated/), { target: { value: "ZZZZZ" } });
  await act(async () => {
    fireEvent.click(screen.getByText("Fetch"));
    await new Promise((r) => setTimeout(r, 300));
  });
  expect(container.innerHTML.length).toBeGreaterThan(0);
  expect(await screen.findByText("ZZZZZ: Ticker 'ZZZZZ' not found or delisted")).toBeInTheDocument();
});

test("fetch quality only appears on the matching cached window and interval", async () => {
  const data = { ticker: "AAPL", start_date: "2025-01-01", end_date: "2025-12-31", records: 100, last_updated: "2026-11-01" };
  vi.mocked(getAvailableData).mockResolvedValue([
    { ...data, key: "daily", interval: "1d" },
    { ...data, key: "weekly", interval: "1wk" },
    { ...data, key: "other-window", interval: "1d", start_date: "2024-01-01" },
  ]);
  vi.mocked(fetchData).mockResolvedValue({status: "ok", data: { AAPL: { quality_score: 0.75, records: 100 } }, errors: []});
  render(<DataManager />);
  const weekly = (await screen.findByText("Weekly")).closest("tr")!;
  fireEvent.click(within(weekly).getByRole("button", { name: "Refresh" }));
  expect(await within(weekly).findByText("75%")).toBeInTheDocument();
  expect(screen.getAllByText("75%")).toHaveLength(1);
});
