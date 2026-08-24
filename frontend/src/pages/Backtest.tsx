import { useState } from "react";
import { useBacktestStore } from "@/stores/backtestStore";
import { runBacktest, fetchData } from "@/services/api";
import type { StrategyType, StrategyParams, BacktestResult, RawOrder, MACrossoverParams, RSIMeanReversionParams, RSISimpleParams, MomentumBreakoutParams, BollingerBreakoutParams, VWAPReversionParams, BollingerRSIComboParams, TrendAdaptiveRSIParams, GreenblattWeeklyParams, RiskSettings, EquityCurvePoint } from "@/types";
import { STRATEGY_INFO, DEFAULT_PARAMS, DEFAULT_RISK_SETTINGS } from "@/types";
import { MetricCard } from "@/components/metrics/MetricCard";
import { MetricsTabs } from "@/components/metrics/MetricsTabs";
import { EquityChart } from "@/components/charts/EquityChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { MonthlyReturnsHeatmap } from "@/components/charts/MonthlyReturnsHeatmap";
import { TradeTable } from "@/components/charts/TradeTable";
import { pairTradesFIFO } from "@/utils/tradePairing";
import { ExportButton } from "@/components/export/ExportButton";
import { RiskSettingsPanel } from "@/components/backtest/RiskSettingsPanel";
import { BatchBacktest } from "@/components/backtest/BatchBacktest";
import ParameterOptimize from "@/components/backtest/ParameterOptimize";
import { formatPercent, formatCurrency, formatNumber, formatDate, pnlColor, qualityColor, strategyDisplayName } from "@/utils/formatters";
import { STRATEGY_META } from "@/utils/strategyMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  Loader2, TrendingUp, TrendingDown, Target, Percent, Activity, ChevronDown, Save, ListChecks,
  Play, LineChart as LineChartIcon, FlaskConical, CheckCircle2, Circle,
  AlertTriangle, ShieldQuestion, Lock, Rocket, ArrowRight,
} from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

const GHOST_EQUITY_BARS = [38, 42, 40, 46, 44, 50, 48, 55, 52, 60, 58, 66, 63, 70, 68, 76, 74, 82, 80, 88];

// Real, backend-enforced export restrictions (mirrors the 422 responses
// returned by POST /api/strategies/export in
// backend/alphalab/api/blueprints/backtest.py - a strategy listed here is
// rejected by the server regardless of what the UI does, so the panel
// below only ever *previews* that server-side rule, never invents one).
const EXPORT_BLOCKED: Partial<Record<StrategyType, string>> = {
  vwap_reversion:
    "Requires an intraday timeframe (1Hour/15Min); AlphaLab's data layer only fetches 1Day/1Week/1Month bars, so no export could satisfy AlphaLive's intraday validation. Backtesting is supported - exporting is not.",
  rsi_simple:
    "Research/testing strategy only - AlphaLive has no matching entry in its StrategyName schema and would reject the export. Use rsi_mean_reversion for a deployable RSI strategy.",
};

const RESULT_TABS = ["overview", "drawdown", "monthly", "trades", "detailed"] as const;
type ResultTab = (typeof RESULT_TABS)[number];

// Client-side zoom over the real, already-fetched equity curve - no backend
// range param exists, so "1M"/"3M"/etc. slice the real series by date
// rather than requesting different data.
const CHART_RANGES = ["1M", "3M", "1Y", "YTD", "All"] as const;
type ChartRange = (typeof CHART_RANGES)[number];

function sliceByRange(curve: EquityCurvePoint[], range: ChartRange): EquityCurvePoint[] {
  if (range === "All" || curve.length === 0) return curve;
  const lastDate = new Date(curve[curve.length - 1].date);
  const cutoff = new Date(lastDate);
  if (range === "1M") cutoff.setMonth(cutoff.getMonth() - 1);
  else if (range === "3M") cutoff.setMonth(cutoff.getMonth() - 3);
  else if (range === "1Y") cutoff.setFullYear(cutoff.getFullYear() - 1);
  else if (range === "YTD") { cutoff.setMonth(0); cutoff.setDate(1); }
  const sliced = curve.filter((p) => new Date(p.date) >= cutoff);
  return sliced.length >= 2 ? sliced : curve;
}

