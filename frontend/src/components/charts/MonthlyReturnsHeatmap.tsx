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

  const getColorClass = (value: number) => {
    if (value >= 10) return "bg-green-600 text-white";
    if (value >= 5) return "bg-green-500 text-white";
    if (value >= 2) return "bg-green-400 text-white";
    if (value > 0) return "bg-green-300 text-gray-900";
    if (value === 0) return "bg-gray-200 text-gray-700";
    if (value > -2) return "bg-red-300 text-gray-900";
    if (value > -5) return "bg-red-400 text-white";
    if (value > -10) return "bg-red-500 text-white";
    return "bg-red-600 text-white";
  };

  if (years.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
        No data available for monthly returns
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="sticky left-0 bg-background border border-border px-2 py-1.5 text-left font-semibold text-muted-foreground">
              Year
            </th>
            {MONTHS.map((month) => (
              <th key={month} className="border border-border px-2 py-1.5 text-center font-medium text-muted-foreground min-w-[60px]">
                {month}
              </th>
            ))}
            <th className="border border-border px-2 py-1.5 text-center font-semibold text-muted-foreground bg-muted/50 min-w-[70px]">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => (
            <tr key={year}>
              <td className="sticky left-0 bg-background border border-border px-2 py-1.5 font-semibold">
                {year}
              </td>
              {MONTHS.map((_, monthIdx) => {
                const key = `${year}-${monthIdx}`;
                const value = monthlyReturns.get(key);
                if (value === undefined) {
                  return (
                    <td key={monthIdx} className="border border-border px-2 py-1.5 text-center bg-gray-100">
                      <span className="text-muted-foreground">—</span>
                    </td>
                  );
                }
                return (
                  <td
                    key={monthIdx}
                    className={cn(
                      "border border-border px-2 py-1.5 text-center font-mono-numbers font-medium transition-colors",
                      getColorClass(value)
                    )}
                    title={`${MONTHS[monthIdx]} ${year}: ${value.toFixed(2)}%`}
                  >
                    {value.toFixed(1)}%
                  </td>
                );
              })}
              <td
                className={cn(
                  "border border-border px-2 py-1.5 text-center font-mono-numbers font-bold bg-muted/50",
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
      <div className="mt-4 flex items-center justify-center gap-2 text-xs">
        <span className="text-muted-foreground">Color scale:</span>
        <div className="flex gap-1">
          <div className="bg-red-600 text-white px-2 py-1 rounded">{"< -10%"}</div>
          <div className="bg-red-500 text-white px-2 py-1 rounded">-5%</div>
          <div className="bg-red-300 text-gray-900 px-2 py-1 rounded">-2%</div>
          <div className="bg-gray-200 text-gray-700 px-2 py-1 rounded">0%</div>
          <div className="bg-green-300 text-gray-900 px-2 py-1 rounded">+2%</div>
          <div className="bg-green-500 text-white px-2 py-1 rounded">+5%</div>
          <div className="bg-green-600 text-white px-2 py-1 rounded">{"> +10%"}</div>
        </div>
      </div>
    </div>
  );
}
