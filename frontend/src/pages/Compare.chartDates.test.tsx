import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "@/App";
import type { EquityCurvePoint } from "@/types";

const { request, plot } = vi.hoisted(() => ({ request: vi.fn(), plot: vi.fn() }));

vi.mock("axios", async (importOriginal) => {
  const actual = await importOriginal<typeof import("axios")>();
  return {
    ...actual,
    default: {
      ...actual.default,
      create: (config: Parameters<typeof actual.default.create>[0]) =>
        actual.default.create({ ...config, adapter: request }),
    },
  };
});

vi.mock("recharts", async (importOriginal) => ({
  ...await importOriginal<typeof import("recharts")>(),
  ResponsiveContainer: ({ children }: React.PropsWithChildren) => children,
  LineChart: ({ data }: { data: Record<string, unknown>[] }) => {
    plot(data);
    return <div data-testid="chart" />;
  },
}));

function point(date: string, value: number): EquityCurvePoint {
  return { date: new Date(date).toUTCString(), value };
}

function result(curve: EquityCurvePoint[], benchmark = curve, periodsPerYear?: number) {
  return {
    ticker: "SPY",
    total_return_pct: 10,
    total_trades: 1,
    equity_curve: curve,
    benchmark: { total_return_pct: 3, equity_curve: benchmark },
    metrics: {
      risk: { sharpe_ratio: 1 },
      drawdown: { max_drawdown_pct: -1 },
      trades: { win_rate: 0.6, profit_factor: 2 },
      assumptions: periodsPerYear === undefined ? undefined : { periods_per_year: periodsPerYear },
    },
  };
}

const originalScrollIntoView = Element.prototype.scrollIntoView;

afterEach(() => {
  Element.prototype.scrollIntoView = originalScrollIntoView;
  request.mockReset();
  plot.mockReset();
});

async function runComparison(data: Record<string, ReturnType<typeof result>>) {
  request.mockImplementation(async (config) => ({
    config,
    status: 200,
    data: config.url === "/compare"
      ? { status: "ok", data }
      : config.url === "/data/available" ? { data: [] } : { status: "ok", version: "test" },
  }));
  Element.prototype.scrollIntoView = vi.fn();
  window.history.replaceState({}, "", "/compare");
  render(<App />);
  fireEvent.keyDown(screen.getByRole("combobox", { name: "Add a strategy" }), { key: "Enter" });
  fireEvent.click(await screen.findByRole("option", { name: /Greenblatt/ }));
  fireEvent.click(screen.getByRole("button", { name: "Run comparison" }));
  await screen.findByTestId("chart");
  expect(request).toHaveBeenCalledWith(expect.objectContaining({
    url: "/compare",
    data: expect.stringContaining('"greenblatt_weekly"'),
  }));
}

function chartRows() {
  return plot.mock.lastCall?.[0] as Array<{ date: string } & Record<string, string | number | undefined>>;
}

it("plots sparse comparison and benchmark observations on their actual dates", async () => {
  const movingAverage = [
    point("2024-01-05", 100_000),
    point("2024-01-08", 101_000),
    point("2024-01-09", 102_000),
  ];
  const relativeStrength = [point("2024-01-05", 100_000), point("2024-01-09", 99_000)];
  const weekly = [point("2024-01-05", 100_000), point("2024-01-12", 105_000)];
  const benchmark = [point("2024-01-05", 100_000), point("2024-01-10", 103_000)];
  await runComparison({
    ma_crossover: result(movingAverage, benchmark),
    rsi_mean_reversion: result(relativeStrength),
    greenblatt_weekly: result(weekly),
  });

  const observations = () => chartRows().map((row) => [
    new Date(row.date).toISOString().slice(0, 10),
    row.ma_crossover ?? null,
    row.rsi_mean_reversion ?? null,
    row.greenblatt_weekly ?? null,
    row.benchmark ?? null,
  ]);
  expect(observations()).toEqual([
    ["2024-01-05", 100_000, 100_000, 100_000, 100_000],
    ["2024-01-08", 101_000, null, null, null],
    ["2024-01-09", 102_000, 99_000, null, null],
    ["2024-01-10", null, null, null, 103_000],
    ["2024-01-12", null, null, 105_000, null],
  ]);

  fireEvent.click(screen.getByRole("button", { name: "Drawdown" }));
  expect(observations()[2]).toEqual(["2024-01-09", 0, -1, null, null]);
});

it("uses a quarter of weekly returns and the weekly annualization for rolling Sharpe", async () => {
  const returns = Array.from({ length: 63 }, (_, i) => i % 2 ? -0.01 : 0.02);
  const start = Date.UTC(2023, 0, 6);
  let value = 100_000;
  const curve = Array.from({ length: returns.length + 1 }, (_, i) => {
    if (i) value *= 1 + returns[i - 1];
    return point(new Date(start + i * 7 * 86_400_000).toISOString(), value);
  });
  await runComparison({
    greenblatt_weekly: result(curve, curve, 52),
    ma_crossover: result(curve),
  });

  fireEvent.click(screen.getByRole("button", { name: "Rolling Sharpe" }));
  const quarter = returns.slice(-13);
  const mean = quarter.reduce((sum, r) => sum + r, 0) / quarter.length;
  const std = Math.sqrt(quarter.reduce((sum, r) => sum + (r - mean) ** 2, 0) / quarter.length);
  const expected = (mean / std) * Math.sqrt(52);
  const rows = chartRows();
  expect(rows[12].greenblatt_weekly).toBeUndefined();
  expect(rows[13].greenblatt_weekly).toBeTypeOf("number");
  expect(rows[13].ma_crossover).toBeUndefined();
  expect(rows.at(-1)?.greenblatt_weekly).toBeCloseTo(expected, 6);
  expect(rows.at(-1)?.benchmark).toBeCloseTo(expected, 6);
});
