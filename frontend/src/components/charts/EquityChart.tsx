import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { EquityCurvePoint } from "@/types";
import { formatCurrency } from "@/utils/formatters";

interface EquityChartProps {
  data: EquityCurvePoint[];
  benchmarkData?: EquityCurvePoint[];
  height?: number;
}

export function EquityChart({ data, benchmarkData, height = 350 }: EquityChartProps) {
  const merged = data.map((point, i) => ({
    date: point.date,
    portfolio: point.value,
    benchmark: benchmarkData?.[i]?.value,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={merged} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
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
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          stroke="hsl(217 33% 22%)"
          width={60}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(217 33% 17%)",
            border: "1px solid hsl(217 33% 22%)",
            borderRadius: "8px",
            fontSize: 12,
          }}
          labelFormatter={(v) => new Date(v).toLocaleDateString()}
          formatter={(value: number, name: string) => [formatCurrency(value), name === "portfolio" ? "Portfolio" : "Benchmark"]}
        />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "hsl(215 20% 55%)" }}
        />
        <Line
          type="monotone"
          dataKey="portfolio"
          stroke="hsl(217 91% 60%)"
          strokeWidth={2}
          dot={false}
          name="Portfolio"
        />
        {benchmarkData && (
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="hsl(215 20% 55%)"
            strokeWidth={1.5}
            strokeDasharray="5 5"
            dot={false}
            name="Benchmark"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
