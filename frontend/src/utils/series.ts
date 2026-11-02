import type { EquityCurvePoint } from "@/types";

/** Percent below the running peak at each point (0 at a new high). */
export function drawdownSeries(values: number[]): number[] {
  let peak = -Infinity;
  return values.map((v) => {
    peak = Math.max(peak, v);
    return peak > 0 ? ((v - peak) / peak) * 100 : 0;
  });
}

export const CHART_RANGES = [
  { value: "1M", label: "1M" },
  { value: "3M", label: "3M" },
  { value: "1Y", label: "1Y" },
  { value: "YTD", label: "YTD" },
  { value: "All", label: "All" },
] as const;

export type ChartRange = (typeof CHART_RANGES)[number]["value"];

/** Zooms into the tail of an already-fetched curve; there is no range parameter on the API. */
export function sliceByRange(curve: EquityCurvePoint[], range: ChartRange): EquityCurvePoint[] {
  if (range === "All" || curve.length === 0) return curve;
  const cutoff = new Date(curve[curve.length - 1].date);
  if (range === "1M") cutoff.setMonth(cutoff.getMonth() - 1);
  else if (range === "3M") cutoff.setMonth(cutoff.getMonth() - 3);
  else if (range === "1Y") cutoff.setFullYear(cutoff.getFullYear() - 1);
  else cutoff.setMonth(0, 1);
  const sliced = curve.filter((p) => new Date(p.date) >= cutoff);
  return sliced.length >= 2 ? sliced : curve;
}
