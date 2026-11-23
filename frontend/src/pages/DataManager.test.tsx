import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import DataManager from "@/pages/DataManager";
import { formatFetchError } from "@/types";

// Exact shape POST /api/data/fetch returns for a ticker it can't fetch
// (backend/alphalab/api/blueprints/data.py): errors are {ticker, error}
// objects. Passing one to toast.error made React throw "Objects are not valid
// as a React child" and the whole app unmounted (B11, Nov 2026 audit).
vi.mock("@/services/api", () => ({
  errorMessage: (e: unknown) => String(e),
  getAvailableData: async () => [],
  fetchData: async () => ({
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
