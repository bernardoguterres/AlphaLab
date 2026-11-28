import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BacktestResult, EquityCurvePoint } from "@/types";
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

const DAILY_PERIODS_PER_YEAR = 252;

function rollingSharpeSeries(values: number[], periodsPerYear: number): (number | undefined)[] {
  const windowSize = Math.max(2, Math.round(periodsPerYear / 4));
  const returns = values.slice(1).map((v, i) => (values[i] === 0 ? 0 : (v - values[i]) / values[i]));
  return values.map((_, i) => {
    if (i < windowSize) return undefined;
    const window = returns.slice(i - windowSize, i);
    const mean = window.reduce((a, b) => a + b, 0) / window.length;
    const std = Math.sqrt(window.reduce((a, b) => a + (b - mean) ** 2, 0) / window.length);
    return std === 0 ? 0 : (mean / std) * Math.sqrt(periodsPerYear);
  });
}

const VIEW: Record<OverlayView, { series: (values: number[], periodsPerYear: number) => (number | undefined)[]; format: (v: number) => string; axis: (v: number) => string }> = {
  equity: { series: (v) => v, format: (v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, axis: thousands },
  drawdown: { series: drawdownSeries, format: (v) => `${v.toFixed(2)}%`, axis: (v) => `${v.toFixed(0)}%` },
  rollingSharpe: { series: rollingSharpeSeries, format: (v) => v.toFixed(2), axis: (v) => v.toFixed(1) },
};

export function OverlayEquityChart({ results, view, benchmarkLabel }: { results: Record<string, BacktestResult>; view: OverlayView; benchmarkLabel?: string }) {
  const { series, format, axis } = VIEW[view];

  const { rows, names, hasBenchmark } = useMemo(() => {
    const entries = Object.entries(results);
    const benchmarkSource = entries[0]?.[1];
    const benchmark = benchmarkSource?.benchmark?.equity_curve;
    const rowsByTime = new Map<number, Record<string, string | number | undefined>>();
    const addSeries = (name: string, curve: EquityCurvePoint[], source: BacktestResult) => {
      const points = Array.from(new Map(curve.map((point) => [Date.parse(point.date), point])))
        .sort(([left], [right]) => left - right);
      const periodsPerYear = source.metrics.assumptions?.periods_per_year ?? DAILY_PERIODS_PER_YEAR;
      const values = series(points.map(([, point]) => point.value), periodsPerYear);
      points.forEach(([time, point], index) => {
        const row = rowsByTime.get(time) ?? { date: point.date };
        row[name] = values[index];
        rowsByTime.set(time, row);
      });
    };

    for (const [name, result] of entries) {
      addSeries(name, result.equity_curve, result);
    }
    if (benchmark && benchmarkSource) {
      addSeries("benchmark", benchmark, benchmarkSource);
    }
    const rows = Array.from(rowsByTime).sort(([left], [right]) => left - right).map(([, row]) => row);
    return { rows, names: entries.map(([name]) => name), hasBenchmark: !!benchmark?.length };
  }, [results, series]);

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={rows} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis {...xAxisProps} />
        <YAxis {...yAxisProps} tickFormatter={axis} />
        <Tooltip
          {...tooltipProps}
          formatter={(value: number, key: string) => [value == null ? "-" : format(value), key === "benchmark" ? benchmarkLabel ?? "Buy & hold" : strategyName(key)]}
        />
        {hasBenchmark && <Line {...lineProps} dataKey="benchmark" stroke={BENCHMARK_COLOR} strokeWidth={1} connectNulls />}
        {names.map((name, i) => (
          <Line key={name} {...lineProps} dataKey={name} stroke={SERIES_COLORS[i % SERIES_COLORS.length]} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
