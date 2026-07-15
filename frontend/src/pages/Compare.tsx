import { useState } from "react";
import { compareStrategies, fetchData } from "@/services/api";
import { useBacktestStore } from "@/stores/backtestStore";
import type { StrategyType, BacktestResult } from "@/types";
import { STRATEGY_INFO } from "@/types";
import { STRATEGY_META, STRATEGY_ACCENT_GRADIENT } from "@/utils/strategyMeta";
import { OverlayEquityChart } from "@/components/comparison/OverlayEquityChart";
import { CorrelationMatrix } from "@/components/comparison/CorrelationMatrix";
import { BestStrategySummary } from "@/components/comparison/BestStrategySummary";
import { MetricCard } from "@/components/metrics/MetricCard";
import { formatPercent, formatNumber, pnlColor, strategyDisplayName } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { Loader2, GitCompare, Sparkles, TrendingUp, Shield, Percent, ChevronRight } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";

// Colorblind-friendly palette - also used to number selected strategies in the picker
const CHART_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea"];

// Decorative-only ghost series for the pre-run overlay preview - never rendered as real data.
const GHOST_SERIES_A = [30, 32, 31, 35, 34, 38, 42, 40, 45, 48, 47, 52, 55, 53, 58];
const GHOST_SERIES_B = [30, 29, 31, 30, 33, 32, 36, 35, 39, 38, 42, 41, 45, 44, 48];

