import { useState } from "react";
import { compareStrategies, fetchData } from "@/services/api";
import type { StrategyType, BacktestResult } from "@/types";
import { STRATEGY_INFO } from "@/types";
import { OverlayEquityChart } from "@/components/comparison/OverlayEquityChart";
import { CorrelationMatrix } from "@/components/comparison/CorrelationMatrix";
import { BestStrategySummary } from "@/components/comparison/BestStrategySummary";
import { MetricCard } from "@/components/metrics/MetricCard";
import { formatPercent, formatNumber, pnlColor, strategyDisplayName } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { Loader2, GitCompare } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";

// Colorblind-friendly palette
const CHART_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea"];

export default function Compare() {
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
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <h1 className="font-display text-2xl font-bold">Compare Strategies</h1>

      {/* Config */}
      <div className="card-elevated p-5 space-y-4">
        <div className="grid grid-cols-4 gap-4">
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

        <div className="space-y-2">
          <Label className="text-xs">Strategies (select 2-3)</Label>
          <div className="flex gap-3">
            {(Object.keys(STRATEGY_INFO) as StrategyType[]).map((key) => (
              <label
                key={key}
                className={cn(
                  "flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors flex-1",
                  selectedStrategies.includes(key) ? "border-primary bg-primary/10" : "border-border hover:border-muted-foreground/30"
                )}
              >
                <Checkbox checked={selectedStrategies.includes(key)} onCheckedChange={() => toggleStrategy(key)} />
                <div>
                  <div className="text-sm font-medium">{STRATEGY_INFO[key].name}</div>
                  <div className="text-xs text-muted-foreground">{STRATEGY_INFO[key].description}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <Button className="gap-2" onClick={handleRun} disabled={isRunning || selectedStrategies.length < 2}>
          {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
          {isRunning ? "Running comparison..." : "Run Comparison"}
        </Button>
      </div>

      {/* Results */}
      {resultEntries.length > 0 && (
        <>
          {/* Best Strategy Summary */}
          <BestStrategySummary results={results!} />

          {/* Overlay Equity Chart */}
          <div className="card-elevated p-4">
            <h3 className="text-sm font-semibold mb-3">Equity Curves (Normalized to % Returns)</h3>
            <OverlayEquityChart results={results!} />
          </div>

          {/* Correlation Matrix */}
          <div className="card-elevated p-4">
            <h3 className="text-sm font-semibold mb-3">Return Correlation Matrix</h3>
            <CorrelationMatrix results={results!} />
          </div>

          {/* Comparison Table */}
          <div className="card-elevated overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/50">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Strategy</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Return %</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">CAGR</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Sharpe</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Max DD</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Win Rate</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Trades</th>
                </tr>
              </thead>
              <tbody>
                {resultEntries.map(([name, result], i) => (
                  <tr key={name} className="border-b border-border/50 hover:bg-secondary/30">
                    <td className="px-4 py-3 font-medium flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS[i] }} />
                      {strategyDisplayName(name)}
                    </td>
                    <td className={cn("px-4 py-3 text-right font-mono-numbers font-semibold", pnlColor(result.total_return_pct))}>{formatPercent(result.total_return_pct)}</td>
                    <td className={cn("px-4 py-3 text-right font-mono-numbers", pnlColor(result.metrics.returns.cagr))}>{formatPercent(result.metrics.returns.cagr)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers">{formatNumber(result.metrics.risk.sharpe_ratio)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers text-loss">{formatPercent(result.metrics.drawdown.max_drawdown)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers">{formatPercent(result.metrics.trades.win_rate)}</td>
                    <td className="px-4 py-3 text-right font-mono-numbers">{result.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card-elevated p-4">
              <h3 className="text-sm font-semibold mb-3">Equity Curves</h3>
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
              <h3 className="text-sm font-semibold mb-3">Performance Radar</h3>
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
