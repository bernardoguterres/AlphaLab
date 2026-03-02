import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { EquityCurvePoint } from "@/types";

interface DrawdownChartProps {
  equityCurve: EquityCurvePoint[];
  height?: number;
}

export function DrawdownChart({ equityCurve, height = 200 }: DrawdownChartProps) {
  let peak = 0;
  const data = equityCurve.map((point) => {
    if (point.value > peak) peak = point.value;
    const drawdown = peak > 0 ? ((point.value - peak) / peak) * 100 : 0;
    return { date: point.date, drawdown };
  });

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 22%)" />
        <XAxis
          dataKey="date"
          tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }}
          tickFormatter={(v) => new Date(v).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
          stroke="hsl(217 33% 22%)"
          minTickGap={40}
        />
        <YAxis
          tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }}
          tickFormatter={(v) => `${v.toFixed(0)}%`}
          stroke="hsl(217 33% 22%)"
          width={50}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(217 33% 17%)",
            border: "1px solid hsl(217 33% 22%)",
            borderRadius: "8px",
            fontSize: 12,
          }}
          labelFormatter={(v) => new Date(v).toLocaleDateString()}
          formatter={(value: number) => [`${value.toFixed(2)}%`, "Drawdown"]}
        />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="hsl(0 84% 60%)"
          fill="hsl(0 84% 60% / 0.2)"
          strokeWidth={1.5}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