export default function Compare() {
  const { isBackendOnline } = useBacktestStore();
  const [ticker, setTicker] = useState("AAPL");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [selectedStrategies, setSelectedStrategies] = useState<StrategyType[]>(["ma_crossover", "rsi_mean_reversion"]);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<Record<string, BacktestResult> | null>(null);

  const toggleStrategy = (s: StrategyType) => {
    setSelectedStrategies((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : prev.length < 3 ? [...prev, s] : prev
    );
  };

  const handleRun = async () => {
    if (selectedStrategies.length < 2) {
      toast.error("Select at least 2 strategies");
      return;
    }
    setIsRunning(true);
    try {
      await fetchData([ticker.toUpperCase()], startDate, endDate, "1d");
      const res = await compareStrategies({
        ticker: ticker.toUpperCase(),
        strategies: selectedStrategies,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
      });
      setResults(res.data);
      toast.success("Comparison complete!");
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Comparison failed");
    } finally {
      setIsRunning(false);
    }
  };

  const resultEntries = results ? Object.entries(results) : [];

  // Build multi-line equity data
  const equityData = resultEntries.length > 0
    ? resultEntries[0][1].equity_curve.map((point, i) => {
        const obj: Record<string, any> = { date: point.date };
        resultEntries.forEach(([name, result]) => {
          obj[name] = result.equity_curve[i]?.value;
        });
        return obj;
      })
    : [];

  // Build radar data
  const radarData = resultEntries.length > 0
    ? [
        { metric: "Sharpe", ...Object.fromEntries(resultEntries.map(([name, r]) => [name, Math.max(0, r.metrics.risk.sharpe_ratio)])) },
        { metric: "Win Rate", ...Object.fromEntries(resultEntries.map(([name, r]) => [name, r.metrics.trades.win_rate])) },
        { metric: "Calmar", ...Object.fromEntries(resultEntries.map(([name, r]) => [name, Math.max(0, r.metrics.risk.calmar_ratio)])) },
        { metric: "Sortino", ...Object.fromEntries(resultEntries.map(([name, r]) => [name, Math.max(0, r.metrics.risk.sortino_ratio)])) },
      ]
    : [];

  return (
    <div className="page-shell py-8 space-y-6 animate-in-stagger">
      {/* Page header / command strip */}
      <div className="hero-panel px-6 py-6 sm:px-8 sm:py-7">
        <div className="glow-blob h-36 w-36 -bottom-14 right-1/4 opacity-20 bg-lab-secondary" />
        <div className="flex items-start justify-between flex-wrap gap-5 relative">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 mb-2.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              <span className="text-[11px] font-semibold text-primary uppercase tracking-widest">Strategy Comparison Lab</span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight gradient-text leading-tight">
              Compare Strategies
            </h1>
            <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
              Run 2-3 strategies side-by-side on the same ticker and timeframe to find your best performer.
            </p>
            <div className="flex items-center gap-2 mt-4 flex-wrap">
              <StatusBadge
                label={isBackendOnline ? "Backend Online" : "Backend Offline"}
                tone={isBackendOnline ? "gain" : "loss"}
                dot
                pulse={isBackendOnline}
                className="normal-case tracking-normal"
              />
              <StatusBadge label={ticker.toUpperCase()} tone="primary" className="normal-case tracking-normal" />
              <StatusBadge
                label={`${selectedStrategies.length}/3 strategies selected`}
                tone={selectedStrategies.length >= 2 ? "gain" : "neutral"}
                className="normal-case tracking-normal"
              />
            </div>
          </div>
          <Button
            size="lg"
            className="gap-2 shrink-0"
            onClick={handleRun}
            disabled={isRunning || selectedStrategies.length < 2}
          >
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
            {isRunning ? "Running comparison..." : "Run Comparison"}
          </Button>
        </div>
      </div>

      {/* Test parameter strip */}
      <div className="card-elevated p-4 sm:p-5">
        <h3 className="section-label mb-3">Test Parameters</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <Label className="text-xs">Ticker</Label>
            <Input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} className="mt-1 font-mono-numbers" />
          </div>
          <div>
            <Label className="text-xs">Start Date</Label>
            <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label className="text-xs">End Date</Label>
            <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label className="text-xs">Initial Capital</Label>
            <Input type="number" value={initialCapital} onChange={(e) => setInitialCapital(Number(e.target.value))} className="mt-1 font-mono-numbers" />
          </div>
        </div>
      </div>

      {/* Strategy selection grid */}
      <div className="card-elevated p-4 sm:p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="section-label">Strategies</h3>
          <span className="text-[11px] font-mono-numbers text-muted-foreground">
            {selectedStrategies.length}/3 selected · min 2
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(Object.keys(STRATEGY_INFO) as StrategyType[]).map((key) => {
            const selected = selectedStrategies.includes(key);
            const idx = selectedStrategies.indexOf(key);
            const meta = STRATEGY_META[key];
            const Icon = meta.icon;
            const gradient = STRATEGY_ACCENT_GRADIENT[meta.accent] ?? "from-primary to-lab-deep";
            return (
              <button
                key={key}
                type="button"
                onClick={() => toggleStrategy(key)}
                className={cn(
                  "group relative text-left flex items-start gap-3 p-3.5 rounded-xl border transition-all",
                  selected
                    ? "border-primary bg-primary/10 shadow-[0_0_0_1px_hsl(var(--primary)/0.3)]"
                    : "border-border/70 bg-card/40 hover:border-muted-foreground/30 hover:bg-secondary/30"
                )}
              >
                <div
                  className={cn(
                    "rounded-lg bg-gradient-to-br shrink-0 flex items-center justify-center text-white shadow transition-transform group-hover:scale-105 h-9 w-9",
                    gradient
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold">{STRATEGY_INFO[key].name}</span>
                    {selected && (
                      <span
                        className="flex items-center justify-center h-4 w-4 rounded-full text-[9px] font-bold shrink-0"
                        style={{ backgroundColor: CHART_COLORS[idx], color: "#fff" }}
                      >
                        {idx + 1}
                      </span>
                    )}
                  </div>
                  <span className="inline-block text-[9px] font-medium text-muted-foreground/80 bg-secondary/50 rounded-full px-1.5 py-0.5 mt-1">
                    {meta.category}
                  </span>
                  <div className="text-xs text-muted-foreground mt-1 leading-snug">{STRATEGY_INFO[key].description}</div>
                </div>
                {!selected && (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/0 group-hover:text-muted-foreground/50 -translate-x-1 group-hover:translate-x-0 transition-all shrink-0 mt-1" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Empty state / results */}
      {resultEntries.length === 0 && (
        <div className="card-elevated">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2">
              <GitCompare className="h-3.5 w-3.5 text-primary" /> Comparison Results
            </h3>
            <span className="text-xs text-muted-foreground">0 runs</span>
          </div>
          <EmptyState
            icon={Sparkles}
            title="No comparison run yet"
            description="Select 2-3 strategies above and run a comparison to see overlayed equity curves, a correlation matrix, and a full performance breakdown."
            preview={
              <div className="max-w-3xl mx-auto space-y-4">
                {/* Ghost metric comparison cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 opacity-50 pointer-events-none select-none">
                  <MetricCard label="Best Sharpe" value="-" icon={<TrendingUp className="h-4 w-4" />} />
                  <MetricCard label="Best Return" value="-" icon={<Percent className="h-4 w-4" />} />
                  <MetricCard label="Lowest Drawdown" value="-" icon={<Shield className="h-4 w-4" />} />
                </div>

                {/* Ghost overlapping equity curves */}
                <div className="rounded-lg border border-border/40 chart-grid-bg h-32 relative p-3 overflow-hidden animate-pulse">
                  <svg viewBox="0 0 200 100" className="w-full h-full" preserveAspectRatio="none">
                    <polyline
                      fill="none"
                      stroke="hsl(var(--muted-foreground))"
                      strokeOpacity={0.35}
                      strokeWidth={1.5}
                      points={GHOST_SERIES_A.map((v, i) => `${(i / (GHOST_SERIES_A.length - 1)) * 200},${100 - v}`).join(" ")}
                    />
                    <polyline
                      fill="none"
                      stroke="hsl(var(--primary))"
                      strokeOpacity={0.3}
                      strokeWidth={1.5}
                      points={GHOST_SERIES_B.map((v, i) => `${(i / (GHOST_SERIES_B.length - 1)) * 200},${100 - v}`).join(" ")}
                    />
                  </svg>
                </div>

                {/* Ghost ranking table - real selected strategy names, skeleton metrics */}
                <div className="rounded-lg border border-border/40 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/50 bg-secondary/20">
                        <th className="px-3 py-2 text-left label-caps">Strategy</th>
                        <th className="px-3 py-2 text-right label-caps">Return %</th>
                        <th className="px-3 py-2 text-right label-caps">Sharpe</th>
                        <th className="px-3 py-2 text-right label-caps">Max DD</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedStrategies.map((s, i) => (
                        <tr key={s} className="border-b border-border/30 last:border-0">
                          <td className="px-3 py-2.5 font-medium flex items-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: CHART_COLORS[i] }} />
                            {STRATEGY_INFO[s].name}
                          </td>
                          <td className="px-3 py-2.5 text-right"><Skeleton className="h-3 w-12 rounded ml-auto" /></td>
                          <td className="px-3 py-2.5 text-right"><Skeleton className="h-3 w-10 rounded ml-auto" /></td>
                          <td className="px-3 py-2.5 text-right"><Skeleton className="h-3 w-12 rounded ml-auto" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            }
          />
        </div>
      )}

      {resultEntries.length > 0 && (
        <>
          {/* Best Strategy Summary */}
          <BestStrategySummary results={results!} />

          {/* Overlay Equity Chart */}
          <div className="card-elevated p-4">
            <h3 className="text-[15px] font-bold tracking-tight mb-3">Equity Curves (Normalized to % Returns)</h3>
            <OverlayEquityChart results={results!} />
          </div>

          {/* Correlation Matrix */}
          <div className="card-elevated p-4">
            <h3 className="text-[15px] font-bold tracking-tight mb-3">Return Correlation Matrix</h3>
            <CorrelationMatrix results={results!} />
          </div>

          {/* Comparison Table */}
          <div className="card-elevated overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/20">
                  <th className="px-4 py-2.5 text-left label-caps">Strategy</th>
                  <th className="px-4 py-2.5 text-right label-caps">Return %</th>
                  <th className="px-4 py-2.5 text-right label-caps">CAGR</th>
                  <th className="px-4 py-2.5 text-right label-caps">Sharpe</th>
                  <th className="px-4 py-2.5 text-right label-caps">Max DD</th>
                  <th className="px-4 py-2.5 text-right label-caps">Win Rate</th>
                  <th className="px-4 py-2.5 text-right label-caps">Trades</th>
                </tr>
              </thead>
              <tbody>
                {resultEntries.map(([name, result], i) => (
                  <tr key={name} className="border-b border-border/50 hover:bg-secondary/40 transition-colors">
                    <td className="px-4 py-3 font-medium flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: CHART_COLORS[i] }} />
                      {strategyDisplayName(name)}
                    </td>
                    <td className={cn("px-4 py-3 text-right font-mono-numbers font-semibold", pnlColor(result.total_return_pct))}>{formatPercent(result.total_return_pct)}</td>
                    <td className={cn("px-4 py-3 text-right font-mono-numbers", pnlColor(result.metrics.returns.cagr_pct))}>{formatPercent(result.metrics.returns.cagr_pct)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers">{formatNumber(result.metrics.risk.sharpe_ratio)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers text-loss">{formatPercent(result.metrics.drawdown.max_drawdown_pct)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers">{formatPercent(result.metrics.trades.win_rate * 100)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers">{result.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card-elevated p-4">
              <h3 className="text-[15px] font-bold tracking-tight mb-3">Equity Curves</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={equityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 22%)" />
                  <XAxis dataKey="date" tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} stroke="hsl(217 33% 22%)" tickFormatter={(v) => new Date(v).toLocaleDateString("en-US", { month: "short", year: "2-digit" })} minTickGap={40} />
                  <YAxis tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} stroke="hsl(217 33% 22%)" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={60} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(217 33% 17%)", border: "1px solid hsl(217 33% 22%)", borderRadius: "8px", fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {resultEntries.map(([name], i) => (
                    <Line key={name} type="monotone" dataKey={name} stroke={CHART_COLORS[i]} strokeWidth={2} dot={false} name={strategyDisplayName(name)} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="card-elevated p-4">
              <h3 className="text-[15px] font-bold tracking-tight mb-3">Performance Radar</h3>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="hsl(217 33% 22%)" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} />
                  <PolarRadiusAxis tick={{ fill: "hsl(215 20% 55%)", fontSize: 9 }} />
                  {resultEntries.map(([name], i) => (
                    <Radar key={name} name={strategyDisplayName(name)} dataKey={name} stroke={CHART_COLORS[i]} fill={CHART_COLORS[i]} fillOpacity={0.15} />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
