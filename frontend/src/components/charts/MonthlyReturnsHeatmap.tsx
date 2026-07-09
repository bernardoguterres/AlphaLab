import { useMemo } from "react";
import type { EquityCurvePoint } from "@/types";
import { cn } from "@/lib/utils";

interface MonthlyReturnsHeatmapProps {
  equityCurve: EquityCurvePoint[];
}

interface MonthlyReturn {
  year: number;
  month: number;
  return: number;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function MonthlyReturnsHeatmap({ equityCurve }: MonthlyReturnsHeatmapProps) {
  const { monthlyReturns, yearlyReturns, years } = useMemo(() => {
    if (!equityCurve || equityCurve.length === 0) {
      return { monthlyReturns: new Map(), yearlyReturns: new Map(), years: [] };
    }

    const returns = new Map<string, number>();
    const yearly = new Map<number, number[]>();
    const yearSet = new Set<number>();

    // Calculate monthly returns
    let monthStart = 0;
    for (let i = 1; i < equityCurve.length; i++) {
      const curr = new Date(equityCurve[i].date);
      const prev = new Date(equityCurve[i - 1].date);

      // New month detected
      if (curr.getMonth() !== prev.getMonth() || curr.getFullYear() !== prev.getFullYear()) {
        const year = prev.getFullYear();
        const month = prev.getMonth();
        const startValue = equityCurve[monthStart].value;
        const endValue = equityCurve[i - 1].value;
        const monthlyReturn = ((endValue - startValue) / startValue) * 100;

        const key = `${year}-${month}`;
        returns.set(key, monthlyReturn);
        yearSet.add(year);

        if (!yearly.has(year)) {
          yearly.set(year, []);
        }
        yearly.get(year)!.push(monthlyReturn);

        monthStart = i;
      }
    }

    // Handle last month
    if (monthStart < equityCurve.length - 1) {
      const lastDate = new Date(equityCurve[equityCurve.length - 1].date);
      const year = lastDate.getFullYear();
      const month = lastDate.getMonth();
      const startValue = equityCurve[monthStart].value;
      const endValue = equityCurve[equityCurve.length - 1].value;
      const monthlyReturn = ((endValue - startValue) / startValue) * 100;

      const key = `${year}-${month}`;
      returns.set(key, monthlyReturn);
      yearSet.add(year);

      if (!yearly.has(year)) {
        yearly.set(year, []);
      }
      yearly.get(year)!.push(monthlyReturn);
    }

    // Calculate yearly returns
    const yearlyReturnsMap = new Map<number, number>();
    yearly.forEach((monthReturns, year) => {
      // Compound monthly returns to get yearly return
      const yearlyReturn = monthReturns.reduce((acc, r) => acc * (1 + r / 100), 1) - 1;
      yearlyReturnsMap.set(year, yearlyReturn * 100);
    });

    return {
      monthlyReturns: returns,
      yearlyReturns: yearlyReturnsMap,
      years: Array.from(yearSet).sort(),
    };
  }, [equityCurve]);

  const getColorStyle = (value: number): React.CSSProperties => {
    const intensity = Math.min(Math.abs(value) / 10, 1); // 0 -> 0.15, 10%+ -> 0.85 opacity
    const alpha = 0.15 + intensity * 0.7;
    if (value === 0) return { backgroundColor: "hsl(var(--secondary))", color: "hsl(var(--muted-foreground))" };
    return {
      backgroundColor: `hsl(var(--${value > 0 ? "gain" : "loss"}) / ${alpha})`,
      color: alpha > 0.5 ? "hsl(var(--foreground))" : `hsl(var(--${value > 0 ? "gain" : "loss"}))`,
    };
  };

  if (years.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
        No data available for monthly returns
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border/60">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="sticky left-0 bg-secondary/30 border border-border/50 px-2 py-1.5 text-left label-caps">
              Year
            </th>
            {MONTHS.map((month) => (
              <th key={month} className="border border-border/50 px-2 py-1.5 text-center label-caps min-w-[60px]">
                {month}
              </th>
            ))}
            <th className="border border-border/50 px-2 py-1.5 text-center label-caps bg-secondary/30 min-w-[70px]">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => (
            <tr key={year}>
              <td className="sticky left-0 bg-card border border-border/50 px-2 py-1.5 font-semibold">
                {year}
              </td>
              {MONTHS.map((_, monthIdx) => {
                const key = `${year}-${monthIdx}`;
                const value = monthlyReturns.get(key);
                if (value === undefined) {
                  return (
                    <td key={monthIdx} className="border border-border/50 px-2 py-1.5 text-center bg-secondary/10">
                      <span className="text-muted-foreground/50">-</span>
                    </td>
                  );
                }
                return (
                  <td
                    key={monthIdx}
                    className="border border-border/50 px-2 py-1.5 text-center font-mono-numbers font-medium transition-colors"
                    style={getColorStyle(value)}
                    title={`${MONTHS[monthIdx]} ${year}: ${value.toFixed(2)}%`}
                  >
                    {value.toFixed(1)}%
                  </td>
                );
              })}
              <td
                className={cn(
                  "border border-border/50 px-2 py-1.5 text-center font-mono-numbers font-bold bg-secondary/30",
                  yearlyReturns.get(year)! >= 0 ? "text-gain" : "text-loss"
                )}
              >
                {yearlyReturns.get(year)!.toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div className="py-3 flex items-center justify-center gap-2 text-xs border-t border-border/50">
        <span className="text-muted-foreground">Color scale:</span>
        <div className="flex gap-1">
          <div className="px-2 py-1 rounded" style={getColorStyle(-12)}>{"< -10%"}</div>
          <div className="px-2 py-1 rounded" style={getColorStyle(-5)}>-5%</div>
          <div className="px-2 py-1 rounded" style={getColorStyle(-2)}>-2%</div>
          <div className="px-2 py-1 rounded" style={getColorStyle(0)}>0%</div>
          <div className="px-2 py-1 rounded" style={getColorStyle(2)}>+2%</div>
          <div className="px-2 py-1 rounded" style={getColorStyle(5)}>+5%</div>
          <div className="px-2 py-1 rounded" style={getColorStyle(12)}>{"> +10%"}</div>
        </div>
      </div>
    </div>
  );
}
