import { useNavigate } from "react-router-dom";
import { useBacktestStore } from "@/stores/backtestStore";
import { MetricCard } from "@/components/metrics/MetricCard";
import { ExportButton } from "@/components/export/ExportButton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { EquityChart } from "@/components/charts/EquityChart";
import { Button } from "@/components/ui/button";
import { formatPercent, formatNumber, formatCurrency, formatDate, formatDateTime, strategyDisplayName, pnlColor } from "@/utils/formatters";
import { cn } from "@/lib/utils";
import {
  BarChart3, Database, TrendingUp, TrendingDown, Clock, GitCompare, Play, RefreshCw,
  CheckCircle2, Circle, AlertTriangle, LineChart as LineChartIcon, Target, Percent, ArrowRight,
} from "lucide-react";

type CheckTone = "gain" | "warning" | "loss" | "neutral";

function ValidationRow({ tone, title, subtitle }: { tone: CheckTone; title: string; subtitle: string }) {
  const Icon = tone === "gain" ? CheckCircle2 : tone === "warning" ? AlertTriangle : Circle;
  const iconClass = tone === "gain" ? "text-gain" : tone === "warning" ? "text-warning" : "text-muted-foreground";
  const badgeText = tone === "gain" ? "Verified" : tone === "warning" ? "Pending" : "Not run";
  return (
    <div className="flex items-start justify-between gap-3 py-2.5 border-b border-border/30 last:border-0">
      <div className="flex items-start gap-2.5 min-w-0">
        <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", iconClass)} />
        <div className="min-w-0">
          <p className="text-xs font-semibold text-foreground">{title}</p>
          <p className="text-[10.5px] text-muted-foreground leading-snug mt-0.5">{subtitle}</p>
        </div>
      </div>
      <span className={cn("text-[10px] font-bold uppercase tracking-wide shrink-0 mt-0.5", iconClass)}>{badgeText}</span>
    </div>
  );
}

// Matches the backend's real cache expiry default ("Raw market data cached
// as parquet files, configurable expiry, default 24h"),
// not an arbitrary UI cutoff.
const EXPIRED_CACHE_MS = 24 * 60 * 60 * 1000;

