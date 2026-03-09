import { useMemo } from "react";
import type { BacktestResult } from "@/types";
import { formatPercent, formatNumber, strategyDisplayName } from "@/utils/formatters";
import { Trophy, TrendingUp, TrendingDown, Target, Percent } from "lucide-react";
import { cn } from "@/lib/utils";

interface BestStrategySummaryProps {
  results: Record<string, BacktestResult>;
}

interface Winner {
  strategy: string;
  value: number;
}

export function BestStrategySummary({ results }: BestStrategySummaryProps) {
  const winners = useMemo(() => {
    const entries = Object.entries(results);
    if (entries.length === 0) return null;

    const findBest = (metric: (r: BacktestResult) => number): Winner => {
      let best = entries[0];
      for (const entry of entries) {
        if (metric(entry[1]) > metric(best[1])) {
          best = entry;
        }
      }
      return { strategy: best[0], value: metric(best[1]) };
    };

    const findBestDrawdown = (): Winner => {
      // For drawdown, "best" means closest to 0 (least negative)
      let best = entries[0];
      for (const entry of entries) {
        const curr = entry[1].metrics.drawdown.max_drawdown;
        const bestVal = best[1].metrics.drawdown.max_drawdown;
        if (curr > bestVal) {
          // Less negative is better
          best = entry;
        }
      }
      return { strategy: best[0], value: best[1].metrics.drawdown.max_drawdown };
    };

    const bestSharpe = findBest((r) => r.metrics.risk.sharpe_ratio);
    const bestReturn = findBest((r) => r.total_return_pct);
    const bestDrawdown = findBestDrawdown();
    const bestWinRate = findBest((r) => r.metrics.trades.win_rate);

    // Overall recommendation: highest Sharpe ratio
    const recommended = bestSharpe;

    return {
      sharpe: bestSharpe,
      return: bestReturn,
      drawdown: bestDrawdown,
      winRate: bestWinRate,
      recommended,
    };
  }, [results]);

  if (!winners) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
        No results to compare
      </div>
    );
  }

  return (
    <div className="card-elevated p-5 space-y-4">
      {/* Overall Recommendation */}
      <div className="flex items-center gap-3 pb-4 border-b">
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-amber-500/20">
          <Trophy className="h-5 w-5 text-amber-500" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold">Recommended Strategy</h3>
          <p className="text-lg font-bold text-primary">
            {strategyDisplayName(winners.recommended.strategy)}
          </p>
          <p className="text-xs text-muted-foreground">
            Based on highest Sharpe ratio ({formatNumber(winners.recommended.value)})
          </p>
        </div>
      </div>

      {/* Best on Each Metric */}
      <div className="grid grid-cols-2 gap-3">
        {/* Best Sharpe */}
        <div className="flex items-start gap-2 p-3 bg-muted/30 rounded-lg">
          <Target className="h-4 w-4 text-primary shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Best Sharpe</p>
            <p className="text-sm font-semibold truncate">
              {strategyDisplayName(winners.sharpe.strategy)}
            </p>
            <p className="text-xs font-mono-numbers text-primary">
              {formatNumber(winners.sharpe.value)}
            </p>
          </div>
        </div>

        {/* Best Return */}
        <div className={cn(
          "flex items-start gap-2 p-3 rounded-lg",
          winners.return.value >= 0 ? "bg-green-500/10" : "bg-red-500/10"
        )}>
          {winners.return.value >= 0 ? (
            <TrendingUp className="h-4 w-4 text-gain shrink-0 mt-0.5" />
          ) : (
            <TrendingDown className="h-4 w-4 text-loss shrink-0 mt-0.5" />
          )}
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Best Return</p>
            <p className="text-sm font-semibold truncate">
              {strategyDisplayName(winners.return.strategy)}
            </p>
            <p className={cn(
              "text-xs font-mono-numbers",
              winners.return.value >= 0 ? "text-gain" : "text-loss"
            )}>
              {formatPercent(winners.return.value)}
            </p>
          </div>
        </div>

        {/* Best Drawdown */}
        <div className="flex items-start gap-2 p-3 bg-muted/30 rounded-lg">
          <TrendingDown className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Best Drawdown</p>
            <p className="text-sm font-semibold truncate">
              {strategyDisplayName(winners.drawdown.strategy)}
            </p>
            <p className="text-xs font-mono-numbers text-loss">
              {formatPercent(winners.drawdown.value)}
            </p>
          </div>
        </div>

        {/* Best Win Rate */}
        <div className="flex items-start gap-2 p-3 bg-muted/30 rounded-lg">
          <Percent className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Best Win Rate</p>
            <p className="text-sm font-semibold truncate">
              {strategyDisplayName(winners.winRate.strategy)}
            </p>
            <p className="text-xs font-mono-numbers text-primary">
              {formatPercent(winners.winRate.value * 100)}
            </p>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="pt-3 border-t">
        <p className="text-[10px] text-muted-foreground italic">
          Based on historical backtest. Past performance does not guarantee future results.
        </p>
      </div>
    </div>
  );
}
