import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import Backtest from "./Backtest";
import * as api from "@/services/api";

vi.mock("@/services/api", async () => ({
  ...await vi.importActual<typeof api>("@/services/api"),
  fetchData: vi.fn(),
  runBacktest: vi.fn(),
}));

vi.mock("@/components/forms/RunFields", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/components/forms/RunFields")>(),
  IntervalSelect: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <select aria-label="Bar interval" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="1d">Daily</option>
      <option value="1wk">Weekly</option>
    </select>
  ),
}));

it("runs with the selected interval and hides scores from a different interval", async () => {
  vi.mocked(api.fetchData).mockImplementation(async ([ticker]) => ({
    status: "ok",
    errors: [],
    data: { [ticker]: { records: 100, quality_score: 0.95 } },
  }));
  vi.mocked(api.runBacktest).mockRejectedValue(new Error("Stop after capturing the request"));

  render(<Backtest />);
  fireEvent.click(screen.getByRole("button", { name: "Fetch and score data" }));
  await screen.findByText("95% quality");
  fireEvent.change(screen.getByRole("combobox", { name: "Bar interval" }), { target: { value: "1wk" } });
  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));

  await waitFor(() => expect(api.runBacktest).toHaveBeenCalledWith(expect.objectContaining({ interval: "1wk" })));
  expect(screen.queryByText("95% quality")).not.toBeInTheDocument();
});
