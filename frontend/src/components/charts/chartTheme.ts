import type { XAxisProps, YAxisProps } from "recharts";

const css = (name: string) => `hsl(var(--${name}))`;

export const SERIES_COLORS = [css("series-1"), css("series-2"), css("series-3")];
export const BENCHMARK_COLOR = css("series-benchmark");

const tick = { fill: css("muted-foreground"), fontSize: 11, fontFamily: "IBM Plex Mono" };

export const gridProps = { stroke: css("border"), vertical: false } as const;

export const xAxisProps: XAxisProps = {
  dataKey: "date",
  tick,
  tickLine: false,
  axisLine: { stroke: css("border") },
  minTickGap: 48,
  tickFormatter: (v: string) => new Date(v).toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
};

export const yAxisProps: YAxisProps = {
  tick,
  tickLine: false,
  axisLine: false,
  width: 56,
  domain: ["auto", "auto"],
};

export const tooltipProps = {
  contentStyle: {
    background: css("surface"),
    border: `1px solid ${css("border")}`,
    borderRadius: 4,
    fontSize: 12,
    fontFamily: "IBM Plex Mono",
  },
  labelStyle: { color: css("muted-foreground") },
  labelFormatter: (v: string) => new Date(v).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }),
  cursor: { stroke: css("muted-foreground"), strokeWidth: 1 },
} as const;

export const lineProps = { type: "linear", dot: false, isAnimationActive: false, strokeWidth: 1.5 } as const;

export const thousands = (v: number) => `$${(v / 1000).toFixed(0)}k`;
