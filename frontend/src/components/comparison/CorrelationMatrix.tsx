import { useMemo } from "react";
import type { BacktestResult } from "@/types";
import { cn } from "@/lib/utils";
import { formatNumber } from "@/utils/formatters";

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

  const getColorStyle = (value: number): React.CSSProperties => {
    if (value > -0.2 && value < 0.2) return { backgroundColor: "hsl(var(--secondary))", color: "hsl(var(--muted-foreground))" };
    const intensity = Math.min(Math.abs(value), 1);
    const alpha = 0.15 + intensity * 0.7;
    return {
      backgroundColor: `hsl(var(--primary) / ${value > 0 ? alpha : alpha * 0.5})`,
      color: alpha > 0.5 && value > 0 ? "hsl(var(--primary-foreground))" : "hsl(var(--foreground))",
    };
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
      <div className="overflow-x-auto rounded-lg border border-border/60">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              <th className="border border-border/50 px-2 py-1.5 bg-secondary/30"></th>
              {strategies.map((s) => (
                <th key={s} className="border border-border/50 px-2 py-1.5 text-center label-caps bg-secondary/30 min-w-[80px]">
                  {s.replace("_", " ").slice(0, 10)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {strategies.map((stratI, i) => (
              <tr key={stratI}>
                <td className="border border-border/50 px-2 py-1.5 font-medium text-left bg-secondary/30 label-caps">
                  {stratI.replace("_", " ").slice(0, 10)}
                </td>
                {strategies.map((stratJ, j) => {
                  const value = matrix[i][j];
                  return (
                    <td
                      key={stratJ}
                      className="border border-border/50 px-2 py-1.5 text-center font-mono-numbers font-medium"
                      style={getColorStyle(value)}
                      title={`Correlation: ${formatNumber(value, 3)}`}
                    >
                      {formatNumber(value, 2)}
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
          <div className="px-2 py-1 rounded text-[10px]" style={getColorStyle(-1)}>-1</div>
          <div className="px-2 py-1 rounded text-[10px]" style={getColorStyle(0)}>0</div>
          <div className="px-2 py-1 rounded text-[10px]" style={getColorStyle(1)}>+1</div>
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
