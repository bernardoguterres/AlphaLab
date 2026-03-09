import { useMemo } from "react";
import type { BacktestResult } from "@/types";
import { cn } from "@/lib/utils";

interface CorrelationMatrixProps {
  results: Record<string, BacktestResult>;
}

export function CorrelationMatrix({ results }: CorrelationMatrixProps) {
  const { matrix, strategies } = useMemo(() => {
    const entries = Object.entries(results);
    if (entries.length < 2) return { matrix: [], strategies: [] };

    const strats = entries.map(([name]) => name);

    // Extract daily returns for each strategy
    const returns: Record<string, number[]> = {};
    entries.forEach(([name, result]) => {
      const dailyReturns: number[] = [];
      for (let i = 1; i < result.equity_curve.length; i++) {
        const prev = result.equity_curve[i - 1].value;
        const curr = result.equity_curve[i].value;
        dailyReturns.push((curr - prev) / prev);
      }
      returns[name] = dailyReturns;
    });

    // Calculate pairwise correlation
    const correlations: number[][] = [];
    for (let i = 0; i < strats.length; i++) {
      const row: number[] = [];
      for (let j = 0; j < strats.length; j++) {
        if (i === j) {
          row.push(1.0); // Self-correlation is always 1
        } else {
          const corr = calculateCorrelation(returns[strats[i]], returns[strats[j]]);
          row.push(corr);
        }
      }
      correlations.push(row);
    }

    return { matrix: correlations, strategies: strats };
  }, [results]);

  const getColorClass = (value: number) => {
    if (value >= 0.8) return "bg-blue-600 text-white";
    if (value >= 0.5) return "bg-blue-500 text-white";
    if (value >= 0.2) return "bg-blue-400 text-white";
    if (value > -0.2) return "bg-gray-200 text-gray-900";
    if (value > -0.5) return "bg-red-400 text-white";
    if (value > -0.8) return "bg-red-500 text-white";
    return "bg-red-600 text-white";
  };

  if (strategies.length < 2) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
        Need at least 2 strategies to show correlation
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              <th className="border border-border px-2 py-1.5"></th>
              {strategies.map((s) => (
                <th key={s} className="border border-border px-2 py-1.5 text-center font-medium min-w-[80px]">
                  {s.replace("_", " ").slice(0, 10)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {strategies.map((stratI, i) => (
              <tr key={stratI}>
                <td className="border border-border px-2 py-1.5 font-medium text-left">
                  {stratI.replace("_", " ").slice(0, 10)}
                </td>
                {strategies.map((stratJ, j) => {
                  const value = matrix[i][j];
                  return (
                    <td
                      key={stratJ}
                      className={cn(
                        "border border-border px-2 py-1.5 text-center font-mono-numbers font-medium",
                        getColorClass(value)
                      )}
                      title={`Correlation: ${value.toFixed(3)}`}
                    >
                      {value.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
        <span>Correlation:</span>
        <div className="flex gap-1">
          <div className="bg-red-600 text-white px-2 py-1 rounded text-[10px]">-1</div>
          <div className="bg-gray-200 text-gray-900 px-2 py-1 rounded text-[10px]">0</div>
          <div className="bg-blue-600 text-white px-2 py-1 rounded text-[10px]">+1</div>
        </div>
        <span className="ml-2">Lower correlation = better diversification</span>
      </div>
    </div>
  );
}

// Helper: Calculate Pearson correlation coefficient
function calculateCorrelation(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length);
  if (n === 0) return 0;

  const meanX = x.slice(0, n).reduce((a, b) => a + b, 0) / n;
  const meanY = y.slice(0, n).reduce((a, b) => a + b, 0) / n;

  let num = 0,
    denX = 0,
    denY = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX;
    const dy = y[i] - meanY;
    num += dx * dy;
    denX += dx * dx;
    denY += dy * dy;
  }

  if (denX === 0 || denY === 0) return 0;
  return num / Math.sqrt(denX * denY);
}