// Real, per-strategy parameter summary shown in the collapsed trigger -
// every value here is read straight from the live params object, nothing
// invented.
function strategyParamsSummary(strategy: StrategyType, params: StrategyParams): string {
  switch (strategy) {
    case "ma_crossover": {
      const p = params as MACrossoverParams;
      return `Short MA ${p.short_window} - Long MA ${p.long_window} - Cooldown ${p.cooldown_days}d`;
    }
    case "rsi_mean_reversion": {
      const p = params as RSIMeanReversionParams;
      return `RSI ${p.rsi_period} - Oversold ${p.oversold} - Overbought ${p.overbought}`;
    }
    case "rsi_simple": {
      const p = params as RSISimpleParams;
      return `RSI ${p.period} - Oversold ${p.oversold} - Overbought ${p.overbought}`;
    }
    case "momentum_breakout": {
      const p = params as MomentumBreakoutParams;
      return `Lookback ${p.lookback} - Volume Surge ${p.volume_surge_pct}% - Stop ${p.stop_loss_atr_mult}x ATR`;
    }
    case "bollinger_breakout": {
      const p = params as BollingerBreakoutParams;
      return `BB ${p.bb_period}/${p.bb_std_dev}sigma - Confirm ${p.confirmation_bars} bars`;
    }
    case "vwap_reversion": {
      const p = params as VWAPReversionParams;
      return `VWAP ${p.vwap_period} - Deviation ${p.deviation_threshold}sigma - RSI ${p.rsi_period}`;
    }
    case "bollinger_rsi_combo": {
      const p = params as BollingerRSIComboParams;
      return `BB ${p.bb_period}/${p.bb_std} - RSI ${p.rsi_period} (${p.rsi_oversold}/${p.rsi_overbought})`;
    }
    case "trend_adaptive_rsi": {
      const p = params as TrendAdaptiveRSIParams;
      return `RSI ${p.rsi_period} - Trend SMA ${p.trend_sma} - Lookback ${p.trend_lookback}`;
    }
    case "greenblatt_weekly": {
      const p = params as GreenblattWeeklyParams;
      return `SMA ${p.fast_sma}/${p.slow_sma}w - Min Hold ${p.min_hold_bars}w - Trailing Stop ${(p.trailing_stop_pct * 100).toFixed(0)}%`;
    }
    default:
      return "";
  }
}

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
  const [riskSettings, setRiskSettings] = useState<RiskSettings>(DEFAULT_RISK_SETTINGS);

  // UI state
  const [isFetching, setIsFetching] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [qualityScore, setQualityScore] = useState<number | null>(null);
  const [qualityContext, setQualityContext] = useState<{ ticker: string; startDate: string; endDate: string } | null>(null);
  const [resultTab, setResultTab] = useState<ResultTab>("overview");
  const [chartRange, setChartRange] = useState<ChartRange>("All");

  // Snapshot of the exact config that produced `currentResult` - captured at
  // submit time so Research Checks / Export keep describing the completed
  // run even if the form is edited afterward without re-running.
  const [submittedConfig, setSubmittedConfig] = useState<{
    ticker: string;
    strategy: StrategyType;
    startDate: string;
    endDate: string;
    initialCapital: number;
    riskSettings: RiskSettings;
  } | null>(null);

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
    setQualityContext(null);
    try {
      const result = await fetchData([ticker.toUpperCase()], startDate, endDate, interval);
      const tickerData = result.data?.[ticker.toUpperCase()];
      if (tickerData) {
        setQualityScore(tickerData.quality_score);
        setQualityContext({ ticker: ticker.toUpperCase(), startDate, endDate });
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
        risk_settings: riskSettings,
      });
      setCurrentResult(result);
      setSubmittedConfig({
        ticker: ticker.toUpperCase(),
        strategy,
        startDate,
        endDate,
        initialCapital,
        riskSettings,
      });
      setResultTab("overview");
      setChartRange("All");
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
      max_drawdown: currentResult.metrics.drawdown.max_drawdown_pct,
      total_trades: currentResult.total_trades,
      result: currentResult,
    });
    toast.success("Saved to history!");
  };

  const pairedTrades = currentResult ? pairTradesFIFO(currentResult.trades) : [];
  const ledgerRows = currentResult ? buildLedgerRows(currentResult.trades) : [];
  const recentLedgerRows = [...ledgerRows]
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 5);

  // Export eligibility describes the completed run, so it's keyed off the
  // submitted-config snapshot's strategy - not the live selector (which may
  // have been changed since) and not currentResult.strategy (the backend
  // echoes it back in a different casing, "RSI_Simple" vs the StrategyType
  // union's "rsi_simple").
  const exportBlockReason = submittedConfig ? EXPORT_BLOCKED[submittedConfig.strategy] : undefined;

  // A fetched quality score only describes the completed run if it was
  // fetched for the exact same ticker/window that was actually submitted -
  // otherwise it's stale evidence and must not be shown as verified.
  const qualityScoreForRun =
    submittedConfig && qualityContext &&
    qualityContext.ticker === submittedConfig.ticker &&
    qualityContext.startDate === submittedConfig.startDate &&
    qualityContext.endDate === submittedConfig.endDate
      ? qualityScore
      : null;

  const slicedEquityCurve = currentResult ? sliceByRange(currentResult.equity_curve, chartRange) : [];
  const slicedBenchmarkCurve = currentResult?.benchmark ? sliceByRange(currentResult.benchmark.equity_curve, chartRange) : undefined;

  return (
    <div className="h-screen overflow-hidden flex flex-col">
      {/* Compact header */}
      <div className="shrink-0 border-b border-border bg-card/40 backdrop-blur-sm px-5 py-3.5 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 text-primary p-2 shrink-0">
            <FlaskConical className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-foreground leading-none">Backtest Studio</h1>
            <p className="text-xs text-muted-foreground mt-1">Configure, validate, and run strategy research</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleSaveToHistory} disabled={!currentResult}>
            <Save className="h-3.5 w-3.5" /> Save Configuration
          </Button>
          <Button onClick={handleRunBacktest} disabled={isRunning} size="sm" className="gap-2">
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {isRunning ? "Running..." : "Run Backtest"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="single" className="flex-1 min-h-0 flex flex-col">
        <TabsList className="mx-5 mt-3 mb-0 w-fit shrink-0">
          <TabsTrigger value="single">Single Backtest</TabsTrigger>
          <TabsTrigger value="batch">Batch Backtest</TabsTrigger>
          <TabsTrigger value="optimize">Optimize Parameters</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="flex-1 min-h-0 overflow-y-auto mt-3">
          <div className="px-5 pb-6 space-y-4">
            {/* Horizontal configuration bar */}
            <div className="card-elevated p-3.5">
              <div className="flex flex-wrap items-stretch gap-3">
                <ConfigField label="Strategy" className="w-[220px]">
                  <Select value={strategy} onValueChange={(v: StrategyType) => setStrategy(v)}>
                    <SelectTrigger className="h-9 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(STRATEGY_INFO) as StrategyType[]).map((key) => {
                        const Icon = STRATEGY_META[key].icon;
                        return (
                          <SelectItem key={key} value={key}>
                            <span className="flex items-center gap-2">
                              <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                              {STRATEGY_INFO[key].name}
                            </span>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <span className="text-[10px] text-muted-foreground/85 mt-1 block truncate">
                    {STRATEGY_META[strategy].category}
                  </span>
                </ConfigField>

                <ConfigField label="Ticker" className="w-[110px]">
                  <Input
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    className="h-9 text-sm font-mono-numbers"
                  />
                </ConfigField>

                <ConfigField label="Initial Capital" className="w-[140px]">
                  <Input
                    type="number"
                    value={initialCapital}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    min={1000}
                    className="h-9 text-sm font-mono-numbers"
                  />
                </ConfigField>

                <ConfigField label="Test Window" className="min-w-[210px]">
                  <div className="flex items-center gap-1.5">
                    <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="h-9 text-xs" />
                    <span className="text-muted-foreground text-xs shrink-0">-</span>
                    <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="h-9 text-xs" />
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <button
                      onClick={handleFetchData}
                      disabled={isFetching}
                      className="text-[10px] font-semibold text-primary hover:text-primary/80 disabled:opacity-50 inline-flex items-center gap-1"
                    >
                      {isFetching ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <Activity className="h-2.5 w-2.5" />}
                      Fetch data
                    </button>
                    {qualityScore !== null && (
                      <span className={cn("text-[10px] font-mono-numbers font-semibold", qualityColor(qualityScore))}>
                        Quality {(qualityScore * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </ConfigField>

                <ConfigField label="Interval" className="w-[110px]">
                  <Select value={interval} onValueChange={setInterval}>
                    <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1d">Daily</SelectItem>
                      <SelectItem value="1wk">Weekly</SelectItem>
                      <SelectItem value="1mo">Monthly</SelectItem>
                    </SelectContent>
                  </Select>
                </ConfigField>

                <ConfigField label="Allocation & Simulation" className="min-w-[220px] flex-1">
                  <div className="flex items-center gap-1.5">
                    <Select value={positionSizing} onValueChange={(v: "equal_weight" | "risk_parity" | "volatility_weighted") => setPositionSizing(v)}>
                      <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="equal_weight">Equal Weight</SelectItem>
                        <SelectItem value="risk_parity">Risk Parity</SelectItem>
                        <SelectItem value="volatility_weighted">Volatility Weighted</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      value={monteCarloRuns}
                      onChange={(e) => setMonteCarloRuns(Number(e.target.value))}
                      min={0}
                      max={1000}
                      title="Monte Carlo runs (0 = disabled)"
                      className="h-9 w-16 text-xs font-mono-numbers shrink-0"
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground/85 mt-1 block truncate">
                    Position sizing method - Monte Carlo runs: {monteCarloRuns || "off"}
                  </span>
                </ConfigField>
              </div>
            </div>

            {/* Secondary strip: strategy parameters + risk settings, both collapsible */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <StrategyParamsPanel strategy={strategy} params={currentParams} onChange={updateParam} />
              <RiskSettingsPanel settings={riskSettings} onChange={setRiskSettings} />
            </div>

            {/* Primary results area */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="xl:col-span-2 space-y-4 min-w-0">
                {!currentResult ? (
                  <div className="space-y-3">
                    <EmptyState
                      size="sm"
                      icon={LineChartIcon}
                      title={qualityScore !== null ? "Data ready - run a backtest to see results" : "Fetch data and run a backtest"}
                      description="Your equity curve, drawdown, and metrics will appear here."
                    />
                    <div className="grid grid-cols-3 xl:grid-cols-5 gap-3 opacity-50 pointer-events-none select-none">
                      <MetricCard label="Net Return" value="-" icon={<TrendingUp className="h-4 w-4" />} />
                      <MetricCard label="Sharpe Ratio" value="-" icon={<Target className="h-4 w-4" />} />
                      <MetricCard label="Max Drawdown" value="-" />
                      <MetricCard label="Win Rate" value="-" icon={<Percent className="h-4 w-4" />} />
                      <MetricCard label="Profit Factor" value="-" />
                    </div>
                    <div className="card-elevated p-3">
                      <h3 className="section-label mb-2">Portfolio Value Preview</h3>
                      <div className="h-20 rounded-lg border border-border/40 bg-secondary/10 flex items-end gap-1 p-2.5">
                        {GHOST_EQUITY_BARS.map((h, i) => (
                          <Skeleton key={i} className="flex-1 rounded-sm" style={{ height: `${h}%` }} />
                        ))}
                      </div>
                    </div>
                    <div className="card-elevated p-3">
                      <h4 className="section-label mb-2 flex items-center gap-1.5">
                        <ListChecks className="h-3.5 w-3.5" /> Workflow
                      </h4>
                      <ol className="flex flex-wrap gap-x-4 gap-y-1.5">
                        {[
                          { label: "Select ticker and date range", done: true },
                          { label: "Fetch data", done: qualityScore !== null },
                          { label: "Choose strategy", done: true },
                          { label: "Run backtest", done: isRunning },
                        ].map((step, i) => (
                          <li key={step.label} className="flex items-center gap-1.5 text-xs">
                            <span
                              className={cn(
                                "flex items-center justify-center h-4 w-4 rounded-full text-[9px] font-bold shrink-0",
                                step.done ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground border border-border"
                              )}
                            >
                              {i + 1}
                            </span>
                            <span className={step.done ? "text-foreground" : "text-muted-foreground"}>{step.label}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between flex-wrap gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className={cn("rounded-lg p-2 shrink-0 bg-secondary/60", pnlColor(currentResult.total_return_pct))}>
                          {currentResult.total_return_pct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                        </div>
                        <h2 className="text-lg font-bold tracking-tight text-foreground">
                          {submittedConfig?.ticker ?? currentResult.ticker ?? ticker} - {strategyDisplayName(submittedConfig?.strategy ?? currentResult.strategy)}
                        </h2>
                      </div>
                      <ExportButton
                        backtestId={currentResult.backtest_id || ""}
                        strategyName={submittedConfig?.strategy ?? strategy}
                        ticker={submittedConfig?.ticker ?? ticker}
                        variant="outline"
                        size="sm"
                        showLabel={true}
                      />
                    </div>

                    {/* Portfolio value / equity curve, strategy vs benchmark */}
                    <div className="card-elevated p-4">
                      <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                        <h3 className="section-label">Portfolio Value</h3>
                        <div className="flex items-center gap-1 rounded-lg border border-border/60 p-0.5">
                          {CHART_RANGES.map((r) => (
                            <button
                              key={r}
                              onClick={() => setChartRange(r)}
                              className={cn(
                                "px-2 py-1 rounded-md text-[11px] font-semibold transition-colors",
                                chartRange === r ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                              )}
                            >
                              {r}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-5 mb-3">
                        <div className="flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full bg-primary shrink-0" />
                          <span className="text-xs text-muted-foreground">Portfolio</span>
                          <span className="font-mono-numbers text-xs font-semibold">{formatCurrency(currentResult.final_value)}</span>
                          <span className={cn("font-mono-numbers text-xs font-semibold", pnlColor(currentResult.total_return_pct))}>
                            {formatPercent(currentResult.total_return_pct)}
                          </span>
                        </div>
                        {currentResult.benchmark && (
                          <div className="flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-full bg-lab-secondary shrink-0" />
                            <span className="text-xs text-muted-foreground">Buy &amp; Hold</span>
                            <span className={cn("font-mono-numbers text-xs font-semibold", pnlColor(currentResult.benchmark.total_return_pct))}>
                              {formatPercent(currentResult.benchmark.total_return_pct)}
                            </span>
                          </div>
                        )}
                      </div>
                      <EquityChart data={slicedEquityCurve} benchmarkData={slicedBenchmarkCurve} />
                    </div>

                    {/* Key metrics */}
                    <div className="grid grid-cols-3 xl:grid-cols-5 gap-3">
                      <MetricCard
                        label="Net Return"
                        value={formatPercent(currentResult.total_return_pct)}
                        colorClass={pnlColor(currentResult.total_return_pct)}
                        icon={currentResult.total_return_pct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                      />
                      <MetricCard label="Sharpe Ratio" value={formatNumber(currentResult.metrics.risk.sharpe_ratio)} icon={<Target className="h-4 w-4" />} />
                      <MetricCard label="Max Drawdown" value={formatPercent(currentResult.metrics.drawdown.max_drawdown_pct)} colorClass="text-loss" />
                      <MetricCard label="Win Rate" value={formatPercent(currentResult.metrics.trades.win_rate * 100)} icon={<Percent className="h-4 w-4" />} />
                      <MetricCard label="Profit Factor" value={formatNumber(currentResult.metrics.trades.profit_factor)} />
                    </div>

                    {/* Result tabs */}
                    <div className="card-elevated p-4">
                      <Tabs value={resultTab} onValueChange={(v: ResultTab) => setResultTab(v)} className="w-full">
                        <TabsList className="grid w-full grid-cols-5">
                          <TabsTrigger value="overview">Overview</TabsTrigger>
                          <TabsTrigger value="drawdown">Drawdown</TabsTrigger>
                          <TabsTrigger value="monthly">Monthly Returns</TabsTrigger>
                          <TabsTrigger value="trades">Trades</TabsTrigger>
                          <TabsTrigger value="detailed">Detailed Metrics</TabsTrigger>
                        </TabsList>

                        <TabsContent value="overview" className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-x-8">
                          <div>
                            <h4 className="section-label mb-2">Returns</h4>
                            <StatRow label="Total Return" value={formatPercent(currentResult.metrics.returns.total_return_pct)} />
                            <StatRow label="CAGR" value={formatPercent(currentResult.metrics.returns.cagr_pct)} />
                            <StatRow label="Mean Daily Return" value={formatPercent(currentResult.metrics.returns.mean_daily_return, 4)} />
                            <StatRow label="Skewness" value={formatNumber(currentResult.metrics.returns.skewness)} />
                            <StatRow label="Kurtosis" value={formatNumber(currentResult.metrics.returns.kurtosis)} />
                          </div>
                          <div>
                            <h4 className="section-label mb-2">vs. Benchmark</h4>
                            <StatRow label="Beta" value={formatNumber(currentResult.metrics.vs_benchmark.beta)} />
                            <StatRow label="Alpha (annual)" value={formatPercent(currentResult.metrics.vs_benchmark.alpha_annual_pct)} />
                            <StatRow label="Tracking Error" value={formatPercent(currentResult.metrics.vs_benchmark.tracking_error_pct)} />
                            <StatRow label="Information Ratio" value={formatNumber(currentResult.metrics.vs_benchmark.information_ratio)} />
                            <StatRow label="Up / Down Capture" value={`${formatPercent(currentResult.metrics.vs_benchmark.up_capture_pct)} / ${formatPercent(currentResult.metrics.vs_benchmark.down_capture_pct)}`} />
                          </div>
                        </TabsContent>

                        <TabsContent value="drawdown" className="mt-4">
                          <DrawdownChart equityCurve={currentResult.equity_curve} />
                        </TabsContent>

                        <TabsContent value="monthly" className="mt-4">
                          <MonthlyReturnsHeatmap equityCurve={currentResult.equity_curve} />
                        </TabsContent>

                        <TabsContent value="trades" className="mt-4">
                          <TradeTable trades={pairedTrades} />
                        </TabsContent>

                        <TabsContent value="detailed" className="mt-4">
                          <MetricsTabs metrics={currentResult.metrics} />
                        </TabsContent>
                      </Tabs>
                    </div>

                    {/* Trade ledger */}
                    <div className="card-elevated p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="section-label flex items-center gap-1.5">Recent Trades</h3>
                        {ledgerRows.length > 0 && (
                          <span className="text-[10px] text-muted-foreground">
                            Showing last {recentLedgerRows.length} of {ledgerRows.length} orders
                          </span>
                        )}
                      </div>
                      {ledgerRows.length === 0 ? (
                        <p className="text-xs text-muted-foreground py-4 text-center">
                          No trades executed in this window - the strategy's entry conditions never fired.
                        </p>
                      ) : (
                        <>
                          <TradeLedgerPreview rows={recentLedgerRows} />
                          <button
                            onClick={() => setResultTab("trades")}
                            className="mt-2.5 text-xs font-semibold text-primary hover:text-primary/80 inline-flex items-center gap-1"
                          >
                            View all trades <ArrowRight className="h-3 w-3" />
                          </button>
                        </>
                      )}
                    </div>

                    {/* Monte Carlo */}
                    {currentResult.monte_carlo && (
                      <div className="card-elevated p-4">
                        <h3 className="text-sm font-semibold mb-3">Monte Carlo Simulation</h3>
                        <p className="text-xs text-muted-foreground mb-3">
                          Distribution of final portfolio value across {currentResult.monte_carlo.runs} randomized runs.
                        </p>
                        <div className="grid grid-cols-5 gap-3">
                          <MetricCard label="5th Percentile" value={formatCurrency(currentResult.monte_carlo.percentile_5)} colorClass="text-loss" className="!p-3" />
                          <MetricCard label="Min" value={formatCurrency(currentResult.monte_carlo.min_final_value)} colorClass="text-loss" className="!p-3" />
                          <MetricCard label="Median" value={formatCurrency(currentResult.monte_carlo.median_final_value)} className="!p-3" />
                          <MetricCard label="Max" value={formatCurrency(currentResult.monte_carlo.max_final_value)} colorClass="text-gain" className="!p-3" />
                          <MetricCard label="95th Percentile" value={formatCurrency(currentResult.monte_carlo.percentile_95)} colorClass="text-gain" className="!p-3" />
                        </div>
                        <div className="grid grid-cols-3 gap-3 mt-3">
                          <MetricCard label="Mean Final Value" value={formatCurrency(currentResult.monte_carlo.mean_final_value)} className="!p-3" />
                          <MetricCard label="Std Dev" value={formatCurrency(currentResult.monte_carlo.std_final_value)} className="!p-3" />
                          <MetricCard label="Probability of Profit" value={formatPercent(currentResult.monte_carlo.prob_profit * 100)} className="!p-3" />
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Research checks + AlphaLive export */}
              <div className="space-y-4 min-w-0">
                <ResearchChecksPanel
                  hasResult={!!currentResult}
                  qualityScore={qualityScoreForRun}
                  riskSettings={submittedConfig?.riskSettings ?? riskSettings}
                />
                <ExportPanel
                  currentResult={currentResult}
                  ticker={submittedConfig?.ticker ?? ticker}
                  strategy={submittedConfig?.strategy ?? strategy}
                  initialCapital={submittedConfig?.initialCapital ?? initialCapital}
                  blockReason={exportBlockReason}
                />
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="batch" className="h-[calc(100%-3rem)] overflow-y-auto">
          <BatchBacktest />
        </TabsContent>

        <TabsContent value="optimize" className="h-[calc(100%-3rem)] overflow-y-auto">
          <ParameterOptimize
            ticker={ticker}
            strategy={strategy}
            startDate={startDate}
            endDate={endDate}
            initialCapital={initialCapital}
            onApplyParams={(newParams) => {
              setParams((prev) => ({
                ...prev,
                [strategy]: { ...prev[strategy], ...newParams },
              }));
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// --- Layout primitives -------------------------------------------------

function ConfigField({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("rounded-lg border border-border/70 bg-card/60 p-2.5", className)}>
      <span className="label-caps block mb-1.5">{label}</span>
      {children}
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono-numbers text-xs font-medium">{value}</span>
    </div>
  );
}

// One row per real order (not one row per round trip): a BUY row opens a
// position (no realized P&L/holding period yet, same as the backend's own
// order log), a SELL row closes the FIFO-matched entry and carries the
// realized P&L, fees, and holding period for that round trip - mirrors
// pairTradesFIFO's matching logic but keeps both legs visible as separate
// ledger rows instead of collapsing them into one, since that's what a
// trade ledger (as opposed to the Trades tab's round-trip table) shows.
interface LedgerRow {
  date: string;
  side: "BUY" | "SELL";
  price: number;
  shares: number;
  fees: number;
  pnl: number | null;
  holdingDays: number | null;
}

function buildLedgerRows(orders: RawOrder[]): LedgerRow[] {
  const filled = orders.filter((o) => o.status === "filled");
  const buyQueue: RawOrder[] = [];
  const rows: LedgerRow[] = [];

  for (const order of filled) {
    if (order.side === "buy") {
      buyQueue.push(order);
      rows.push({
        date: order.filled_timestamp ?? order.timestamp ?? "",
        side: "BUY",
        price: order.filled_price ?? 0,
        shares: order.shares,
        fees: order.commission,
        pnl: null,
        holdingDays: null,
      });
    } else if (order.side === "sell" && buyQueue.length > 0) {
      const buy = buyQueue.shift()!;
      const buyPrice = buy.filled_price ?? 0;
      const sellPrice = order.filled_price ?? 0;
      const shares = Math.min(buy.shares, order.shares);
      const pnl = (sellPrice - buyPrice) * shares - (buy.commission + order.commission);
      const entryDate = buy.filled_timestamp ?? buy.timestamp ?? "";
      const exitDate = order.filled_timestamp ?? order.timestamp ?? "";
      const entryMs = new Date(entryDate).getTime();
      const exitMs = new Date(exitDate).getTime();
      const holdingDays = !isNaN(entryMs) && !isNaN(exitMs) ? Math.round((exitMs - entryMs) / 86400000) : null;
      rows.push({
        date: exitDate,
        side: "SELL",
        price: sellPrice,
        shares: order.shares,
        fees: order.commission,
        pnl,
        holdingDays,
      });
    }
  }
  return rows;
}

function TradeLedgerPreview({ rows }: { rows: LedgerRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-secondary/20">
            <th className="px-2.5 py-2 text-left label-caps">Date</th>
            <th className="px-2.5 py-2 text-left label-caps">Side</th>
            <th className="px-2.5 py-2 text-right label-caps">Price</th>
            <th className="px-2.5 py-2 text-right label-caps">Shares</th>
            <th className="px-2.5 py-2 text-right label-caps">Fees</th>
            <th className="px-2.5 py-2 text-right label-caps">P&L</th>
            <th className="px-2.5 py-2 text-right label-caps">Holding Period</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0">
              <td className="px-2.5 py-1.5 font-mono-numbers">{formatDate(r.date)}</td>
              <td className="px-2.5 py-1.5">
                <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded", r.side === "BUY" ? "bg-gain/20 text-gain" : "bg-loss/20 text-loss")}>
                  {r.side}
                </span>
              </td>
              <td className="px-2.5 py-1.5 text-right font-mono-numbers">{formatCurrency(r.price)}</td>
              <td className="px-2.5 py-1.5 text-right font-mono-numbers">{r.shares}</td>
              <td className="px-2.5 py-1.5 text-right font-mono-numbers text-muted-foreground">{formatCurrency(r.fees)}</td>
              <td className={cn("px-2.5 py-1.5 text-right font-mono-numbers font-semibold", r.pnl == null ? "text-muted-foreground" : pnlColor(r.pnl))}>
                {r.pnl == null ? "-" : formatCurrency(r.pnl)}
              </td>
              <td className="px-2.5 py-1.5 text-right font-mono-numbers text-muted-foreground">
                {r.holdingDays == null ? "-" : `${r.holdingDays} day${r.holdingDays === 1 ? "" : "s"}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StrategyParamsPanel({
  strategy,
  params,
  onChange,
}: {
  strategy: StrategyType;
  params: StrategyParams;
  onChange: (k: string, v: number | boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-xl border border-border/70 bg-card/60 px-3.5">
      <CollapsibleTrigger className="flex items-center justify-between w-full py-3 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-semibold shrink-0">Strategy Parameters</span>
          <span className="text-[10px] text-muted-foreground/85 font-mono-numbers truncate hidden sm:inline">
            {strategyParamsSummary(strategy, params)}
          </span>
        </div>
        <ChevronDown className={cn("h-3.5 w-3.5 text-muted-foreground transition-transform shrink-0", open && "rotate-180")} />
      </CollapsibleTrigger>
      <CollapsibleContent className="pb-3.5">
        {strategy === "ma_crossover" && <MACrossoverForm params={params as MACrossoverParams} onChange={onChange} />}
        {strategy === "rsi_mean_reversion" && <RSIMeanReversionForm params={params as RSIMeanReversionParams} onChange={onChange} />}
        {strategy === "rsi_simple" && <RSISimpleForm params={params as RSISimpleParams} onChange={onChange} />}
        {strategy === "momentum_breakout" && <MomentumBreakoutForm params={params as MomentumBreakoutParams} onChange={onChange} />}
        {strategy === "bollinger_breakout" && <BollingerBreakoutForm params={params as BollingerBreakoutParams} onChange={onChange} />}
        {strategy === "vwap_reversion" && <VWAPReversionForm params={params as VWAPReversionParams} onChange={onChange} />}
        {strategy === "bollinger_rsi_combo" && <BollingerRSIComboForm params={params as BollingerRSIComboParams} onChange={onChange} />}
        {strategy === "trend_adaptive_rsi" && <TrendAdaptiveRSIForm params={params as TrendAdaptiveRSIParams} onChange={onChange} />}
        {strategy === "greenblatt_weekly" && <GreenblattWeeklyForm params={params as GreenblattWeeklyParams} onChange={onChange} />}
      </CollapsibleContent>
    </Collapsible>
  );
}

// --- Research checks -----------------------------------------------------

type CheckTone = "gain" | "warning" | "loss" | "neutral";

function CheckRow({ tone, title, subtitle }: { tone: CheckTone; title: string; subtitle: string }) {
  const Icon = tone === "gain" ? CheckCircle2 : tone === "loss" ? AlertTriangle : tone === "warning" ? AlertTriangle : Circle;
  const iconClass = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : tone === "warning" ? "text-warning" : "text-muted-foreground";
  const badgeText = tone === "gain" ? "OK" : tone === "loss" ? "Low" : tone === "warning" ? "Fair" : "Pending";
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

function ResearchChecksPanel({
  hasResult,
  qualityScore,
  riskSettings,
}: {
  hasResult: boolean;
  qualityScore: number | null;
  riskSettings: RiskSettings;
}) {
  const dataQualityTone: CheckTone = !hasResult ? "neutral" : qualityScore === null ? "neutral" : qualityScore >= 0.9 ? "gain" : qualityScore >= 0.7 ? "warning" : "loss";
  const dataQualitySubtitle = !hasResult
    ? "Run a backtest to evaluate this window's data."
    : qualityScore === null
    ? "Not verified this session - click Fetch Data to compute a quality score."
    : `${(qualityScore * 100).toFixed(0)}% quality score for the fetched window.`;

  const verifiedCount = [
    hasResult, // next-bar execution, architecturally always true once a run exists
    hasResult, // transaction costs, always applied once a run exists
    hasResult && dataQualityTone === "gain",
    hasResult, // position limits, always threaded through once a run exists
  ].filter(Boolean).length;

  return (
    <div className="card-elevated p-4">
      <div className="flex items-center justify-between mb-1">
        <h3 className="section-label">Research Checks</h3>
        <span className={cn("text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border", hasResult ? "bg-gain/10 text-gain border-gain/30" : "bg-secondary text-muted-foreground border-border")}>
          {hasResult ? `${verifiedCount}/5 verified` : "Not run"}
        </span>
      </div>
      <div>
        <CheckRow
          tone={hasResult ? "gain" : "neutral"}
          title="Next-bar execution"
          subtitle="Signals generated at bar N execute at bar N+1's open - enforced architecturally, no look-ahead bias."
        />
        <CheckRow
          tone={hasResult ? "gain" : "neutral"}
          title="Transaction costs"
          subtitle={`$${riskSettings.commission_per_trade.toFixed(2)}/trade commission (2x round trip) - default slippage applied by the backend.`}
        />
        <CheckRow tone={dataQualityTone} title="Data quality" subtitle={dataQualitySubtitle} />
        <CheckRow
          tone={hasResult ? "gain" : "neutral"}
          title="Position limits"
          subtitle={`Max ${riskSettings.max_position_size_pct}% per position - max ${riskSettings.max_open_positions} concurrent positions.`}
        />
        <CheckRow
          tone="neutral"
          title="Walk-forward validation"
          subtitle="Not part of a single backtest - run via AlphaLab's offline walk-forward research scripts."
        />
      </div>
    </div>
  );
}

function ExportPanel({
  currentResult,
  ticker,
  strategy,
  initialCapital,
  blockReason,
}: {
  currentResult: BacktestResult | null;
  ticker: string;
  strategy: StrategyType;
  initialCapital: number;
  blockReason?: string;
}) {
  if (!currentResult) {
    return (
      <div className="card-elevated p-4">
        <h3 className="section-label mb-3">AlphaLive Export</h3>
        <div className="flex items-center gap-2.5 text-muted-foreground">
          <ShieldQuestion className="h-5 w-5 shrink-0" />
          <p className="text-xs">Run a backtest to check export eligibility.</p>
        </div>
      </div>
    );
  }

  if (blockReason) {
    return (
      <div className="card-elevated p-4">
        <h3 className="section-label mb-3">AlphaLive Export</h3>
        <div className="flex items-start gap-2.5">
          <div className="rounded-full bg-loss/10 p-2 shrink-0">
            <Lock className="h-4 w-4 text-loss" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Research-only strategy</p>
            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{blockReason}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card-elevated p-4">
      <h3 className="section-label mb-3">AlphaLive Export</h3>
      <div className="flex items-start gap-2.5">
        <div className="rounded-full bg-gain/10 p-2 shrink-0">
          <Rocket className="h-4 w-4 text-gain" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">Ready for paper execution</p>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            This configuration passes AlphaLab's export rules and can be sent to AlphaLive for paper trading / testing.
            Backtested performance does not imply proven live profitability.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-3.5 text-xs">
        <div>
          <span className="label-caps block">Strategy</span>
          <span className="font-medium">{strategyDisplayName(strategy)}</span>
        </div>
        <div>
          <span className="label-caps block">Ticker</span>
          <span className="font-mono-numbers font-medium">{ticker.toUpperCase()}</span>
        </div>
        <div>
          <span className="label-caps block">Capital</span>
          <span className="font-mono-numbers font-medium">{formatCurrency(initialCapital)}</span>
        </div>
      </div>
      <div className="mt-3.5">
        <ExportButton
          backtestId={currentResult.backtest_id || ""}
          strategyName={strategy}
          ticker={ticker}
          variant="default"
          size="sm"
          showLabel={true}
        />
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

function ParamCheckbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox checked={checked} onCheckedChange={(v) => onChange(!!v)} id={`chk-${label}`} />
      <Label htmlFor={`chk-${label}`} className="text-xs">{label}</Label>
    </div>
  );
}

function MACrossoverForm({ params, onChange }: { params: MACrossoverParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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

function RSISimpleForm({ params, onChange }: { params: RSISimpleParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <ParamSlider label="RSI Period" value={params.period} onChange={(v) => onChange("period", v)} min={5} max={30} />
      <ParamSlider label="Oversold" value={params.oversold} onChange={(v) => onChange("oversold", v)} min={10} max={40} />
      <ParamSlider label="Overbought" value={params.overbought} onChange={(v) => onChange("overbought", v)} min={60} max={90} />
    </div>
  );
}

function MomentumBreakoutForm({ params, onChange }: { params: MomentumBreakoutParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <ParamSlider label="Lookback" value={params.lookback} onChange={(v) => onChange("lookback", v)} min={10} max={60} />
      <ParamSlider label="Volume Surge %" value={params.volume_surge_pct} onChange={(v) => onChange("volume_surge_pct", v)} min={100} max={300} />
      <ParamSlider label="RSI Min" value={params.rsi_min} onChange={(v) => onChange("rsi_min", v)} min={40} max={60} />
      <ParamSlider label="Stop Loss ATR Mult" value={params.stop_loss_atr_mult} onChange={(v) => onChange("stop_loss_atr_mult", v)} min={1} max={5} step={0.1} />
    </div>
  );
}

function BollingerBreakoutForm({ params, onChange }: { params: BollingerBreakoutParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <ParamSlider label="BB Period" value={params.bb_period} onChange={(v) => onChange("bb_period", v)} min={5} max={100} />
      <ParamSlider label="Std Dev" value={params.bb_std_dev} onChange={(v) => onChange("bb_std_dev", v)} min={0.5} max={4} step={0.1} />
      <ParamSlider label="Confirmation Bars" value={params.confirmation_bars} onChange={(v) => onChange("confirmation_bars", v)} min={1} max={5} />
      <ParamCheckbox label="Volume Filter" checked={params.volume_filter} onChange={(v) => onChange("volume_filter", v)} />
      {params.volume_filter && (
        <ParamSlider label="Volume Threshold" value={params.volume_threshold} onChange={(v) => onChange("volume_threshold", v)} min={1} max={3} step={0.1} />
      )}
      <ParamSlider label="Cooldown Days" value={params.cooldown_days} onChange={(v) => onChange("cooldown_days", v)} min={0} max={10} />
    </div>
  );
}

function VWAPReversionForm({ params, onChange }: { params: VWAPReversionParams; onChange: (k: string, v: number) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <ParamSlider label="VWAP Period" value={params.vwap_period} onChange={(v) => onChange("vwap_period", v)} min={5} max={50} />
      <ParamSlider label="Deviation Threshold" value={params.deviation_threshold} onChange={(v) => onChange("deviation_threshold", v)} min={0.5} max={5} step={0.1} />
      <ParamSlider label="RSI Period" value={params.rsi_period} onChange={(v) => onChange("rsi_period", v)} min={5} max={30} />
      <ParamSlider label="Oversold" value={params.oversold} onChange={(v) => onChange("oversold", v)} min={10} max={40} />
      <ParamSlider label="Overbought" value={params.overbought} onChange={(v) => onChange("overbought", v)} min={60} max={90} />
      <ParamSlider label="Cooldown Days" value={params.cooldown_days} onChange={(v) => onChange("cooldown_days", v)} min={0} max={10} />
    </div>
  );
}

function BollingerRSIComboForm({ params, onChange }: { params: BollingerRSIComboParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <ParamSlider label="BB Period" value={params.bb_period} onChange={(v) => onChange("bb_period", v)} min={5} max={50} />
      <ParamSlider label="BB Std Dev" value={params.bb_std} onChange={(v) => onChange("bb_std", v)} min={1} max={4} step={0.1} />
      <ParamSlider label="RSI Period" value={params.rsi_period} onChange={(v) => onChange("rsi_period", v)} min={5} max={30} />
      <ParamSlider label="RSI Oversold" value={params.rsi_oversold} onChange={(v) => onChange("rsi_oversold", v)} min={20} max={49} />
      <ParamSlider label="RSI Overbought" value={params.rsi_overbought} onChange={(v) => onChange("rsi_overbought", v)} min={51} max={80} />
      <ParamCheckbox label="Exit at BB Middle" checked={params.exit_at_middle} onChange={(v) => onChange("exit_at_middle", v)} />
    </div>
  );
}

function TrendAdaptiveRSIForm({ params, onChange }: { params: TrendAdaptiveRSIParams; onChange: (k: string, v: number) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <ParamSlider label="RSI Period" value={params.rsi_period} onChange={(v) => onChange("rsi_period", v)} min={5} max={30} />
      <ParamSlider label="Trend SMA" value={params.trend_sma} onChange={(v) => onChange("trend_sma", v)} min={20} max={200} />
      <ParamSlider label="Trend Lookback" value={params.trend_lookback} onChange={(v) => onChange("trend_lookback", v)} min={1} max={20} />
      <ParamSlider label="Uptrend Buy" value={params.uptrend_buy} onChange={(v) => onChange("uptrend_buy", v)} min={20} max={49} />
      <ParamSlider label="Uptrend Sell" value={params.uptrend_sell} onChange={(v) => onChange("uptrend_sell", v)} min={51} max={80} />
      <ParamSlider label="Downtrend Buy" value={params.downtrend_buy} onChange={(v) => onChange("downtrend_buy", v)} min={10} max={49} />
      <ParamSlider label="Downtrend Sell" value={params.downtrend_sell} onChange={(v) => onChange("downtrend_sell", v)} min={51} max={70} />
      <ParamSlider label="Range Buy" value={params.range_buy} onChange={(v) => onChange("range_buy", v)} min={20} max={49} />
      <ParamSlider label="Range Sell" value={params.range_sell} onChange={(v) => onChange("range_sell", v)} min={51} max={80} />
    </div>
  );
}

function GreenblattWeeklyForm({ params, onChange }: { params: GreenblattWeeklyParams; onChange: (k: string, v: number | boolean) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {/* fast_sma/slow_sma should only be 10/20/50/100/200 - FeatureEngineer's precomputed
          SMA windows (see AlphaLab/docs/STRATEGY_SCHEMA.md). Slider doesn't enforce the
          discrete set, same as other params here that rely on backend validation. */}
      <ParamSlider label="Fast SMA (weeks)" value={params.fast_sma} onChange={(v) => onChange("fast_sma", v)} min={10} max={100} step={10} />
      <ParamSlider label="Slow SMA (weeks)" value={params.slow_sma} onChange={(v) => onChange("slow_sma", v)} min={20} max={200} step={10} />
      <ParamSlider label="RSI Period" value={params.rsi_period} onChange={(v) => onChange("rsi_period", v)} min={5} max={30} />
      <ParamSlider label="RSI Oversold" value={params.rsi_oversold} onChange={(v) => onChange("rsi_oversold", v)} min={20} max={49} />
      <ParamSlider label="RSI Overbought" value={params.rsi_overbought} onChange={(v) => onChange("rsi_overbought", v)} min={51} max={80} />
      <ParamSlider label="Min Hold (weeks)" value={params.min_hold_bars} onChange={(v) => onChange("min_hold_bars", v)} min={4} max={104} />
      <ParamSlider label="Trailing Stop %" value={params.trailing_stop_pct} onChange={(v) => onChange("trailing_stop_pct", v)} min={0.05} max={0.5} step={0.05} />
      <ParamCheckbox label="Exit on RSI Overbought" checked={params.exit_rsi_overbought} onChange={(v) => onChange("exit_rsi_overbought", v)} />
      <ParamCheckbox label="Exit on SMA Death-Cross" checked={params.exit_sma_cross} onChange={(v) => onChange("exit_sma_cross", v)} />
    </div>
  );
}
