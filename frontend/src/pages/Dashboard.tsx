import { useNavigate } from "react-router-dom";
import { useBacktestStore } from "@/stores/backtestStore";
import { MetricCard } from "@/components/metrics/MetricCard";
import { ExportButton } from "@/components/export/ExportButton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { ActionCard } from "@/components/ui/action-card";
import { StrategyCard } from "@/components/strategy/StrategyCard";
import { SparklinePlaceholder } from "@/components/ui/sparkline-placeholder";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { formatPercent, formatNumber, strategyDisplayName, formatDate, pnlColor } from "@/utils/formatters";
import { STRATEGY_META } from "@/utils/strategyMeta";
import { STRATEGY_INFO } from "@/types";
import type { StrategyType } from "@/types";
import {
  BarChart3,
  Database,
  TrendingUp,
  Clock,
  ArrowRight,
  AlertCircle,
  GitCompare,
  Settings as SettingsIcon,
  Sparkles,
  LayoutGrid,
  Activity,
} from "lucide-react";
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

  // history is stored newest-first; reverse for chronological series.
  const chronological = [...history].reverse();
  const totalBacktestsSparkline = chronological.map((_, i) => i + 1);
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const runsThisWeek = history.filter((h) => {
    const t = new Date(h.date).getTime();
    return !isNaN(t) && t >= sevenDaysAgo;
  }).length;

  const strategiesUsed = new Set(history.map((h) => h.strategy));
  const strategyCounts = (Object.keys(STRATEGY_INFO) as StrategyType[]).map((key) => {
    const runs = history.filter((h) => h.strategy === key);
    const bestReturn = runs.length > 0 ? Math.max(...runs.map((r) => r.total_return_pct)) : undefined;
    const avgSharpe = runs.length > 0 ? runs.reduce((sum, r) => sum + r.sharpe_ratio, 0) / runs.length : undefined;
    const sparklineData = [...runs].reverse().map((r) => r.total_return_pct);
    return {
      key,
      name: STRATEGY_INFO[key].name,
      count: runs.length,
      bestReturn,
      avgSharpe,
      sparklineData,
    };
  });

  const checklist = [
    { label: "Fetch market data", hint: "Cache OHLCV data for at least one ticker", done: cachedCount > 0 },
    { label: "Run your first backtest", hint: "Test a strategy against historical data", done: totalBacktests > 0 },
    { label: "Compare 2+ strategies", hint: "Find your best performer side-by-side", done: strategiesUsed.size >= 2 },
    { label: "Configure notifications", hint: "Wire up Telegram/Alpaca alerts", done: false },
  ];
  const checklistDone = checklist.filter((c) => c.done).length;
  const checklistPct = Math.round((checklistDone / checklist.length) * 100);

  const quickActions = [
    { label: "Run Backtest", description: "Test a strategy on any ticker", icon: BarChart3, to: "/backtest" },
    { label: "Compare Strategies", description: "Side-by-side performance", icon: GitCompare, to: "/compare" },
    { label: "Manage Data", description: "Fetch & cache market data", icon: Database, to: "/data" },
    { label: "Settings", description: "Notifications & connections", icon: SettingsIcon, to: "/settings" },
  ];

  return (
    <div className="page-shell py-8 space-y-7 animate-in-stagger">
      {/* Hero / command section */}
      <div className="hero-panel px-6 py-8 sm:px-9 sm:py-9">
        <div className="glow-blob h-48 w-48 -bottom-20 left-1/3 opacity-20 bg-lab-secondary" />
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-8 relative">
          {/* Left: identity + CTAs */}
          <div className="flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
                </span>
                <span className="text-[11px] font-semibold text-primary uppercase tracking-widest">Research Command Center</span>
              </div>
              <h1 className="font-display text-3xl sm:text-[2.6rem] font-bold tracking-tight gradient-text leading-[1.08]">Dashboard</h1>
              <p className="text-[15px] text-muted-foreground/90 mt-3 leading-relaxed max-w-lg">
                Backtest, validate, and export algorithmic strategies before they go live in AlphaLive.
              </p>
              <div className="flex items-center gap-2 mt-5 flex-wrap">
                <StatusBadge
                  label={isBackendOnline ? "Backend Online" : "Backend Offline"}
                  tone={isBackendOnline ? "gain" : "loss"}
                  dot
                  pulse={isBackendOnline}
                  className="normal-case tracking-normal"
                />
                <StatusBadge label={`${cachedCount} tickers cached`} tone="primary" className="normal-case tracking-normal" />
                <StatusBadge label={`${totalBacktests} backtests run`} tone="neutral" className="normal-case tracking-normal" />
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap w-full sm:w-auto mt-6">
              <Button variant="ghost" onClick={() => navigate("/data")} className="gap-2 flex-1 sm:flex-none text-muted-foreground hover:text-foreground">
                <Database className="h-4 w-4" />
                Manage Data
              </Button>
              <Button variant="outline" onClick={() => navigate("/compare")} className="gap-2 flex-1 sm:flex-none">
                <GitCompare className="h-4 w-4" />
                Compare Strategies
              </Button>
              <Button onClick={() => navigate("/backtest")} size="lg" className="gap-2 flex-1 sm:flex-none">
                <Sparkles className="h-4 w-4" />
                Run New Backtest
              </Button>
            </div>
          </div>

          {/* Right: real featured-strategy preview, or an empty placeholder when no runs exist yet */}
          {bestStrategy ? (
            <div className="rounded-xl border border-border/70 bg-card/70 backdrop-blur-sm relative overflow-hidden surface-glow">
              <div className="flex items-start justify-between p-5 pb-0">
                <div className="min-w-0">
                  <p className="label-caps text-foreground/60 truncate">
                    Best Performer · {bestStrategy.ticker} · {strategyDisplayName(bestStrategy.strategy)}
                  </p>
                  <p className={cn("text-[28px] leading-tight font-bold font-mono-numbers mt-1.5", pnlColor(bestStrategy.total_return_pct))}>
                    {formatPercent(bestStrategy.total_return_pct)}
                  </p>
                </div>
                <div className={cn("flex items-center gap-1 text-xs font-semibold rounded-full px-2.5 py-1 shrink-0 bg-secondary/60", pnlColor(bestStrategy.sharpe_ratio))}>
                  <TrendingUp className="h-3 w-3" />
                  Sharpe {formatNumber(bestStrategy.sharpe_ratio)}
                </div>
              </div>
              {bestStrategy.result.equity_curve.length >= 2 && (
                <div className="chart-grid-bg mt-3 mx-2 rounded-lg">
                  <SparklinePlaceholder
                    data={bestStrategy.result.equity_curve.map((p) => p.value)}
                    className={cn("w-full h-24", pnlColor(bestStrategy.total_return_pct))}
                    strokeClassName={pnlColor(bestStrategy.total_return_pct)}
                    height={96}
                  />
                </div>
              )}
              <div className="grid grid-cols-3 gap-2 px-5 py-4 border-t border-border/60 bg-secondary/20">
                <div>
                  <p className="label-caps">CAGR</p>
                  <p className={cn("text-sm font-mono-numbers font-semibold mt-0.5", pnlColor(bestStrategy.result.metrics.returns.cagr_pct))}>
                    {formatPercent(bestStrategy.result.metrics.returns.cagr_pct)}
                  </p>
                </div>
                <div className="border-x border-border/50 px-2">
                  <p className="label-caps">Max DD</p>
                  <p className="text-sm font-mono-numbers font-semibold text-loss mt-0.5">{formatPercent(bestStrategy.max_drawdown)}</p>
                </div>
                <div>
                  <p className="label-caps">Win Rate</p>
                  <p className="text-sm font-mono-numbers font-semibold mt-0.5">{formatPercent(bestStrategy.result.metrics.trades.win_rate)}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border/70 bg-card/30 flex flex-col items-center justify-center text-center p-8 min-h-[200px]">
              <div className="rounded-xl bg-secondary/60 p-3 mb-3 ring-1 ring-border/60">
                <TrendingUp className="h-5 w-5 text-primary/80" />
              </div>
              <p className="text-sm font-semibold">Your top strategy will be featured here</p>
              <p className="text-xs text-muted-foreground/80 mt-1 max-w-xs">
                Run a backtest to see its equity curve and key metrics spotlighted in this panel.
              </p>
            </div>
          )}
        </div>
      </div>

      {!isBackendOnline && (
        <div className="card-elevated p-4 flex items-center gap-3 border-loss/30 bg-loss/[0.03]">
          <AlertCircle className="h-5 w-5 text-loss shrink-0" />
          <div>
            <p className="text-sm font-medium">Backend not reachable</p>
            <p className="text-xs text-muted-foreground">Is the Flask server running on localhost:5050?</p>
          </div>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Backtests"
          value={totalBacktests.toString()}
          icon={<BarChart3 className="h-4 w-4" />}
          tone="primary"
          trend={runsThisWeek > 0 ? { direction: "up", label: `+${runsThisWeek} this week` } : undefined}
          sparkline={totalBacktestsSparkline.length >= 2 ? totalBacktestsSparkline : undefined}
          accent
        />
        <MetricCard
          label="Cached Tickers"
          value={cachedCount.toString()}
          icon={<Database className="h-4 w-4" />}
          tone="cyan"
          accent
        />
        <MetricCard
          label="Best Strategy"
          value={bestStrategy ? strategyDisplayName(bestStrategy.strategy) : "-"}
          subValue={bestStrategy ? formatPercent(bestStrategy.total_return_pct) : "Run a backtest to populate"}
          icon={<TrendingUp className="h-4 w-4" />}
          colorClass={bestStrategy && bestStrategy.total_return_pct > 0 ? "text-gain" : undefined}
          tone="gain"
          accent
        />
        <MetricCard
          label="Last Backtest"
          value={lastBacktest ? formatPercent(lastBacktest.total_return_pct) : "-"}
          subValue={lastBacktest ? `${lastBacktest.ticker} · ${strategyDisplayName(lastBacktest.strategy)}` : "No runs recorded yet"}
          icon={<Clock className="h-4 w-4" />}
          colorClass={lastBacktest ? pnlColor(lastBacktest.total_return_pct) : undefined}
          tone="warning"
          accent
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-stretch">
        {/* Recent Activity - takes 2 cols */}
        <div className="xl:col-span-2 card-elevated flex flex-col">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              <Activity className="h-3.5 w-3.5 text-primary" />
              <h2 className="text-[15px] font-bold tracking-tight">Recent Activity</h2>
            </div>
            <span className="text-xs text-muted-foreground font-medium">{history.length} total</span>
          </div>
          {history.length === 0 ? (
            <div className="px-5 flex-1 flex flex-col justify-center">
              <EmptyState
                icon={BarChart3}
                title="No backtests yet"
                description="This is where your performance history, equity curves, and detailed metrics will live once you run a backtest."
                preview={
                  <div className="rounded-lg border border-border/50 bg-secondary/20 p-4 opacity-60">
                    <div className="flex items-end gap-1.5 h-16 mb-3">
                      {[40, 55, 35, 60, 48, 72, 58, 80, 65, 90, 75, 95].map((h, i) => (
                        <Skeleton key={i} className="flex-1 rounded-sm" style={{ height: `${h}%` }} />
                      ))}
                    </div>
                    <div className="grid grid-cols-4 gap-3">
                      <Skeleton className="h-3 rounded" />
                      <Skeleton className="h-3 rounded" />
                      <Skeleton className="h-3 rounded" />
                      <Skeleton className="h-3 rounded" />
                    </div>
                  </div>
                }
              />
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pb-6">
                {quickActions.slice(0, 3).map((action) => (
                  <ActionCard
                    key={action.to}
                    icon={action.icon}
                    label={action.label}
                    description={action.description}
                    onClick={() => navigate(action.to)}
                    compact
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/20">
                    <th className="px-5 py-2.5 text-left label-caps">Date</th>
                    <th className="px-4 py-2.5 text-left label-caps">Ticker</th>
                    <th className="px-4 py-2.5 text-left label-caps">Strategy</th>
                    <th className="px-4 py-2.5 text-left label-caps hidden sm:table-cell">Trend</th>
                    <th className="px-4 py-2.5 text-right label-caps">Return %</th>
                    <th className="px-4 py-2.5 text-right label-caps">Sharpe</th>
                    <th className="px-5 py-2.5 text-center label-caps">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 8).map((item) => {
                    const positive = item.total_return_pct >= 0;
                    const equitySeries = item.result.equity_curve?.map((p) => p.value) ?? [];
                    return (
                      <tr
                        key={item.id}
                        className="relative border-b border-border/50 hover:bg-secondary/40 cursor-pointer transition-colors group"
                        onClick={() => {
                          useBacktestStore.getState().setCurrentResult(item.result);
                          navigate("/backtest");
                        }}
                      >
                        <td className="px-5 py-3 relative">
                          <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-primary scale-y-0 group-hover:scale-y-100 transition-transform origin-center" />
                          <span className="font-mono-numbers text-xs text-muted-foreground">{formatDate(item.date)}</span>
                        </td>
                        <td className="px-4 py-3 font-semibold">{item.ticker}</td>
                        <td className="px-4 py-3 text-muted-foreground">{strategyDisplayName(item.strategy)}</td>
                        <td className="px-4 py-3 hidden sm:table-cell">
                          {equitySeries.length >= 2 ? (
                            <div className={cn("inline-flex items-center rounded-md px-2 py-1", positive ? "bg-gain/[0.07]" : "bg-loss/[0.07]")}>
                              <SparklinePlaceholder
                                data={equitySeries}
                                height={24}
                                className={cn("w-16 h-6", positive ? "text-gain" : "text-loss")}
                                strokeClassName={positive ? "text-gain" : "text-loss"}
                                fill={false}
                              />
                            </div>
                          ) : (
                            <span className="text-[10px] text-muted-foreground/40">-</span>
                          )}
                        </td>
                        <td className={cn("px-4 py-3 text-right font-mono-numbers font-semibold", pnlColor(item.total_return_pct))}>
                          {formatPercent(item.total_return_pct)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono-numbers">{formatNumber(item.sharpe_ratio)}</td>
                        <td className="px-5 py-3 text-center" onClick={(e) => e.stopPropagation()}>
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
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right rail: Quick Actions + Readiness checklist */}
        <div className="space-y-5">
          <div className="card-elevated p-4">
            <h2 className="section-label mb-3">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-2.5">
              {quickActions.map((action) => (
                <ActionCard
                  key={action.to}
                  icon={action.icon}
                  label={action.label}
                  description={action.description}
                  onClick={() => navigate(action.to)}
                />
              ))}
            </div>
          </div>

          <div className="card-elevated p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="section-label">Readiness Checklist</h2>
              <span className="text-[11px] font-mono-numbers text-muted-foreground">{checklistDone}/{checklist.length}</span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary/60 overflow-hidden mb-4">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-lab-secondary transition-all duration-500"
                style={{ width: `${checklistPct}%` }}
              />
            </div>
            <div className="space-y-3">
              {checklist.map((item, i) => (
                <div key={item.label} className="flex items-start gap-2.5">
                  <span
                    className={cn(
                      "flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold shrink-0 mt-0.5",
                      item.done ? "bg-gain/15 text-gain" : "bg-secondary text-muted-foreground border border-border"
                    )}
                  >
                    {item.done ? "✓" : i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className={cn("text-xs font-medium", item.done ? "text-foreground" : "text-muted-foreground")}>
                      {item.label}
                    </p>
                    <p className="text-[10px] text-muted-foreground/60">{item.hint}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card-elevated p-4">
            <h2 className="section-label mb-3">Data Status</h2>
            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Backend</span>
                <StatusBadge
                  label={isBackendOnline ? "Online" : "Offline"}
                  tone={isBackendOnline ? "gain" : "loss"}
                  dot
                  pulse={isBackendOnline}
                />
              </div>
              <Separator className="bg-border/50" />
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Cached tickers</span>
                <span className="font-mono-numbers font-semibold">{cachedCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Saved backtests</span>
                <span className="font-mono-numbers font-semibold">{totalBacktests}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Strategy overview */}
      <div className="card-elevated p-5 sm:p-6">
        <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 text-primary p-2">
              <LayoutGrid className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-tight">Strategy Library</h2>
              <p className="text-[11px] text-muted-foreground/70">Research modules available for backtesting</p>
            </div>
          </div>
          <button
            onClick={() => navigate("/backtest")}
            className="flex items-center gap-1 text-[11px] font-semibold text-muted-foreground hover:text-primary transition-colors group"
          >
            View all
            <ArrowRight className="h-3 w-3 -translate-x-0.5 group-hover:translate-x-0 transition-transform" />
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3.5">
          {strategyCounts.map((s) => {
            const meta = STRATEGY_META[s.key];
            return (
              <StrategyCard
                key={s.key}
                name={s.name}
                category={meta.category}
                icon={meta.icon}
                accentClass={meta.accent}
                count={s.count}
                bestReturn={s.bestReturn}
                avgSharpe={s.avgSharpe}
                sparklineData={s.sparklineData}
                available={isBackendOnline}
                onClick={() => navigate("/backtest")}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
