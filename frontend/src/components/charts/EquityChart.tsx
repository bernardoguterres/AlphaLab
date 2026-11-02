import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EquityCurvePoint } from "@/types";
import { formatCurrency } from "@/utils/formatters";
import { BENCHMARK_COLOR, SERIES_COLORS, gridProps, lineProps, thousands, tooltipProps, xAxisProps, yAxisProps } from "./chartTheme";

interface EquityChartProps {
  data: EquityCurvePoint[];
  benchmarkData?: EquityCurvePoint[];
  height?: number;
}

export function EquityChart({ data, benchmarkData, height = 320 }: EquityChartProps) {
  const rows = data.map((point, i) => ({ date: point.date, portfolio: point.value, benchmark: benchmarkData?.[i]?.value }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis {...xAxisProps} />
        <YAxis {...yAxisProps} tickFormatter={thousands} />
        <Tooltip
          {...tooltipProps}
          formatter={(value: number, name: string) => [formatCurrency(value), name === "portfolio" ? "Strategy" : "Buy & hold"]}
        />
        {benchmarkData && <Line {...lineProps} dataKey="benchmark" stroke={BENCHMARK_COLOR} strokeWidth={1} />}
        <Line {...lineProps} dataKey="portfolio" stroke={SERIES_COLORS[0]} />
      </LineChart>
    </ResponsiveContainer>
  );
}
