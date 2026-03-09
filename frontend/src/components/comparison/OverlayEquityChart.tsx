import { useMemo } from "react";
import type { BacktestResult } from "@/types";
import { Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface OverlayEquityChartProps {
  results: Record<string, BacktestResult>;
}

// Colorblind-friendly palette
const COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea"];

export function OverlayEquityChart({ results }: OverlayEquityChartProps) {
  const { chartData, strategyNames } = useMemo(() => {
    const entries = Object.entries(results);
    if (entries.length === 0) return { chartData: [], strategyNames: [] };

    // Find common date range
    const firstResult = entries[0][1];
    const names = entries.map(([name]) => name);

    // Normalize all strategies to start at 0% (percentage returns from initial capital)
    const normalized = firstResult.equity_curve.map((point, idx) => {
      const dataPoint: Record<string, any> = { date: point.date, benchmark: 0 };

      entries.forEach(([name, result]) => {
        const equity = result.equity_curve[idx];
        if (equity) {
          const initialValue = result.equity_curve[0].value;
          const returnPct = ((equity.value - initialValue) / initialValue) * 100;
          dataPoint[name] = returnPct;
        }
      });

      // Add buy-and-hold benchmark if available
      if (firstResult.benchmark?.equity_curve[idx]) {
        const benchInitial = firstResult.benchmark.equity_curve[0].value;
        const benchCurrent = firstResult.benchmark.equity_curve[idx].value;
        dataPoint.benchmark = ((benchCurrent - benchInitial) / benchInitial) * 100;
      }

      return dataPoint;
    });

    return { chartData: normalized, strategyNames: names };
  }, [results]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          tickFormatter={(val) => new Date(val).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(val) => `${val.toFixed(0)}%`}
          label={{ value: "Return %", angle: -90, position: "insideLeft", style: { fontSize: 11 } }}
        />
        <Tooltip
          contentStyle={{ fontSize: 12 }}
          labelFormatter={(label) => new Date(label).toLocaleDateString()}
          formatter={(value: number) => `${value.toFixed(2)}%`}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />

        {/* Strategy lines */}
        {strategyNames.map((name, idx) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[idx % COLORS.length]}
            strokeWidth={2}
            dot={false}
            name={name.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          />
        ))}

        {/* Benchmark (dashed gray line) */}
        <Line
          type="monotone"
          dataKey="benchmark"
          stroke="#9ca3af"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={false}
          name="Buy & Hold"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
