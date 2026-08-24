import { useMemo, useState } from "react";
import { compareStrategies, fetchData } from "@/services/api";
import { useBacktestStore } from "@/stores/backtestStore";
import type { StrategyType, BacktestResult } from "@/types";
import { STRATEGY_INFO } from "@/types";
import { STRATEGY_META } from "@/utils/strategyMeta";
import { OverlayEquityChart, type OverlayView } from "@/components/comparison/OverlayEquityChart";
import { formatPercent, formatNumber, pnlColor, strategyDisplayName } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  Loader2, GitCompare, Sparkles, X, Plus, Save, TrendingUp, TrendingDown, Trophy, Layers,
  BarChart3, Lock, CheckCircle2, Circle,
} from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

// Colorblind-friendly palette - also numbers the selected strategies in the picker/legend/table.
const CHART_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea"];

// Real, backend-enforced export restrictions (mirrors POST /api/strategies/export
// in backend/alphalab/api/blueprints/backtest.py - same rule Backtest Studio
// previews). /api/compare never stores a backtest_id for its results (only
// the single-backtest endpoint populates the results store), so there is no
// working export action from this page - only an honest eligibility status.
const EXPORT_BLOCKED: Partial<Record<StrategyType, string>> = {
  vwap_reversion: "Requires intraday data (1Hour/15Min); AlphaLab only fetches daily/weekly/monthly bars.",
  rsi_simple: "Research/testing strategy only - no matching AlphaLive schema entry.",
};

const RANK_OPTIONS: { value: string; label: string; get: (r: BacktestResult) => number; format: (v: number) => string }[] = [
  { value: "sharpe_ratio", label: "Sharpe Ratio", get: (r) => r.metrics.risk.sharpe_ratio, format: formatNumber },
  { value: "total_return_pct", label: "Total Return", get: (r) => r.total_return_pct, format: formatPercent },
  { value: "max_drawdown_pct", label: "Max Drawdown", get: (r) => r.metrics.drawdown.max_drawdown_pct, format: formatPercent },
  { value: "win_rate", label: "Win Rate", get: (r) => r.metrics.trades.win_rate * 100, format: formatPercent },
  { value: "profit_factor", label: "Profit Factor", get: (r) => r.metrics.trades.profit_factor, format: formatNumber },
  { value: "total_trades", label: "Trades", get: (r) => r.total_trades, format: (v) => v.toFixed(0) },
];

const CHART_VIEWS: { value: OverlayView; label: string }[] = [
  { value: "equity", label: "Equity" },
  { value: "drawdown", label: "Drawdown" },
  { value: "rollingSharpe", label: "Rolling Sharpe" },
];

const GHOST_SERIES_A = [30, 32, 31, 35, 34, 38, 42, 40, 45, 48, 47, 52, 55, 53, 58];
const GHOST_SERIES_B = [30, 29, 31, 30, 33, 32, 36, 35, 39, 38, 42, 41, 45, 44, 48];

const MIN_STRATEGIES = 2;
const MAX_STRATEGIES = 3;

