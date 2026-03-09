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
import { Card } from "@/components/ui/card";
import { formatPercent, formatNumber, pnlColor } from "@/utils/formatters";
import { Loader2, Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

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
      alert("Please select at least one ticker");
      return;
    }

    if (selectedTickers.length > 20) {
      alert("Maximum 20 tickers allowed per batch");
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
      alert(`Batch backtest failed: ${err instanceof Error ? err.message : "Unknown error"}`);
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
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        {/* Configuration */}
        <Card className="p-6 space-y-4">
          <h3 className="font-semibold text-lg">Configuration</h3>

          {/* Strategy Selection */}
          <div className="space-y-2">
            <Label>Strategy</Label>
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
            <p className="text-sm text-muted-foreground">{STRATEGY_INFO[strategy].description}</p>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
        </Card>

        {/* Ticker Selection */}
        <Card className="p-6 space-y-4">
          <h3 className="font-semibold text-lg">Tickers ({selectedTickers.length}/20)</h3>

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
              <Label className="text-sm text-muted-foreground">Quick select from cached:</Label>
              <div className="flex flex-wrap gap-2">
                {cachedTickers.slice(0, 10).map((cached) => (
                  <Button
                    key={cached.ticker}
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (!selectedTickers.includes(cached.ticker)) {
                        setSelectedTickers([...selectedTickers, cached.ticker]);
                      }
                    }}
                    disabled={selectedTickers.includes(cached.ticker)}
                  >
                    {cached.ticker}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Selected Tickers */}
          {selectedTickers.length > 0 && (
            <div className="space-y-2">
              <Label>Selected:</Label>
              <div className="flex flex-wrap gap-2">
                {selectedTickers.map((ticker) => (
                  <div key={ticker} className="flex items-center gap-2 px-3 py-1 bg-secondary rounded-md">
                    <span className="font-mono">{ticker}</span>
                    <button
                      onClick={() => handleRemoveTicker(ticker)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Run Button */}
      <div className="flex justify-center">
        <Button onClick={handleRunBatch} disabled={isRunning || selectedTickers.length === 0} size="lg">
          {isRunning ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Running Batch...
            </>
          ) : (
            `Run Batch Backtest (${selectedTickers.length} tickers)`
          )}
        </Button>
      </div>

      {/* Progress */}
      {progress && (
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">
              Testing {progress.ticker}... ({progress.current}/{progress.total})
            </span>
            <div className="w-1/2 bg-secondary rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
          </div>
        </Card>
      )}

      {/* Results */}
      {summary && results && (
        <div className="space-y-4">
          {/* Summary Card */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-lg">Batch Summary</h3>
              <Button onClick={handleExportTop5} variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Export Top 5
              </Button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">Tested</div>
                <div className="text-2xl font-bold">{summary.total_tickers}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Profitable</div>
                <div className="text-2xl font-bold text-green-600">
                  {summary.profitable_count} ({formatPercent(summary.profitable_pct / 100)})
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Avg Sharpe</div>
                <div className="text-2xl font-bold">{summary.avg_sharpe_ratio.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Runtime</div>
                <div className="text-2xl font-bold">{summary.runtime_seconds}s</div>
              </div>
            </div>
            {summary.best_ticker && (
              <div className="mt-4 pt-4 border-t">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Best: </span>
                    <span className="font-semibold">
                      {summary.best_ticker} (Sharpe: {summary.best_sharpe})
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Worst: </span>
                    <span className="font-semibold">
                      {summary.worst_ticker} (Sharpe: {summary.worst_sharpe})
                    </span>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Results Table */}
          <Card className="p-6">
            <h3 className="font-semibold text-lg mb-4">Results (sorted by Sharpe ratio)</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-semibold">Ticker</th>
                    <th className="pb-2 font-semibold text-right">Return %</th>
                    <th className="pb-2 font-semibold text-right">Sharpe</th>
                    <th className="pb-2 font-semibold text-right">Max DD %</th>
                    <th className="pb-2 font-semibold text-right">Win Rate</th>
                    <th className="pb-2 font-semibold text-right">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result) => (
                    <tr key={result.ticker} className="border-b hover:bg-secondary/50">
                      <td className="py-2 font-mono font-semibold">{result.ticker}</td>
                      <td className={`py-2 text-right font-semibold ${pnlColor(result.total_return_pct)}`}>
                        {formatPercent(result.total_return_pct / 100)}
                      </td>
                      <td className="py-2 text-right">{result.sharpe_ratio.toFixed(2)}</td>
                      <td className="py-2 text-right text-red-600">{formatPercent(result.max_drawdown_pct / 100)}</td>
                      <td className="py-2 text-right">{formatPercent(result.win_rate)}</td>
                      <td className="py-2 text-right">{formatNumber(result.total_trades)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Errors */}
          {errors.length > 0 && (
            <Card className="p-6 border-destructive">
              <h3 className="font-semibold text-lg mb-2 text-destructive">Failed Tickers ({errors.length})</h3>
              <div className="space-y-2">
                {errors.map((err) => (
                  <div key={err.ticker} className="text-sm">
                    <span className="font-mono font-semibold">{err.ticker}:</span>{" "}
                    <span className="text-muted-foreground">{err.error}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