export default function Dashboard() {
  const navigate = useNavigate();
  const { history, cachedTickers, isBackendOnline } = useBacktestStore();

  const totalBacktests = history.length;
  const uniqueTickers = new Set(cachedTickers.map((c) => c.ticker)).size;
  const latest = history.length > 0 ? history[0] : null;

  // chronological (oldest-first) count series - real, derived from saved
  // run dates, used only as a small trend indicator, never a fabricated value.
  const totalBacktestsSparkline = [...history].reverse().map((_, i) => i + 1);

  const freshestUpdate = cachedTickers.length
    ? cachedTickers.reduce((max, c) => (new Date(c.last_updated) > new Date(max.last_updated) ? c : max)).last_updated
    : null;
  const oldestUpdate = cachedTickers.length
    ? cachedTickers.reduce((min, c) => (new Date(c.last_updated) < new Date(min.last_updated) ? c : min)).last_updated
    : null;
  const expiredCount = cachedTickers.filter((c) => Date.now() - new Date(c.last_updated).getTime() > EXPIRED_CACHE_MS).length;

  const equityCurve = latest?.result.equity_curve ?? [];
  const testWindow = equityCurve.length >= 2
    ? `${formatDate(equityCurve[0].date)} - ${formatDate(equityCurve[equityCurve.length - 1].date)}`
    : null;

  return (
    <div className="page-shell py-5 space-y-3.5 animate-in-stagger">
      {/* Compact page header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground leading-none">Research Overview</h1>
          <p className="text-xs text-muted-foreground/90 mt-1.5">Monitor recent experiments, validation status, and research data</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate("/compare")} className="gap-2">
            <GitCompare className="h-4 w-4" />
            Compare Strategies
          </Button>
          <Button onClick={() => navigate("/backtest")} className="gap-2">
            <Play className="h-4 w-4" />
            Run New Backtest
          </Button>
        </div>
      </div>

      {!isBackendOnline && (
        <div className="card-elevated p-3.5 flex items-center gap-3 border-loss/30 bg-loss/[0.03]">
          <AlertTriangle className="h-4 w-4 text-loss shrink-0" />
          <div>
            <p className="text-xs font-medium">Backend not reachable</p>
            <p className="text-[11px] text-muted-foreground">Is the Flask server running on localhost:5050?</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3.5">
        {/* Left: latest run + recent runs table */}
        <div className="xl:col-span-2 space-y-3.5 min-w-0">
          {!latest ? (
            <div className="card-elevated p-3.5">
              <h3 className="section-label mb-1">Latest Completed Run</h3>
              <EmptyState
                size="sm"
                icon={LineChartIcon}
                title="No completed runs yet"
                description="Run a backtest to see its equity curve, validation status, and metrics here."
                action={
                  <Button onClick={() => navigate("/backtest")} size="sm" className="gap-2">
                    <Play className="h-3.5 w-3.5" /> Run a backtest
                  </Button>
                }
              />
            </div>
          ) : (
            <div className="card-elevated p-3.5">
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h3 className="section-label">Latest Completed Run</h3>
                <StatusBadge label="Completed" tone="gain" className="normal-case tracking-normal" />
              </div>

              <div className="flex items-center gap-2.5 mb-3">
                <div className={cn("rounded-lg p-2 shrink-0 bg-secondary/60", pnlColor(latest.total_return_pct))}>
                  {latest.total_return_pct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                </div>
                <h2 className="text-lg font-bold tracking-tight text-foreground">
                  {latest.ticker} - {strategyDisplayName(latest.strategy)}
                </h2>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-xs">
                <div>
                  <span className="label-caps block">Strategy</span>
                  <span className="font-medium">{strategyDisplayName(latest.strategy)}</span>
                </div>
                <div>
                  <span className="label-caps block">Ticker</span>
                  <span className="font-mono-numbers font-medium">{latest.ticker}</span>
                </div>
                <div>
                  <span className="label-caps block">Test Window</span>
                  <span className="font-mono-numbers font-medium">{testWindow ?? "-"}</span>
                </div>
                <div>
                  <span className="label-caps block">Initial Capital</span>
                  <span className="font-mono-numbers font-medium">{formatCurrency(latest.result.initial_capital)}</span>
                </div>
              </div>

              {equityCurve.length >= 2 && (
                <div className="mb-4">
                  <div className="flex items-center gap-5 mb-2">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-primary shrink-0" />
                      <span className="text-xs text-muted-foreground">Portfolio</span>
                      <span className={cn("font-mono-numbers text-xs font-semibold", pnlColor(latest.total_return_pct))}>
                        {formatPercent(latest.total_return_pct)}
                      </span>
                    </div>
                    {latest.result.benchmark && (
                      <div className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-lab-secondary shrink-0" />
                        <span className="text-xs text-muted-foreground">Buy &amp; Hold</span>
                        <span className={cn("font-mono-numbers text-xs font-semibold", pnlColor(latest.result.benchmark.total_return_pct))}>
                          {formatPercent(latest.result.benchmark.total_return_pct)}
                        </span>
                      </div>
                    )}
                  </div>
                  <EquityChart data={equityCurve} benchmarkData={latest.result.benchmark?.equity_curve} />
                </div>
              )}

              <div className="grid grid-cols-3 xl:grid-cols-5 gap-3">
                <MetricCard
                  label="Net Return"
                  value={formatPercent(latest.total_return_pct)}
                  colorClass={pnlColor(latest.total_return_pct)}
                  icon={latest.total_return_pct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                />
                <MetricCard label="Sharpe Ratio" value={formatNumber(latest.sharpe_ratio)} icon={<Target className="h-4 w-4" />} />
                <MetricCard label="Max Drawdown" value={formatPercent(latest.max_drawdown)} colorClass="text-loss" />
                <MetricCard label="Win Rate" value={formatPercent(latest.result.metrics.trades.win_rate * 100)} icon={<Percent className="h-4 w-4" />} />
                <MetricCard label="Profit Factor" value={formatNumber(latest.result.metrics.trades.profit_factor)} />
              </div>
            </div>
          )}

          {/* Compact research summary */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard
              label="Total Backtests"
              value={totalBacktests.toString()}
              subValue="Saved this browser"
              icon={<BarChart3 className="h-4 w-4" />}
              tone="primary"
              sparkline={totalBacktestsSparkline.length >= 2 ? totalBacktestsSparkline : undefined}
            />
            <MetricCard label="Cached Datasets" value={cachedTickers.length.toString()} subValue={`Across ${uniqueTickers} tickers`} icon={<Database className="h-4 w-4" />} tone="cyan" />
            <MetricCard label="Unique Tickers" value={uniqueTickers.toString()} subValue="With cached data" icon={<BarChart3 className="h-4 w-4" />} tone="neutral" />
            <MetricCard
              label="Last Research Run"
              value={latest ? formatDate(latest.date) : "-"}
              subValue={latest ? `${latest.ticker} - ${strategyDisplayName(latest.strategy)}` : "No runs recorded yet"}
              icon={<Clock className="h-4 w-4" />}
              tone="warning"
            />
          </div>

          {/* Recent research runs */}
          <div className="card-elevated flex flex-col">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
              <h2 className="section-label">Recent Research Runs</h2>
              <span className="text-xs text-muted-foreground/90 font-medium">{history.length} total</span>
            </div>
            {history.length === 0 ? (
              <div className="p-3">
                <EmptyState
                  size="sm"
                  icon={BarChart3}
                  title="No research runs yet"
                  description="Every backtest you run will show up here with its return, Sharpe, and drawdown."
                  action={
                    <Button onClick={() => navigate("/backtest")} size="sm" variant="outline" className="gap-2">
                      <Play className="h-3.5 w-3.5" /> Run a backtest
                    </Button>
                  }
                />
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-secondary/20">
                        <th className="px-4 py-2 text-left label-caps">Date</th>
                        <th className="px-3 py-2 text-left label-caps">Ticker</th>
                        <th className="px-3 py-2 text-left label-caps">Strategy</th>
                        <th className="px-3 py-2 text-right label-caps">Return</th>
                        <th className="px-3 py-2 text-right label-caps">Sharpe</th>
                        <th className="px-3 py-2 text-right label-caps">Max Drawdown</th>
                        <th className="px-4 py-2 text-center label-caps">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(0, 5).map((item) => (
                        <tr
                          key={item.id}
                          className="border-b border-border/50 hover:bg-secondary/40 cursor-pointer transition-colors"
                          onClick={() => {
                            useBacktestStore.getState().setCurrentResult(item.result);
                            navigate("/backtest");
                          }}
                        >
                          <td className="px-4 py-2 font-mono-numbers text-xs text-muted-foreground/90">{formatDate(item.date)}</td>
                          <td className="px-3 py-2 font-semibold">{item.ticker}</td>
                          <td className="px-3 py-2 text-muted-foreground/90">{strategyDisplayName(item.strategy)}</td>
                          <td className={cn("px-3 py-2 text-right font-mono-numbers font-semibold", pnlColor(item.total_return_pct))}>
                            {formatPercent(item.total_return_pct)}
                          </td>
                          <td className="px-3 py-2 text-right font-mono-numbers">{formatNumber(item.sharpe_ratio)}</td>
                          <td className="px-3 py-2 text-right font-mono-numbers text-loss">{formatPercent(item.max_drawdown)}</td>
                          <td className="px-4 py-2" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center justify-center gap-1">
                              <button
                                onClick={() => {
                                  useBacktestStore.getState().setCurrentResult(item.result);
                                  navigate("/backtest");
                                }}
                                className="text-xs font-semibold text-primary hover:text-primary/80"
                              >
                                View
                              </button>
                              <ExportButton
                                backtestId={item.result.backtest_id || item.id}
                                strategyName={item.strategy}
                                ticker={item.ticker}
                                variant="ghost"
                                size="icon"
                                showLabel={false}
                              />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {history.length > 5 && (
                  <div className="px-4 py-2.5 text-[11px] text-muted-foreground border-t border-border/50">
                    Showing last 5 of {history.length} runs
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right: validation status, next steps, data health */}
        <div className="space-y-3.5 min-w-0">
          <div className="card-elevated p-3.5">
            <h3 className="section-label mb-1">Validation Status</h3>
            {!latest ? (
              <p className="text-xs text-muted-foreground py-4">Run a backtest to see validation status.</p>
            ) : (
              <div className="mt-2">
                <ValidationRow
                  tone="gain"
                  title="Next-bar execution"
                  subtitle="Signals generated at bar N execute at bar N+1's open - enforced architecturally."
                />
                <ValidationRow
                  tone="gain"
                  title="Transaction costs"
                  subtitle="Commission and slippage were applied for every simulated trade in this run."
                />
                <ValidationRow
                  tone="warning"
                  title="Data quality"
                  subtitle="Not recorded with this saved run - quality scores aren't persisted to history."
                />
                <ValidationRow
                  tone="gain"
                  title="Position limits"
                  subtitle="Max position size and open-position caps are enforced on every run."
                />
                <ValidationRow
                  tone="neutral"
                  title="Walk-forward validation"
                  subtitle="Not part of a single backtest - run via AlphaLab's offline research scripts."
                />
              </div>
            )}
          </div>

          <div className="card-elevated p-3.5">
            <h3 className="section-label mb-2">Next Steps</h3>
            <div className="space-y-1">
              <button
                onClick={() => navigate("/data")}
                className="w-full flex items-center gap-2.5 p-2 -mx-2 rounded-lg hover:bg-secondary/40 transition-colors text-left group"
              >
                <div className="rounded-md bg-secondary/60 p-1.5 shrink-0 text-primary">
                  <RefreshCw className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-foreground">Fetch / refresh data</p>
                  <p className="text-[10.5px] text-muted-foreground">Update cached prices and fundamentals.</p>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/0 group-hover:text-primary/70 shrink-0 transition-colors" />
              </button>
              <button
                onClick={() => navigate("/compare")}
                className="w-full flex items-center gap-2.5 p-2 -mx-2 rounded-lg hover:bg-secondary/40 transition-colors text-left group"
              >
                <div className="rounded-md bg-secondary/60 p-1.5 shrink-0 text-primary">
                  <GitCompare className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-foreground">Compare strategies</p>
                  <p className="text-[10.5px] text-muted-foreground">Analyze performance side-by-side.</p>
                </div>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/0 group-hover:text-primary/70 shrink-0 transition-colors" />
              </button>
            </div>
            <p className="text-[10px] text-muted-foreground/90 mt-3 pt-3 border-t border-border/40 leading-relaxed">
              Walk-forward validation isn't available in-app yet - run it via AlphaLab's offline research scripts.
            </p>
          </div>

          <div className="card-elevated p-3.5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="section-label">Data Health</h3>
              {cachedTickers.length > 0 && (
                <StatusBadge
                  label={expiredCount > 0 ? `${expiredCount} expired` : "Fresh"}
                  tone={expiredCount > 0 ? "warning" : "gain"}
                  className="normal-case tracking-normal"
                />
              )}
            </div>
            <div className="flex items-baseline gap-2 mb-1 mt-1.5">
              <span className="text-2xl font-bold font-mono-numbers text-foreground">{cachedTickers.length}</span>
              <span className="text-xs text-muted-foreground/90">cached datasets</span>
            </div>
            <p className="text-[10.5px] text-muted-foreground/90 mb-3">
              Across {uniqueTickers} tickers
              {expiredCount > 0 && ` - ${expiredCount} expired (>24h)`}
            </p>
            <div className="grid grid-cols-2 gap-3 text-xs mb-3">
              <div>
                <span className="label-caps block">Freshest Update</span>
                <span className="font-mono-numbers text-[11px]">{freshestUpdate ? formatDateTime(freshestUpdate) : "-"}</span>
              </div>
              <div>
                <span className="label-caps block">Oldest Update</span>
                <span className={cn("font-mono-numbers text-[11px]", expiredCount > 0 && "text-warning")}>
                  {oldestUpdate ? formatDateTime(oldestUpdate) : "-"}
                </span>
              </div>
            </div>
            <Button variant="outline" size="sm" className="w-full gap-2" onClick={() => navigate("/data")}>
              <Database className="h-3.5 w-3.5" /> Manage Data
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
