import { useMemo } from "react";
import type { EquityCurvePoint } from "@/types";
import { Table, Td, Th } from "@/components/ui/data-table";
import { cn } from "@/lib/utils";
import { pnlColor } from "@/utils/formatters";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Return from each month's first to last point, keyed "year-month". */
function monthlyReturns(curve: EquityCurvePoint[]): Map<string, number> {
  const bounds = new Map<string, { first: number; last: number }>();
  for (const point of curve) {
    const d = new Date(point.date);
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    const month = bounds.get(key);
    if (month) month.last = point.value;
    else bounds.set(key, { first: point.value, last: point.value });
  }
  return new Map([...bounds].map(([key, { first, last }]) => [key, ((last - first) / first) * 100]));
}

/** Background tint scaled by magnitude, saturating at ±10%. */
function cellTint(value: number): React.CSSProperties {
  const alpha = Math.min(Math.abs(value) / 10, 1) * 0.3;
  return { backgroundColor: `hsl(var(--${value >= 0 ? "gain" : "loss"}) / ${alpha})` };
}

export function MonthlyReturnsHeatmap({ equityCurve }: { equityCurve: EquityCurvePoint[] }) {
  const { returns, years } = useMemo(() => {
    const returns = monthlyReturns(equityCurve);
    const years = [...new Set([...returns.keys()].map((k) => Number(k.split("-")[0])))].sort();
    return { returns, years };
  }, [equityCurve]);

  if (years.length === 0) {
    return <p className="py-8 text-[13px] text-muted-foreground">No data for monthly returns.</p>;
  }

  return (
    <Table>
      <thead>
        <tr>
          <Th>Year</Th>
          {MONTHS.map((m) => (
            <Th key={m} align="right">
              {m}
            </Th>
          ))}
          <Th align="right">Year</Th>
        </tr>
      </thead>
      <tbody>
        {years.map((year) => {
          const months = MONTHS.map((_, i) => returns.get(`${year}-${i}`));
          const total = (months.reduce<number>((acc, r) => acc * (1 + (r ?? 0) / 100), 1) - 1) * 100;
          return (
            <tr key={year}>
              <Td num>{year}</Td>
              {months.map((value, i) => (
                <Td
                  key={i}
                  num
                  align="right"
                  style={value === undefined ? undefined : cellTint(value)}
                  title={value === undefined ? undefined : `${MONTHS[i]} ${year}: ${value.toFixed(2)}%`}
                >
                  {value === undefined ? <span className="text-muted-foreground">·</span> : value.toFixed(1)}
                </Td>
              ))}
              <Td num align="right" className={cn("font-medium", pnlColor(total))}>
                {total.toFixed(1)}%
              </Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
