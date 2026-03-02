import type { BacktestMetrics } from "@/types";
import { formatPercent, formatNumber } from "@/utils/formatters";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface MetricsTabsProps {
  metrics: BacktestMetrics;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-mono-numbers text-sm font-medium">{value}</span>
    </div>
  );
}

export function MetricsTabs({ metrics }: MetricsTabsProps) {
  return (
    <Tabs defaultValue="returns" className="w-full">
      <TabsList className="grid w-full grid-cols-6 bg-secondary/50">
        <TabsTrigger value="returns" className="text-xs">Returns</TabsTrigger>
        <TabsTrigger value="risk" className="text-xs">Risk</TabsTrigger>
        <TabsTrigger value="drawdown" className="text-xs">Drawdown</TabsTrigger>
        <TabsTrigger value="trades" className="text-xs">Trades</TabsTrigger>
        <TabsTrigger value="consistency" className="text-xs">Consistency</TabsTrigger>
        <TabsTrigger value="benchmark" className="text-xs">vs Benchmark</TabsTrigger>
      </TabsList>

      <TabsContent value="returns" className="mt-3">
        <MetricRow label="Total Return" value={formatPercent(metrics.returns.total_return_pct)} />
        <MetricRow label="CAGR" value={formatPercent(metrics.returns.cagr)} />
        <MetricRow label="Mean Daily Return" value={formatPercent(metrics.returns.mean_return, 4)} />
        <MetricRow label="Skewness" value={formatNumber(metrics.returns.skewness)} />
        <MetricRow label="Kurtosis" value={formatNumber(metrics.returns.kurtosis)} />
      </TabsContent>

      <TabsContent value="risk" className="mt-3">
        <MetricRow label="Volatility" value={formatPercent(metrics.risk.volatility)} />
        <MetricRow label="Sharpe Ratio" value={formatNumber(metrics.risk.sharpe_ratio)} />
        <MetricRow label="Sortino Ratio" value={formatNumber(metrics.risk.sortino_ratio)} />
        <MetricRow label="Calmar Ratio" value={formatNumber(metrics.risk.calmar_ratio)} />
        <MetricRow label="VaR (95%)" value={formatPercent(metrics.risk.var_95)} />
        <MetricRow label="CVaR (95%)" value={formatPercent(metrics.risk.cvar_95)} />
      </TabsContent>

      <TabsContent value="drawdown" className="mt-3">
        <MetricRow label="Max Drawdown" value={formatPercent(metrics.drawdown.max_drawdown)} />
        <MetricRow label="Avg Drawdown" value={formatPercent(metrics.drawdown.avg_drawdown)} />
        <MetricRow label="Max Duration (days)" value={formatNumber(metrics.drawdown.max_drawdown_duration, 0)} />
        <MetricRow label="Recovery Days" value={formatNumber(metrics.drawdown.recovery_days, 0)} />
      </TabsContent>

      <TabsContent value="trades" className="mt-3">
        <MetricRow label="Win Rate" value={formatPercent(metrics.trades.win_rate)} />
        <MetricRow label="Avg Win" value={formatPercent(metrics.trades.avg_win)} />
        <MetricRow label="Avg Loss" value={formatPercent(metrics.trades.avg_loss)} />
        <MetricRow label="Profit Factor" value={formatNumber(metrics.trades.profit_factor)} />
        <MetricRow label="Expectancy" value={formatPercent(metrics.trades.expectancy)} />
        <MetricRow label="Best Trade" value={formatPercent(metrics.trades.best_trade)} />
        <MetricRow label="Worst Trade" value={formatPercent(metrics.trades.worst_trade)} />
      </TabsContent>

      <TabsContent value="consistency" className="mt-3">
        <MetricRow label="Profitable Months" value={formatPercent(metrics.consistency.profitable_months_pct)} />
        <MetricRow label="Longest Win Streak" value={formatNumber(metrics.consistency.longest_win_streak, 0)} />
        <MetricRow label="Longest Loss Streak" value={formatNumber(metrics.consistency.longest_loss_streak, 0)} />
        <MetricRow label="Ulcer Index" value={formatNumber(metrics.consistency.ulcer_index)} />
      </TabsContent>

      <TabsContent value="benchmark" className="mt-3">
        <MetricRow label="Beta" value={formatNumber(metrics.vs_benchmark.beta)} />
        <MetricRow label="Alpha" value={formatPercent(metrics.vs_benchmark.alpha)} />
        <MetricRow label="Alpha p-value" value={formatNumber(metrics.vs_benchmark.alpha_p_value, 4)} />
        <MetricRow label="Tracking Error" value={formatPercent(metrics.vs_benchmark.tracking_error)} />
        <MetricRow label="Information Ratio" value={formatNumber(metrics.vs_benchmark.information_ratio)} />
        <MetricRow label="Up Capture" value={formatPercent(metrics.vs_benchmark.up_capture)} />
        <MetricRow label="Down Capture" value={formatPercent(metrics.vs_benchmark.down_capture)} />
      </TabsContent>
    </Tabs>
  );
}