export default function Compare() {
  const { isBackendOnline, addToHistory } = useBacktestStore();
  const [ticker, setTicker] = useState("AAPL");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [selectedStrategies, setSelectedStrategies] = useState<StrategyType[]>(["ma_crossover", "rsi_mean_reversion"]);
  const [addOpen, setAddOpen] = useState(false);
  const [rankBy, setRankBy] = useState(RANK_OPTIONS[0].value);
  const [chartView, setChartView] = useState<OverlayView>("equity");
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<Record<string, BacktestResult> | null>(null);

  const removeStrategy = (s: StrategyType) => {
    setSelectedStrategies((prev) => (prev.length > MIN_STRATEGIES ? prev.filter((x) => x !== s) : prev));
  };
  const addStrategy = (s: StrategyType) => {
    setSelectedStrategies((prev) => (prev.length < MAX_STRATEGIES && !prev.includes(s) ? [...prev, s] : prev));
    setAddOpen(false);
  };

  const handleRun = async () => {
    if (selectedStrategies.length < MIN_STRATEGIES) {
      toast.error(`Select at least ${MIN_STRATEGIES} strategies`);
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

  const handleSaveComparison = () => {
    if (!results) return;
    Object.entries(results).forEach(([name, result]) => {
      addToHistory({
        id: result.backtest_id || `${Date.now()}-${name}`,
        date: new Date().toISOString(),
        ticker: ticker.toUpperCase(),
        strategy: name,
        total_return_pct: result.total_return_pct,
        sharpe_ratio: result.metrics.risk.sharpe_ratio,
        max_drawdown: result.metrics.drawdown.max_drawdown_pct,
        total_trades: result.total_trades,
        result,
      });
    });
    toast.success(`Saved ${Object.keys(results).length} results to research history`);
  };

  const resultEntries = results ? Object.entries(results) : [];
  const benchmark = resultEntries[0]?.[1]?.benchmark;
  const testWindow = `${new Date(startDate).toLocaleDateString("en-US", { month: "short", year: "numeric" })} - ${new Date(endDate).toLocaleDateString("en-US", { month: "short", year: "numeric" })}`;

  const summary = useMemo(() => {
    if (resultEntries.length === 0) return null;
    const rankOption = RANK_OPTIONS.find((r) => r.value === rankBy)!;
    const bestBy = (get: (r: BacktestResult) => number) =>
      resultEntries.reduce((best, curr) => (get(curr[1]) > get(best[1]) ? curr : best), resultEntries[0]);

    const highest = bestBy(rankOption.get);
    const bestReturn = bestBy((r) => r.total_return_pct);
    const lowestDrawdown = bestBy((r) => r.metrics.drawdown.max_drawdown_pct);
    const mostTrades = bestBy((r) => r.total_trades);

    const benchReturn = benchmark?.total_return_pct;
    const beatCount = benchReturn == null ? null : resultEntries.filter(([, r]) => r.total_return_pct > benchReturn).length;
    const benchmarkBeatAll = benchReturn != null && resultEntries.every(([, r]) => r.total_return_pct <= benchReturn);

    return { rankOption, highest, bestReturn, lowestDrawdown, mostTrades, benchReturn, beatCount, benchmarkBeatAll };
  }, [resultEntries, rankBy, benchmark]);

  return (
    <div className="page-shell py-5 space-y-3.5 animate-in-stagger">
      {/* Compact header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground leading-none">Strategy Comparison</h1>
          <p className="text-xs text-muted-foreground/90 mt-1.5">Evaluate strategies on identical data and execution assumptions</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleSaveComparison} disabled={!results}>
            <Save className="h-3.5 w-3.5" /> Save Comparison
          </Button>
          <Button onClick={handleRun} disabled={isRunning || selectedStrategies.length < MIN_STRATEGIES} size="sm" className="gap-2">
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
            {isRunning ? "Running..." : "Run Comparison"}
          </Button>
        </div>
      </div>

      {/* Horizontal controls */}
      <div className="card-elevated p-3.5">
        <div className="flex flex-wrap items-stretch gap-3">
          <ConfigField label="Ticker" className="w-[110px]">
            <Input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="AAPL" className="h-9 text-sm font-mono-numbers" />
          </ConfigField>

          <ConfigField label="Test Window" className="min-w-[210px]">
            <div className="flex items-center gap-1.5">
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="h-9 text-xs" />
              <span className="text-muted-foreground text-xs shrink-0">-</span>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="h-9 text-xs" />
            </div>
          </ConfigField>

          <ConfigField label="Initial Capital" className="w-[140px]">
            <Input type="number" value={initialCapital} onChange={(e) => setInitialCapital(Number(e.target.value))} min={1000} className="h-9 text-sm font-mono-numbers" />
          </ConfigField>

          <ConfigField label="Benchmark" className="w-[170px]">
            <div className="h-9 flex items-center text-sm font-medium">Buy &amp; Hold</div>
            <span className="text-[10px] text-muted-foreground/85 mt-1 block leading-snug">Buy-and-hold of the same ticker</span>
          </ConfigField>

          <ConfigField label="Rank By" className="min-w-[150px] flex-1">
            <Select value={rankBy} onValueChange={setRankBy}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                {RANK_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </ConfigField>
        </div>
      </div>

      {/* Compact searchable strategy selection */}
      <div className="card-elevated p-3.5">
        <div className="flex items-center justify-between mb-2.5 flex-wrap gap-2">
          <span className="section-label">Strategies</span>
          <span className="text-[11px] font-mono-numbers text-muted-foreground">
            {selectedStrategies.length}/{MAX_STRATEGIES} selected - min {MIN_STRATEGIES}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {selectedStrategies.map((s, i) => (
            <span
              key={s}
              className="inline-flex items-center gap-1.5 rounded-full border pl-1 pr-2 py-1 text-xs font-semibold"
              style={{ borderColor: `${CHART_COLORS[i]}55`, backgroundColor: `${CHART_COLORS[i]}15` }}
            >
              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: CHART_COLORS[i] }} />
              {STRATEGY_INFO[s].name}
              <button
                onClick={() => removeStrategy(s)}
                disabled={selectedStrategies.length <= MIN_STRATEGIES}
                className="ml-0.5 rounded-full hover:bg-secondary/60 disabled:opacity-30 disabled:cursor-not-allowed p-0.5"
                title={selectedStrategies.length <= MIN_STRATEGIES ? `At least ${MIN_STRATEGIES} strategies required` : "Remove"}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}

          {selectedStrategies.length < MAX_STRATEGIES && (
            <Popover open={addOpen} onOpenChange={setAddOpen}>
              <PopoverTrigger asChild>
                <button className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-border/70 px-2.5 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors">
                  <Plus className="h-3 w-3" /> Add Strategy
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-0" align="start">
                <Command>
                  <CommandInput placeholder="Search strategies..." className="text-sm" />
                  <CommandList>
                    <CommandEmpty>No strategy found.</CommandEmpty>
                    <CommandGroup>
                      {(Object.keys(STRATEGY_INFO) as StrategyType[])
                        .filter((k) => !selectedStrategies.includes(k))
                        .map((k) => {
                          const Icon = STRATEGY_META[k].icon;
                          return (
                            <CommandItem key={k} value={STRATEGY_INFO[k].name} onSelect={() => addStrategy(k)} className="gap-2 cursor-pointer">
                              <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                              <div className="min-w-0">
                                <div className="text-xs font-medium">{STRATEGY_INFO[k].name}</div>
                                <div className="text-[10px] text-muted-foreground truncate">{STRATEGY_META[k].category}</div>
                              </div>
                            </CommandItem>
                          );
                        })}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          )}
        </div>
      </div>

      {/* Empty state / results */}
      {resultEntries.length === 0 ? (
        <div className="card-elevated">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <h3 className="section-label flex items-center gap-1.5">
              <GitCompare className="h-3.5 w-3.5 text-primary" /> Comparison Results
            </h3>
            <span className="text-xs text-muted-foreground">0 runs</span>
          </div>
          <EmptyState
            icon={Sparkles}
            title="No comparison run yet"
            description="Select strategies above and run a comparison to see overlaid equity curves and a full performance breakdown."
            preview={
              <div className="max-w-3xl mx-auto space-y-3">
                <div className="rounded-lg border border-border/40 chart-grid-bg h-32 relative p-3 overflow-hidden animate-pulse">
                  <svg viewBox="0 0 200 100" className="w-full h-full" preserveAspectRatio="none">
                    <polyline fill="none" stroke="hsl(var(--muted-foreground))" strokeOpacity={0.35} strokeWidth={1.5} points={GHOST_SERIES_A.map((v, i) => `${(i / (GHOST_SERIES_A.length - 1)) * 200},${100 - v}`).join(" ")} />
                    <polyline fill="none" stroke="hsl(var(--primary))" strokeOpacity={0.3} strokeWidth={1.5} points={GHOST_SERIES_B.map((v, i) => `${(i / (GHOST_SERIES_B.length - 1)) * 200},${100 - v}`).join(" ")} />
                  </svg>
                </div>
                <div className="rounded-lg border border-border/40 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/50 bg-secondary/20">
                        <th className="px-3 py-2 text-left label-caps">Strategy</th>
                        <th className="px-3 py-2 text-right label-caps">Return</th>
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
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3.5">
          {/* Equity comparison chart */}
          <div className="xl:col-span-2 card-elevated p-4">
            <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
              <h3 className="section-label">Equity Comparison</h3>
              <div className="flex items-center gap-1 rounded-lg border border-border/60 p-0.5">
                {CHART_VIEWS.map((v) => (
                  <button
                    key={v.value}
                    onClick={() => setChartView(v.value)}
                    className={cn(
                      "px-2 py-1 rounded-md text-[11px] font-semibold transition-colors",
                      chartView === v.value ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Strategy vs. benchmark legend */}
            <div className="flex items-center gap-4 flex-wrap mb-3">
              {resultEntries.map(([name, result], i) => (
                <div key={name} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: CHART_COLORS[i] }} />
                  <span className="text-xs text-muted-foreground">{strategyDisplayName(name)}</span>
                  <span className="font-mono-numbers text-xs font-semibold">{formatCurrencyShort(result.final_value)}</span>
                  <span className={cn("font-mono-numbers text-xs font-semibold", pnlColor(result.total_return_pct))}>
                    {formatPercent(result.total_return_pct)}
                  </span>
                </div>
              ))}
              {benchmark && (
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full shrink-0 bg-muted-foreground" />
                  <span className="text-xs text-muted-foreground">Buy &amp; Hold ({ticker.toUpperCase()})</span>
                  <span className={cn("font-mono-numbers text-xs font-semibold", pnlColor(benchmark.total_return_pct))}>
                    {formatPercent(benchmark.total_return_pct)}
                  </span>
                </div>
              )}
            </div>

            <OverlayEquityChart results={results!} view={chartView} colors={CHART_COLORS} />
          </div>

          {/* Comparison summary */}
          <div className="card-elevated p-4 space-y-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <h3 className="section-label">Comparison Summary</h3>
            </div>
            {summary && (
              <>
                <div className="rounded-lg border border-border/60 bg-secondary/20 p-3 mb-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="label-caps">Highest {summary.rankOption.label}</p>
                      <p className="text-sm font-bold text-primary truncate mt-0.5">{strategyDisplayName(summary.highest[0])}</p>
                      <p className="font-mono-numbers text-xs text-muted-foreground mt-0.5">{summary.rankOption.format(summary.rankOption.get(summary.highest[1]))} - {ticker.toUpperCase()} - {testWindow}</p>
                    </div>
                    <span className="text-[9px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border border-warning/30 bg-warning/10 text-warning shrink-0 text-center leading-tight">
                      Not validated<br />out of sample
                    </span>
                  </div>
                </div>

                <SummaryRow icon={<TrendingUp className="h-3.5 w-3.5" />} label="Best Return" name={strategyDisplayName(summary.bestReturn[0])} value={formatPercent(summary.bestReturn[1].total_return_pct)} tone={pnlColor(summary.bestReturn[1].total_return_pct)} />
                <SummaryRow icon={<TrendingDown className="h-3.5 w-3.5" />} label="Lowest Drawdown" name={strategyDisplayName(summary.lowestDrawdown[0])} value={formatPercent(summary.lowestDrawdown[1].metrics.drawdown.max_drawdown_pct)} tone="text-loss" />
                <SummaryRow icon={<Layers className="h-3.5 w-3.5" />} label="Most Trades" name={strategyDisplayName(summary.mostTrades[0])} value={summary.mostTrades[1].total_trades.toString()} />
                {summary.benchReturn != null && (
                  <SummaryRow
                    icon={<Trophy className="h-3.5 w-3.5" />}
                    label="Benchmark Leader"
                    name={summary.benchmarkBeatAll ? `Buy & Hold (${ticker.toUpperCase()})` : strategyDisplayName(summary.bestReturn[0])}
                    value={summary.benchmarkBeatAll ? "Outperformed all selected strategies" : `Beat the benchmark by ${(summary.bestReturn[1].total_return_pct - summary.benchReturn).toFixed(1)}pt`}
                    small
                  />
                )}
                {summary.beatCount != null && (
                  <SummaryRow
                    icon={<BarChart3 className="h-3.5 w-3.5" />}
                    label="Market-Beating Consistency"
                    name={summary.beatCount === resultEntries.length ? "All strategies beat it" : summary.beatCount === 0 ? "None beat it" : "No universal edge"}
                    value={`${summary.beatCount} of ${resultEntries.length} beat the benchmark`}
                    small
                  />
                )}

                <p className="text-[10px] text-muted-foreground/80 pt-2 mt-2 border-t border-border/40 leading-relaxed">
                  Results reflect in-sample performance on the selected test window only.
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* Strategy metrics table */}
      {resultEntries.length > 0 && (
        <div className="card-elevated overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="section-label">Strategy Metrics</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/20">
                  <th className="px-4 py-2.5 text-left label-caps">Strategy</th>
                  <th className="px-3 py-2.5 text-right label-caps">Return</th>
                  <th className="px-3 py-2.5 text-right label-caps">Sharpe</th>
                  <th className="px-3 py-2.5 text-right label-caps">Max Drawdown</th>
                  <th className="px-3 py-2.5 text-right label-caps">Win Rate</th>
                  <th className="px-3 py-2.5 text-right label-caps">Profit Factor</th>
                  <th className="px-3 py-2.5 text-right label-caps">Trades</th>
                  <th className="px-3 py-2.5 text-left label-caps">Validation</th>
                  <th className="px-4 py-2.5 text-left label-caps">AlphaLive</th>
                </tr>
              </thead>
              <tbody>
                {resultEntries.map(([name, result], i) => {
                  const blockReason = EXPORT_BLOCKED[name as StrategyType];
                  const isRankWinner = summary && summary.highest[0] === name;
                  return (
                    <tr key={name} className={cn("border-b border-border/50 hover:bg-secondary/40 transition-colors", isRankWinner && "bg-primary/[0.04]")}>
                      <td className="px-4 py-3 font-medium">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: CHART_COLORS[i] }} />
                          {strategyDisplayName(name)}
                          {isRankWinner && <Trophy className="h-3 w-3 text-warning shrink-0" />}
                        </div>
                      </td>
                      <td className={cn("px-3 py-3 text-right font-mono-numbers font-semibold", pnlColor(result.total_return_pct))}>{formatPercent(result.total_return_pct)}</td>
                      <td className="px-3 py-3 text-right font-mono-numbers">{formatNumber(result.metrics.risk.sharpe_ratio)}</td>
                      <td className="px-3 py-3 text-right font-mono-numbers text-loss">{formatPercent(result.metrics.drawdown.max_drawdown_pct)}</td>
                      <td className="px-3 py-3 text-right font-mono-numbers">{formatPercent(result.metrics.trades.win_rate * 100)}</td>
                      <td className="px-3 py-3 text-right font-mono-numbers">{formatNumber(result.metrics.trades.profit_factor)}</td>
                      <td className="px-3 py-3 text-right font-mono-numbers">{result.total_trades}</td>
                      <td className="px-3 py-3">
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                          <Circle className="h-3 w-3" /> Not run
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {blockReason ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-loss" title={blockReason}>
                            <Lock className="h-3 w-3" /> {name === "rsi_simple" ? "Research only" : "Intraday required"}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-gain">
                            <CheckCircle2 className="h-3 w-3" /> Exportable via Backtest
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Standing export-restriction notice - real backend rule, always shown regardless of selection */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <RestrictionNotice strategy="rsi_simple" label="Research only" note="Not exportable in this framework - AlphaLive has no matching strategy entry." />
        <RestrictionNotice strategy="vwap_reversion" label="Intraday required" note="Requires intraday data AlphaLab cannot fetch - not exportable regardless of backtest results." />
      </div>
    </div>
  );
}

function formatCurrencyShort(v: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(v);
}

function ConfigField({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("rounded-lg border border-border/70 bg-card/60 p-2.5", className)}>
      <span className="label-caps block mb-1.5">{label}</span>
      {children}
    </div>
  );
}

function SummaryRow({ icon, label, name, value, tone, small }: { icon: React.ReactNode; label: string; name: string; value: string; tone?: string; small?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 border-b border-border/30 last:border-0">
      <div className="flex items-start gap-2 min-w-0">
        <span className="text-muted-foreground shrink-0 mt-0.5">{icon}</span>
        <div className="min-w-0">
          <p className="text-[10.5px] text-muted-foreground">{label}</p>
          <p className={cn("font-semibold truncate", small ? "text-xs" : "text-sm")}>{name}</p>
        </div>
      </div>
      <span className={cn("font-mono-numbers text-xs font-semibold shrink-0 text-right", tone)}>{value}</span>
    </div>
  );
}

function RestrictionNotice({ strategy, label, note }: { strategy: StrategyType; label: string; note: string }) {
  const meta = STRATEGY_META[strategy];
  const Icon = meta.icon;
  return (
    <div className="card-elevated p-3.5 flex items-start gap-3">
      <div className="rounded-lg bg-secondary/60 p-2 shrink-0 text-muted-foreground">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold">{STRATEGY_INFO[strategy].name}</span>
          <span className="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-full border border-loss/30 bg-loss/10 text-loss">{label}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{note}</p>
      </div>
    </div>
  );
}
