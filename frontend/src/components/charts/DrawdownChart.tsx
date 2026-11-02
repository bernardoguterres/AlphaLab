import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EquityCurvePoint } from "@/types";
import { drawdownSeries } from "@/utils/series";
import { gridProps, tooltipProps, xAxisProps, yAxisProps } from "./chartTheme";

export function DrawdownChart({ equityCurve, height = 220 }: { equityCurve: EquityCurvePoint[]; height?: number }) {
  const drawdowns = drawdownSeries(equityCurve.map((p) => p.value));
  const rows = equityCurve.map((p, i) => ({ date: p.date, drawdown: drawdowns[i] }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis {...xAxisProps} />
        <YAxis {...yAxisProps} domain={["auto", 0]} tickFormatter={(v: number) => `${v.toFixed(Math.abs(v) < 5 ? 1 : 0)}%`} />
        <Tooltip {...tooltipProps} formatter={(value: number) => [`${value.toFixed(2)}%`, "Drawdown"]} />
        <Area
          type="linear"
          dataKey="drawdown"
          stroke="hsl(var(--loss))"
          fill="hsl(var(--loss) / 0.12)"
          strokeWidth={1}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
