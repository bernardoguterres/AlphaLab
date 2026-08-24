import { useMemo } from "react";
import type { BacktestResult } from "@/types";
import { Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export type OverlayView = "equity" | "drawdown" | "rollingSharpe";

interface OverlayEquityChartProps {
  results: Record<string, BacktestResult>;
  view?: OverlayView;
  colors: string[];
}

// Trading-day window for the rolling Sharpe view (~1 quarter) - chosen so
// there's enough history to compute a meaningful rolling stat on typical
// multi-year backtest windows, short enough to still show variation.
const ROLLING_WINDOW = 63;

function drawdownSeries(values: number[]): number[] {
  let peak = -Infinity;
  return values.map((v) => {
    peak = Math.max(peak, v);
    return peak > 0 ? ((v - peak) / peak) * 100 : 0;
  });
}

function rollingSharpeSeries(values: number[]): (number | undefined)[] {
  const returns = values.slice(1).map((v, i) => (values[i] === 0 ? 0 : (v - values[i]) / values[i]));
  const out: (number | undefined)[] = [undefined]; // no return defined for the first bar
  for (let i = 0; i < returns.length; i++) {
    if (i + 1 < ROLLING_WINDOW) {
      out.push(undefined);
      continue;
    }
    const window = returns.slice(i + 1 - ROLLING_WINDOW, i + 1);
    const mean = window.reduce((a, b) => a + b, 0) / window.length;
    const variance = window.reduce((a, b) => a + (b - mean) ** 2, 0) / window.length;
    const std = Math.sqrt(variance);
    out.push(std === 0 ? 0 : (mean / std) * Math.sqrt(252));
  }
  return out;
}

export function OverlayEquityChart({ results, view = "equity", colors }: OverlayEquityChartProps) {
  const { chartData, strategyNames, hasBenchmark } = useMemo(() => {
    const entries = Object.entries(results);
    if (entries.length === 0) return { chartData: [], strategyNames: [], hasBenchmark: false };

    const firstResult = entries[0][1];
    const names = entries.map(([name]) => name);
    const dates = firstResult.equity_curve.map((p) => p.date);
    const benchCurve = firstResult.benchmark?.equity_curve;

    const seriesFor = (values: number[]) =>
      view === "drawdown" ? drawdownSeries(values) : view === "rollingSharpe" ? rollingSharpeSeries(values) : values;

    const perStrategy: Record<string, (number | undefined)[]> = {};
    entries.forEach(([name, result]) => {
      perStrategy[name] = seriesFor(result.equity_curve.map((p) => p.value));
    });
    const benchSeries = benchCurve ? seriesFor(benchCurve.map((p) => p.value)) : null;

    const rows = dates.map((date, idx) => {
      const row: Record<string, string | number | undefined> = { date };
      names.forEach((name) => { row[name] = perStrategy[name][idx]; });
      if (benchSeries) row.benchmark = benchSeries[idx];
      return row;
    });

    return { chartData: rows, strategyNames: names, hasBenchmark: !!benchSeries };
  }, [results, view]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
        No data available
      </div>
    );
  }

  const yTickFormatter =
    view === "equity" ? (v: number) => `$${(v / 1000).toFixed(0)}k` : view === "drawdown" ? (v: number) => `${v.toFixed(0)}%` : (v: number) => v.toFixed(1);
  const tooltipFormatter =
    view === "equity"
      ? (v: number) => (v == null ? "-" : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`)
      : view === "drawdown"
      ? (v: number) => (v == null ? "-" : `${v.toFixed(2)}%`)
      : (v: number) => (v == null ? "-" : v.toFixed(2));

  return (
    <ResponsiveContainer width="100%" height={360}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 22%)" />
        <XAxis
          dataKey="date"
          tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }}
          stroke="hsl(217 33% 22%)"
          tickFormatter={(val) => new Date(val).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
          minTickGap={40}
        />
        <YAxis tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} stroke="hsl(217 33% 22%)" tickFormatter={yTickFormatter} width={64} />
        <Tooltip
          contentStyle={{ backgroundColor: "hsl(217 33% 17%)", border: "1px solid hsl(217 33% 22%)", borderRadius: "8px", fontSize: 12 }}
          labelFormatter={(label) => new Date(label).toLocaleDateString()}
          formatter={(value: number) => tooltipFormatter(value)}
        />

        {strategyNames.map((name, idx) => (
          <Line key={name} type="monotone" dataKey={name} stroke={colors[idx % colors.length]} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        ))}

        {hasBenchmark && (
          <Line type="monotone" dataKey="benchmark" stroke="#9ca3af" strokeWidth={2} strokeDasharray="5 5" dot={false} connectNulls isAnimationActive={false} />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
