import { useState } from "react";
import { runBatchBacktest, getAvailableData } from "@/services/api";
import type {
  StrategyType,
  StrategyParams,
  BatchBacktestRequest,
  BatchBacktestResult,
  BatchSummary,
  RiskSettings,
  CachedTicker,
} from "@/types";
import { STRATEGY_INFO, DEFAULT_PARAMS, DEFAULT_RISK_SETTINGS } from "@/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPercent, formatNumber, pnlColor } from "@/utils/formatters";
import { Loader2, Download, Layers, ListFilter, AlertTriangle, SlidersHorizontal, Tags } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export function BatchBacktest() {
  const [strategy, setStrategy] = useState<StrategyType>("ma_crossover");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [tickerInput, setTickerInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number; ticker: string } | null>(null);
  const [results, setResults] = useState<BatchBacktestResult[] | null>(null);
  const [summary, setSummary] = useState<BatchSummary | null>(null);
  const [errors, setErrors] = useState<{ ticker: string; error: string }[]>([]);

  // Fetch cached tickers
  const { data: cachedTickers = [] } = useQuery<CachedTicker[]>({
    queryKey: ["availableData"],
    queryFn: getAvailableData,
  });

  const currentParams: StrategyParams = DEFAULT_PARAMS[strategy];

  const handleAddTicker = () => {
    const ticker = tickerInput.toUpperCase().trim();
    if (ticker && !selectedTickers.includes(ticker)) {
      setSelectedTickers([...selectedTickers, ticker]);
      setTickerInput("");
    }
  };

  const handleRemoveTicker = (ticker: string) => {
    setSelectedTickers(selectedTickers.filter((t) => t !== ticker));
  };

  const handleRunBatch = async () => {
    if (selectedTickers.length === 0) {
      toast.error("Please select at least one ticker");
      return;
    }

    if (selectedTickers.length > 20) {
      toast.error("Maximum 20 tickers allowed per batch");
      return;
    }

    setIsRunning(true);
    setProgress({ current: 0, total: selectedTickers.length, ticker: "Starting..." });
    setResults(null);
    setSummary(null);
    setErrors([]);

    try {
      const request: BatchBacktestRequest = {
        tickers: selectedTickers,
        strategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: 100000,
        params: currentParams,
        position_sizing: "equal_weight",
        risk_settings: DEFAULT_RISK_SETTINGS,
      };

      // Since backend runs sequentially, we'll just show a loading state
      // (For a real streaming/progress implementation, we'd use WebSocket or polling)
      const response = await runBatchBacktest(request);

      setResults(response.data.results);
      setSummary(response.data.batch_summary);
      setErrors(response.data.errors);
    } catch (err) {
      toast.error(`Batch backtest failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setIsRunning(false);
      setProgress(null);
    }
  };

  const handleExportTop5 = () => {
    if (!results || results.length === 0) return;

    const top5 = results.slice(0, Math.min(5, results.length));
    const exportData = top5.map((result) => ({
      ticker: result.ticker,
      strategy,
      total_return_pct: result.total_return_pct,
      sharpe_ratio: result.sharpe_ratio,
      max_drawdown_pct: result.max_drawdown_pct,
      win_rate: result.win_rate,
      total_trades: result.total_trades,
      metrics: result.metrics,
    }));

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `batch_top5_${strategy}_${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2 items-start">
        {/* Configuration */}
        <div className="card-elevated p-4 sm:p-5 space-y-4">
          <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2">
            <SlidersHorizontal className="h-3.5 w-3.5 text-primary" /> Configuration
          </h3>

          {/* Strategy Selection */}
          <div className="space-y-2">
            <Label className="text-xs">Strategy</Label>
            <Select value={strategy} onValueChange={(v) => setStrategy(v as StrategyType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(STRATEGY_INFO).map(([key, info]) => (
                  <SelectItem key={key} value={key}>
                    {info.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{STRATEGY_INFO[strategy].description}</p>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-xs">Start Date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">End Date</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
        </div>

        {/* Ticker Selection */}
        <div className="card-elevated p-4 sm:p-5 space-y-4">
          <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2">
            <Tags className="h-3.5 w-3.5 text-lab-secondary" /> Tickers
            <span className="text-xs font-normal text-muted-foreground">({selectedTickers.length}/20)</span>
          </h3>

          {/* Add Ticker */}
          <div className="flex gap-2">
            <Input
              placeholder="Enter ticker (e.g., AAPL)"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddTicker()}
              className="uppercase"
            />
            <Button onClick={handleAddTicker} variant="outline">
              Add
            </Button>
          </div>

          {/* Quick Select from Cache */}
          {cachedTickers.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Quick select from cached:</Label>
              <div className="flex flex-wrap gap-2">
                {Array.from(new Set(cachedTickers.map((c) => c.ticker))).slice(0, 10).map((tickerSymbol) => (
                  <Button
                    key={tickerSymbol}
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (!selectedTickers.includes(tickerSymbol)) {
                        setSelectedTickers([...selectedTickers, tickerSymbol]);
                      }
                    }}
                    disabled={selectedTickers.includes(tickerSymbol)}
                  >
                    {tickerSymbol}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Selected Tickers */}
          {selectedTickers.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs">Selected:</Label>
              <div className="flex flex-wrap gap-2">
                {selectedTickers.map((ticker) => (
                  <div key={ticker} className="flex items-center gap-2 px-2.5 py-1 bg-primary/10 border border-primary/20 rounded-full">
                    <span className="font-mono-numbers text-xs font-semibold text-primary">{ticker}</span>
                    <button
                      onClick={() => handleRemoveTicker(ticker)}
                      className="text-primary/60 hover:text-primary transition-colors"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Run Button */}
      <div className="flex justify-center">
        <Button onClick={handleRunBatch} disabled={isRunning || selectedTickers.length === 0} size="lg" className="gap-2">
          {isRunning ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Running Batch...
            </>
          ) : (
            `Run Batch Backtest (${selectedTickers.length} tickers)`
          )}
        </Button>
      </div>

      {/* Progress - real state, restyled + a queue preview of the actual selected tickers */}
      {progress && (
        <div className="card-elevated p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              Testing {progress.ticker}... ({progress.current}/{progress.total})
            </span>
            <div className="w-1/2 bg-secondary rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-primary to-lab-secondary h-2 rounded-full transition-all"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
          </div>
          {/* Queue preview - the real selected tickers, generic in-flight indicator (no per-ticker status is tracked) */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {selectedTickers.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1.5 text-[11px] font-mono-numbers px-2 py-1 rounded-full bg-secondary/60 text-muted-foreground"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse-gain" />
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Results - real once available; honest empty-state canvas before that */}
      {summary && results ? (
        <div className="space-y-4">
          {/* Summary Card */}
          <div className="card-elevated p-4 sm:p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2">
                <Layers className="h-3.5 w-3.5 text-primary" /> Batch Summary
              </h3>
              <Button onClick={handleExportTop5} variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Export Top 5
              </Button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="label-caps">Tested</div>
                <div className="text-2xl font-bold font-mono-numbers mt-0.5">{summary.total_tickers}</div>
              </div>
              <div>
                <div className="label-caps">Profitable</div>
                <div className="text-2xl font-bold font-mono-numbers text-gain mt-0.5">
                  {summary.profitable_count} <span className="text-sm">({formatPercent(summary.profitable_pct / 100)})</span>
                </div>
              </div>
              <div>
                <div className="label-caps">Avg Sharpe</div>
                <div className="text-2xl font-bold font-mono-numbers mt-0.5">{formatNumber(summary.avg_sharpe_ratio, 2)}</div>
              </div>
              <div>
                <div className="label-caps">Runtime</div>
                <div className="text-2xl font-bold font-mono-numbers mt-0.5">{summary.runtime_seconds}s</div>
              </div>
            </div>
            {summary.best_ticker && (
              <div className="mt-4 pt-4 border-t border-border/50">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Best: </span>
                    <span className="font-semibold text-gain">
                      {summary.best_ticker} (Sharpe: {summary.best_sharpe})
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Worst: </span>
                    <span className="font-semibold text-loss">
                      {summary.worst_ticker} (Sharpe: {summary.worst_sharpe})
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Results Table */}
          <div className="card-elevated p-4 sm:p-5">
            <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2 mb-4">
              <ListFilter className="h-3.5 w-3.5 text-lab-secondary" /> Results (sorted by Sharpe ratio)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-secondary/20">
                    <th className="py-2.5 px-2 text-left label-caps">Ticker</th>
                    <th className="py-2.5 px-2 text-right label-caps">Return %</th>
                    <th className="py-2.5 px-2 text-right label-caps">Sharpe</th>
                    <th className="py-2.5 px-2 text-right label-caps">Max DD %</th>
                    <th className="py-2.5 px-2 text-right label-caps">Win Rate</th>
                    <th className="py-2.5 px-2 text-right label-caps">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result) => (
                    <tr key={result.ticker} className="border-b border-border/50 hover:bg-secondary/40 transition-colors">
                      <td className="py-2.5 px-2 font-mono-numbers font-semibold">{result.ticker}</td>
                      <td className={cn("py-2.5 px-2 text-right font-mono-numbers font-semibold", pnlColor(result.total_return_pct))}>
                        {formatPercent(result.total_return_pct / 100)}
                      </td>
                      <td className="py-2.5 px-2 text-right font-mono-numbers">{formatNumber(result.sharpe_ratio, 2)}</td>
                      <td className="py-2.5 px-2 text-right font-mono-numbers text-loss">{formatPercent(result.max_drawdown_pct / 100)}</td>
                      <td className="py-2.5 px-2 text-right font-mono-numbers">{formatPercent(result.win_rate)}</td>
                      <td className="py-2.5 px-2 text-right font-mono-numbers">{formatNumber(result.total_trades)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Errors */}
          {errors.length > 0 && (
            <div className="card-elevated p-4 sm:p-5 border-loss/30 bg-loss/[0.03]">
              <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2 mb-3 text-loss">
                <AlertTriangle className="h-3.5 w-3.5" /> Failed Tickers ({errors.length})
              </h3>
              <div className="space-y-2">
                {errors.map((err) => (
                  <div key={err.ticker} className="text-xs">
                    <span className="font-mono-numbers font-semibold">{err.ticker}:</span>{" "}
                    <span className="text-muted-foreground">{err.error}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        !progress && (
          <div className="card-elevated">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-2">
                <Layers className="h-3.5 w-3.5 text-primary" /> Batch Results
              </h3>
              <span className="text-xs text-muted-foreground">0 tested</span>
            </div>
            <EmptyState
              icon={Layers}
              title="No batch run yet"
              description="Add tickers above and run a batch backtest - summary stats, a sortable results table, and per-ticker performance will appear here."
              preview={
                <div className="rounded-lg border border-border/50 bg-secondary/20 p-4 max-w-2xl mx-auto opacity-70 space-y-3">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {["Tested", "Profitable", "Avg Sharpe", "Runtime"].map((label) => (
                      <div key={label}>
                        <div className="text-[9px] uppercase tracking-wide text-muted-foreground">{label}</div>
                        <Skeleton className="h-5 w-12 rounded mt-1" />
                      </div>
                    ))}
                  </div>
                  <div className="pt-2 border-t border-border/40 space-y-1.5">
                    {(selectedTickers.length > 0 ? selectedTickers : ["-", "-", "-"]).slice(0, 5).map((t, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground font-mono-numbers">{t}</span>
                        <Skeleton className="h-3 w-16 rounded" />
                      </div>
                    ))}
                  </div>
                </div>
              }
            />
          </div>
        )
      )}
    </div>
  );
}
