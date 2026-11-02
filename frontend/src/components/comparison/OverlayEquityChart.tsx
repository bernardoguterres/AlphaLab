import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BacktestResult } from "@/types";
import { drawdownSeries } from "@/utils/series";
import { strategyName } from "@/utils/strategies";
import {
  BENCHMARK_COLOR,
  SERIES_COLORS,
  gridProps,
  lineProps,
  thousands,
  tooltipProps,
  xAxisProps,
  yAxisProps,
} from "@/components/charts/chartTheme";

export type OverlayView = "equity" | "drawdown" | "rollingSharpe";

// Trading days in the rolling Sharpe window, about one quarter: long enough
// to be meaningful on multi-year runs, short enough to still move.
const ROLLING_WINDOW = 63;

function rollingSharpeSeries(values: number[]): (number | undefined)[] {
  const returns = values.slice(1).map((v, i) => (values[i] === 0 ? 0 : (v - values[i]) / values[i]));
  return values.map((_, i) => {
    if (i < ROLLING_WINDOW) return undefined;
    const window = returns.slice(i - ROLLING_WINDOW, i);
    const mean = window.reduce((a, b) => a + b, 0) / window.length;
    const std = Math.sqrt(window.reduce((a, b) => a + (b - mean) ** 2, 0) / window.length);
    return std === 0 ? 0 : (mean / std) * Math.sqrt(252);
  });
}

const VIEW: Record<OverlayView, { series: (values: number[]) => (number | undefined)[]; format: (v: number) => string; axis: (v: number) => string }> = {
  equity: { series: (v) => v, format: (v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, axis: thousands },
  drawdown: { series: drawdownSeries, format: (v) => `${v.toFixed(2)}%`, axis: (v) => `${v.toFixed(0)}%` },
  rollingSharpe: { series: rollingSharpeSeries, format: (v) => v.toFixed(2), axis: (v) => v.toFixed(1) },
};

export function OverlayEquityChart({ results, view }: { results: Record<string, BacktestResult>; view: OverlayView }) {
  const { series, format, axis } = VIEW[view];

  const { rows, names, hasBenchmark } = useMemo(() => {
    const entries = Object.entries(results);
    const benchmark = entries[0]?.[1].benchmark?.equity_curve;
    const perStrategy = entries.map(([, r]) => series(r.equity_curve.map((p) => p.value)));
    const benchSeries = benchmark ? series(benchmark.map((p) => p.value)) : null;
    const rows = (entries[0]?.[1].equity_curve ?? []).map((point, idx) => ({
      date: point.date,
      benchmark: benchSeries?.[idx],
      ...Object.fromEntries(entries.map(([name], s) => [name, perStrategy[s][idx]])),
    }));
    return { rows, names: entries.map(([name]) => name), hasBenchmark: !!benchSeries };
  }, [results, series]);

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={rows} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis {...xAxisProps} />
        <YAxis {...yAxisProps} tickFormatter={axis} />
        <Tooltip
          {...tooltipProps}
          formatter={(value: number, key: string) => [value == null ? "-" : format(value), key === "benchmark" ? "Buy & hold" : strategyName(key)]}
        />
        {hasBenchmark && <Line {...lineProps} dataKey="benchmark" stroke={BENCHMARK_COLOR} strokeWidth={1} connectNulls />}
        {names.map((name, i) => (
          <Line key={name} {...lineProps} dataKey={name} stroke={SERIES_COLORS[i % SERIES_COLORS.length]} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
