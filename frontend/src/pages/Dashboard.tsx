import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useBacktestStore } from "@/stores/backtestStore";
import { MetricCard } from "@/components/metrics/MetricCard";
import { ExportButton } from "@/components/export/ExportButton";
import { formatPercent, formatNumber, strategyDisplayName, formatDate, pnlColor } from "@/utils/formatters";
import { BarChart3, Database, TrendingUp, Clock, ArrowRight, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Dashboard() {
  const navigate = useNavigate();
  const { history, cachedTickers, isBackendOnline } = useBacktestStore();

  const totalBacktests = history.length;
  const cachedCount = cachedTickers.length;
  const bestStrategy = history.length > 0
    ? history.reduce((best, curr) => curr.total_return_pct > best.total_return_pct ? curr : best)
    : null;
  const lastBacktest = history.length > 0 ? history[0] : null;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Overview of your backtesting activity</p>
        </div>
        <Button onClick={() => navigate("/backtest")} className="gap-2">
          <BarChart3 className="h-4 w-4" />
          Run New Backtest
        </Button>
      </div>

      {!isBackendOnline && (
        <div className="card-elevated p-4 flex items-center gap-3 border-loss/30">
          <AlertCircle className="h-5 w-5 text-loss shrink-0" />
          <div>
            <p className="text-sm font-medium">Backend not reachable</p>
            <p className="text-xs text-muted-foreground">Is the Flask server running on localhost:5000?</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Total Backtests"
          value={totalBacktests.toString()}
          icon={<BarChart3 className="h-4 w-4" />}
        />
        <MetricCard
          label="Cached Tickers"
          value={cachedCount.toString()}
          icon={<Database className="h-4 w-4" />}
        />
        <MetricCard
          label="Best Strategy"
          value={bestStrategy ? strategyDisplayName(bestStrategy.strategy) : "—"}
          subValue={bestStrategy ? formatPercent(bestStrategy.total_return_pct) : undefined}
          icon={<TrendingUp className="h-4 w-4" />}
          colorClass={bestStrategy && bestStrategy.total_return_pct > 0 ? "text-gain" : undefined}
        />
        <MetricCard
          label="Last Backtest"
          value={lastBacktest ? formatPercent(lastBacktest.total_return_pct) : "—"}
          subValue={lastBacktest ? `${lastBacktest.ticker} · ${strategyDisplayName(lastBacktest.strategy)}` : undefined}
          icon={<Clock className="h-4 w-4" />}
          colorClass={lastBacktest ? pnlColor(lastBacktest.total_return_pct) : undefined}
        />
      </div>

      <div className="card-elevated">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">Recent Backtests</h2>
          <span className="text-xs text-muted-foreground">{history.length} total</span>
        </div>
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <BarChart3 className="h-10 w-10 text-muted-foreground/50 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">No backtests yet</p>
            <p className="text-xs text-muted-foreground/70 mt-1">Run your first backtest to see results here</p>
            <Button variant="outline" size="sm" className="mt-4 gap-2" onClick={() => navigate("/backtest")}>
              Get Started <ArrowRight className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Date</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Ticker</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Strategy</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Return %</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Sharpe</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Max DD</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Trades</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 10).map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-border/50 hover:bg-secondary/30 cursor-pointer transition-colors"
                    onClick={() => {
                      useBacktestStore.getState().setCurrentResult(item.result);
                      navigate("/backtest");
                    }}
                  >
                    <td className="px-4 py-2 font-mono-numbers text-xs">{formatDate(item.date)}</td>
                    <td className="px-4 py-2 font-semibold">{item.ticker}</td>
                    <td className="px-4 py-2 text-muted-foreground">{strategyDisplayName(item.strategy)}</td>
                    <td className={cn("px-4 py-2 text-right font-mono-numbers font-semibold", pnlColor(item.total_return_pct))}>
                      {formatPercent(item.total_return_pct)}
                    </td>
                    <td className="px-4 py-2 text-right font-mono-numbers">{formatNumber(item.sharpe_ratio)}</td>
                    <td className="px-4 py-2 text-right font-mono-numbers text-loss">{formatPercent(item.max_drawdown)}</td>
                    <td className="px-4 py-2 text-right font-mono-numbers">{item.total_trades}</td>
                    <td className="px-4 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                      <ExportButton
                        backtestId={item.result.backtest_id || item.id}
                        strategyName={item.strategy}
                        ticker={item.ticker}
                        variant="ghost"
                        size="icon"
                        showLabel={false}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
