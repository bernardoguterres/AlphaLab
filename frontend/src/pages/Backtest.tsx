import { useState } from "react";
import { useBacktestStore } from "@/stores/backtestStore";
import { runBacktest, fetchData } from "@/services/api";
import type { StrategyType, StrategyParams, BacktestResult, MACrossoverParams, RSIMeanReversionParams, MomentumBreakoutParams } from "@/types";
import { STRATEGY_INFO, DEFAULT_PARAMS } from "@/types";
import { MetricCard } from "@/components/metrics/MetricCard";
import { MetricsTabs } from "@/components/metrics/MetricsTabs";
import { EquityChart } from "@/components/charts/EquityChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { TradeTable } from "@/components/charts/TradeTable";
import { formatPercent, formatCurrency, formatNumber, pnlColor, qualityColor, strategyDisplayName } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { Loader2, TrendingUp, TrendingDown, BarChart3, Target, Percent, Activity, ChevronDown, Download, Save } from "lucide-react";

export default function Backtest() {
  const { currentResult, setCurrentResult, addToHistory } = useBacktestStore();

  // Form state
  const [ticker, setTicker] = useState("AAPL");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [interval, setInterval] = useState("1d");
  const [strategy, setStrategy] = useState<StrategyType>("ma_crossover");
  const [params, setParams] = useState<Record<StrategyType, StrategyParams>>({ ...DEFAULT_PARAMS });
  const [initialCapital, setInitialCapital] = useState(100000);
  const [positionSizing, setPositionSizing] = useState<"equal_weight" | "risk_parity" | "volatility_weighted">("equal_weight");
  const [monteCarloRuns, setMonteCarloRuns] = useState(0);

  // UI state
  const [isFetching, setIsFetching] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [qualityScore, setQualityScore] = useState<number | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const currentParams = params[strategy];

  const updateParam = (key: string, value: number | boolean) => {
    setParams((prev) => ({
      ...prev,
      [strategy]: { ...prev[strategy], [key]: value },
    }));
  };

  const handleFetchData = async () => {
    setIsFetching(true);
    setQualityScore(null);
    try {
      const result = await fetchData([ticker.toUpperCase()], startDate, endDate, interval);
      const tickerData = result.data?.[ticker.toUpperCase()];
      if (tickerData) {
        setQualityScore(tickerData.quality_score);
        toast.success(`Fetched ${tickerData.records} records for ${ticker.toUpperCase()}`);
      }
      if (result.errors?.length) {
        toast.error(result.errors.join(", "));
      }
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Failed to fetch data");
    } finally {
      setIsFetching(false);
    }
  };

  const handleRunBacktest = async () => {
    setIsRunning(true);
    try {
      const result = await runBacktest({
        ticker: ticker.toUpperCase(),
        strategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        params: currentParams,
        position_sizing: positionSizing,
        monte_carlo_runs: monteCarloRuns,
      });
      setCurrentResult(result);
      toast.success("Backtest completed!");
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Backtest failed");
    } finally {
      setIsRunning(false);
    }
  };

  const handleSaveToHistory = () => {
    if (!currentResult) return;
    addToHistory({
      id: currentResult.backtest_id || Date.now().toString(),
      date: new Date().toISOString(),
      ticker: ticker.toUpperCase(),
      strategy,
      total_return_pct: currentResult.total_return_pct,
      sharpe_ratio: currentResult.metrics.risk.sharpe_ratio,
      max_drawdown: currentResult.metrics.drawdown.max_drawdown,
      total_trades: currentResult.total_trades,
      result: currentResult,
    });
    toast.success("Saved to history!");
  };

  const handleExportJSON = () => {
    if (!currentResult) return;
    const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backtest_${ticker}_${strategy}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Left Panel - Configuration */}
      <div className="w-[380px] shrink-0 border-r border-border overflow-y-auto p-5 space-y-5">
        <h2 className="font-display text-lg font-bold">Configuration</h2>

        {/* Data Input */}
        <section className="space-y-3">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Data Input</h3>
          <div>
            <Label className="text-xs">Ticker Symbol</Label>
            <Input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              className="mt-1 font-mono-numbers"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-xs">Start Date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-1 text-xs" />
            </div>
            <div>
              <Label className="text-xs">End Date</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="mt-1 text-xs" />
            </div>
          </div>
          <div>
            <Label className="text-xs">Interval</Label>
            <Select value={interval} onValueChange={setInterval}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="1d">Daily</SelectItem>
                <SelectItem value="1wk">Weekly</SelectItem>
                <SelectItem value="1mo">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" size="sm" className="w-full gap-2" onClick={handleFetchData} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-3 w-3 animate-spin" /> : <Activity className="h-3 w-3" />}
            Fetch Data
          </Button>
          {qualityScore !== null && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Quality Score:</span>
              <span className={cn("font-mono-numbers font-semibold", qualityColor(qualityScore))}>
                {(qualityScore * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </section>

        {/* Strategy Selection */}
        <section className="space-y-3">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Strategy</h3>
          <div className="space-y-2">
            {(Object.keys(STRATEGY_INFO) as StrategyType[]).map((key) => (
              <button
                key={key}
                onClick={() => setStrategy(key)}
                className={cn(
                  "w-full text-left p-3 rounded-lg border transition-colors",
                  strategy === key
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground/30"
                )}
              >
                <div className="text-sm font-medium">{STRATEGY_INFO[key].name}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{STRATEGY_INFO[key].description}</div>
              </button>
            ))}
          </div>
        </section>

        {/* Strategy Parameters */}
        <section className="space-y-3">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Parameters</h3>
          {strategy === "ma_crossover" && (
            <MACrossoverForm params={currentParams as MACrossoverParams} onChange={updateParam} />
          )}
          {strategy === "rsi_mean_reversion" && (
            <RSIMeanReversionForm params={currentParams as RSIMeanReversionParams} onChange={updateParam} />
          )}
          {strategy === "momentum_breakout" && (
            <MomentumBreakoutForm params={currentParams as MomentumBreakoutParams} onChange={updateParam} />
          )}
        </section>

        {/* Advanced Settings */}
        <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
          <CollapsibleTrigger className="flex items-center justify-between w-full text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Advanced Settings
            <ChevronDown className={cn("h-3 w-3 transition-transform", advancedOpen && "rotate-180")} />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-3 mt-3">
            <div>
              <Label className="text-xs">Initial Capital</Label>
              <Input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
                min={1000}
                className="mt-1 font-mono-numbers"
              />
            </div>
            <div>
              <Label className="text-xs">Position Sizing</Label>
              <Select value={positionSizing} onValueChange={(v: any) => setPositionSizing(v)}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="equal_weight">Equal Weight</SelectItem>
                  <SelectItem value="risk_parity">Risk Parity</SelectItem>
                  <SelectItem value="volatility_weighted">Volatility Weighted</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Monte Carlo Runs</Label>
              <Input
                type="number"
                value={monteCarloRuns}
                onChange={(e) => setMonteCarloRuns(Number(e.target.value))}
                min={0}
                max={1000}
                className="mt-1 font-mono-numbers"
              />
              <p className="text-[10px] text-muted-foreground mt-1">0 = disabled. Higher values give better statistical confidence but take longer.</p>
            </div>
          </CollapsibleContent>
        </Collapsible>

        <Button className="w-full gap-2" size="lg" onClick={handleRunBacktest} disabled={isRunning}>
          {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
          {isRunning ? `Backtesting ${strategyDisplayName(strategy)} on ${ticker}...` : "Run Backtest"}
        </Button>
      </div>

      {/* Right Panel - Results */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {!currentResult ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <BarChart3 className="h-16 w-16 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold text-muted-foreground">No Results Yet</h3>
            <p className="text-sm text-muted-foreground/70 mt-1">Configure your strategy and run a backtest to see results</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold">
                Results — {currentResult.ticker || ticker} · {strategyDisplayName(currentResult.strategy)}
              </h2>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="gap-1.5" onClick={handleSaveToHistory}>
                  <Save className="h-3 w-3" /> Save
                </Button>
                <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExportJSON}>
                  <Download className="h-3 w-3" /> Export JSON
                </Button>
              </div>
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-3 xl:grid-cols-6 gap-3">
              <MetricCard
                label="Total Return"
                value={formatPercent(currentResult.total_return_pct)}
                colorClass={pnlColor(currentResult.total_return_pct)}
                icon={currentResult.total_return_pct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              />
              <MetricCard label="CAGR" value={formatPercent(currentResult.metrics.returns.cagr)} colorClass={pnlColor(currentResult.metrics.returns.cagr)} />
              <MetricCard label="Sharpe Ratio" value={formatNumber(currentResult.metrics.risk.sharpe_ratio)} icon={<Target className="h-4 w-4" />} />
              <MetricCard label="Max Drawdown" value={formatPercent(currentResult.metrics.drawdown.max_drawdown)} colorClass="text-loss" />
              <MetricCard label="Win Rate" value={formatPercent(currentResult.metrics.trades.win_rate)} icon={<Percent className="h-4 w-4" />} />
              <MetricCard label="Total Trades" value={currentResult.total_trades.toString()} />
            </div>

            {/* Equity Curve */}
            <div className="card-elevated p-4">
              <h3 className="text-sm font-semibold mb-3">Equity Curve</h3>
              <EquityChart
                data={currentResult.equity_curve}
                benchmarkData={currentResult.benchmark?.equity_curve}
              />
            </div>

            {/* Drawdown */}
            <div className="card-elevated p-4">
              <h3 className="text-sm font-semibold mb-3">Drawdown</h3>
              <DrawdownChart equityCurve={currentResult.equity_curve} />
            </div>

            {/* Detailed Metrics */}
            <div className="card-elevated p-4">
              <h3 className="text-sm font-semibold mb-3">Detailed Metrics</h3>
              <MetricsTabs metrics={currentResult.metrics} />
            </div>

            {/* Monte Carlo */}
            {currentResult.monte_carlo && (
              <div className="card-elevated p-4">
                <h3 className="text-sm font-semibold mb-3">Monte Carlo Simulation</h3>
                <div className="grid grid-cols-5 gap-3">
                  <MetricCard label="5th Percentile" value={formatPercent(currentResult.monte_carlo.percentile_5)} colorClass="text-loss" className="!p-3" />
                  <MetricCard label="25th Percentile" value={formatPercent(currentResult.monte_carlo.percentile_25)} className="!p-3" />
                  <MetricCard label="Median" value={formatPercent(currentResult.monte_carlo.median)} className="!p-3" />
                  <MetricCard label="75th Percentile" value={formatPercent(currentResult.monte_carlo.percentile_75)} className="!p-3" />
                  <MetricCard label="95th Percentile" value={formatPercent(currentResult.monte_carlo.percentile_95)} colorClass="text-gain" className="!p-3" />
                </div>
              </div>
            )}

            {/* Trade List */}
            <div className="card-elevated p-4">
              <h3 className="text-sm font-semibold mb-3">Trade List</h3>
              <TradeTable trades={currentResult.trades} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Parameter Forms
function ParamSlider({ label, value, onChange, min, max, step = 1 }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <Label className="text-xs">{label}</Label>
        <span className="font-mono-numbers text-xs text-muted-foreground">{value}</span>
      </div>
      <Slider value={[value]} onValueChange={([v]) => onChange(v)} min={min} max={max} step={step} />
    </div>
  );
}

function MACrossoverForm({ params, onChange }: { params: MACrossoverParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="space-y-3">
      <ParamSlider label="Short Window" value={params.short_window} onChange={(v) => onChange("short_window", v)} min={10} max={100} />
      <ParamSlider label="Long Window" value={params.long_window} onChange={(v) => onChange("long_window", v)} min={50} max={300} />
      <div className="flex items-center gap-2">
        <Checkbox checked={params.volume_confirmation} onCheckedChange={(v) => onChange("volume_confirmation", !!v)} id="vol" />
        <Label htmlFor="vol" className="text-xs">Volume Confirmation</Label>
      </div>
      <ParamSlider label="Cooldown Days" value={params.cooldown_days} onChange={(v) => onChange("cooldown_days", v)} min={0} max={30} />
    </div>
  );
}

function RSIMeanReversionForm({ params, onChange }: { params: RSIMeanReversionParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="space-y-3">
      <ParamSlider label="RSI Period" value={params.rsi_period} onChange={(v) => onChange("rsi_period", v)} min={7} max={30} />
      <ParamSlider label="Oversold" value={params.oversold} onChange={(v) => onChange("oversold", v)} min={20} max={40} />
      <ParamSlider label="Overbought" value={params.overbought} onChange={(v) => onChange("overbought", v)} min={60} max={80} />
      <div className="flex items-center gap-2">
        <Checkbox checked={params.use_bb_confirmation} onCheckedChange={(v) => onChange("use_bb_confirmation", !!v)} id="bb" />
        <Label htmlFor="bb" className="text-xs">Bollinger Band Confirmation</Label>
      </div>
      <ParamSlider label="ADX Threshold" value={params.adx_threshold} onChange={(v) => onChange("adx_threshold", v)} min={20} max={40} />
    </div>
  );
}

function MomentumBreakoutForm({ params, onChange }: { params: MomentumBreakoutParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="space-y-3">
      <ParamSlider label="Lookback" value={params.lookback} onChange={(v) => onChange("lookback", v)} min={10} max={60} />
      <ParamSlider label="Volume Surge %" value={params.volume_surge_pct} onChange={(v) => onChange("volume_surge_pct", v)} min={100} max={300} />
      <ParamSlider label="RSI Min" value={params.rsi_min} onChange={(v) => onChange("rsi_min", v)} min={40} max={60} />
      <ParamSlider label="Stop Loss ATR Mult" value={params.stop_loss_atr_mult} onChange={(v) => onChange("stop_loss_atr_mult", v)} min={1} max={5} step={0.1} />
    </div>
  );
}
