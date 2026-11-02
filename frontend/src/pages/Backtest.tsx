import { useState } from "react";
import { toast } from "sonner";
import type { BacktestResult, RiskSettings, StrategyParams, StrategyType } from "@/types";
import { DEFAULT_RISK_SETTINGS } from "@/types";
import { Page } from "@/components/layout/Page";
import { BatchBacktest } from "@/components/backtest/BatchBacktest";
import { ExportPanel } from "@/components/backtest/ExportPanel";
import { MonteCarloSummary } from "@/components/backtest/MonteCarloSummary";
import ParameterOptimize from "@/components/backtest/ParameterOptimize";
import { ResearchChecks } from "@/components/backtest/ResearchChecks";
import { RiskSettingsPanel } from "@/components/backtest/RiskSettingsPanel";
import { RunSummary } from "@/components/backtest/RunSummary";
import { StrategyParamsPanel } from "@/components/backtest/StrategyParamsPanel";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { MonthlyReturnsHeatmap } from "@/components/charts/MonthlyReturnsHeatmap";
import { TradeTable } from "@/components/charts/TradeTable";
import { CapitalField, DateRangeFields, IntervalSelect, StrategyField, TickerField } from "@/components/forms/RunFields";
import { MetricsBreakdown } from "@/components/metrics/MetricsBreakdown";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { errorMessage, fetchData, runBacktest } from "@/services/api";
import { historyItem, useBacktestStore } from "@/stores/backtestStore";
import { DEFAULT_CAPITAL, DEFAULT_END, DEFAULT_START, DEFAULT_TICKER } from "@/utils/defaults";
import { qualityColor } from "@/utils/formatters";
import { DEFAULT_PARAMS } from "@/utils/strategies";
import { pairTradesFIFO } from "@/utils/tradePairing";

type Sizing = "equal_weight" | "volatility_weighted";

interface RunConfig {
  ticker: string;
  strategy: StrategyType;
  startDate: string;
  endDate: string;
  interval: string;
  initialCapital: number;
  sizing: Sizing;
  monteCarloRuns: number;
  drawdownHalt: boolean;
  risk: RiskSettings;
  /** Parameters are kept per strategy so switching back restores your edits. */
  params: Record<StrategyType, StrategyParams>;
}

const INITIAL_CONFIG: RunConfig = {
  ticker: DEFAULT_TICKER,
  strategy: "ma_crossover",
  startDate: DEFAULT_START,
  endDate: DEFAULT_END,
  interval: "1d",
  initialCapital: DEFAULT_CAPITAL,
  sizing: "equal_weight",
  monteCarloRuns: 0,
  drawdownHalt: true,
  risk: DEFAULT_RISK_SETTINGS,
  params: DEFAULT_PARAMS,
};

/** A quality score is only evidence for the exact ticker and window it was fetched for. */
interface QualityScore {
  score: number;
  ticker: string;
  startDate: string;
  endDate: string;
}

export default function Backtest() {
  const { currentRun, setCurrentRun, addToHistory, history } = useBacktestStore();
  const [config, setConfig] = useState(INITIAL_CONFIG);
  const [submitted, setSubmitted] = useState<RunConfig | null>(null);
  const [quality, setQuality] = useState<QualityScore | null>(null);
  const [fetching, setFetching] = useState(false);
  const [running, setRunning] = useState(false);

  const set = <K extends keyof RunConfig>(key: K, value: RunConfig[K]) => setConfig((c) => ({ ...c, [key]: value }));
  const setParam = (key: string, value: number | boolean) =>
    setConfig((c) => ({ ...c, params: { ...c.params, [c.strategy]: { ...c.params[c.strategy], [key]: value } } }));

  const handleFetch = async () => {
    setFetching(true);
    try {
      const { ticker, startDate, endDate, interval } = config;
      const response = await fetchData([ticker], startDate, endDate, interval);
      const fetched = response.data?.[ticker];
      if (fetched) {
        setQuality({ score: fetched.quality_score, ticker, startDate, endDate });
        toast.success(`Fetched ${fetched.records} bars for ${ticker}`);
      }
      if (response.errors?.length) toast.error(response.errors.join(", "));
    } catch (error) {
      toast.error(errorMessage(error, "Fetching data failed"));
    } finally {
      setFetching(false);
    }
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      const result = await runBacktest({
        ticker: config.ticker,
        strategy: config.strategy,
        start_date: config.startDate,
        end_date: config.endDate,
        initial_capital: config.initialCapital,
        params: config.params[config.strategy],
        position_sizing: config.sizing,
        monte_carlo_runs: config.monteCarloRuns,
        risk_settings: config.risk,
        drawdown_halt_enabled: config.drawdownHalt,
      });
      setCurrentRun(historyItem(result, config.ticker, config.strategy));
      setSubmitted(config);
    } catch (error) {
      toast.error(errorMessage(error, "Backtest failed"));
    } finally {
      setRunning(false);
    }
  };

  const saved = currentRun !== null && history.some((h) => h.id === currentRun.id);
  const qualityForRun =
    quality && submitted && quality.ticker === submitted.ticker && quality.startDate === submitted.startDate && quality.endDate === submitted.endDate
      ? quality.score
      : null;
  const freshQuality = quality && quality.ticker === config.ticker ? quality.score : null;

  return (
    <Page title="Backtest">
      <Tabs defaultValue="single">
        <TabsList>
          <TabsTrigger value="single">Single run</TabsTrigger>
          <TabsTrigger value="batch">Batch</TabsTrigger>
          <TabsTrigger value="optimize">Optimize</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="space-y-8">
          <div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-4 md:grid-cols-4 xl:grid-cols-8">
              <div className="col-span-2">
                <StrategyField value={config.strategy} onChange={(v) => set("strategy", v)} />
              </div>
              <TickerField value={config.ticker} onChange={(v) => set("ticker", v)} />
              <DateRangeFields
                start={config.startDate}
                end={config.endDate}
                onStartChange={(v) => set("startDate", v)}
                onEndChange={(v) => set("endDate", v)}
              />
              <CapitalField value={config.initialCapital} onChange={(v) => set("initialCapital", v)} />
              <Field label="Sizing" htmlFor="sizing">
                <Select value={config.sizing} onValueChange={(v) => set("sizing", v as Sizing)}>
                  <SelectTrigger id="sizing">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="equal_weight">Equal weight</SelectItem>
                    <SelectItem value="volatility_weighted">Volatility weighted</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Monte Carlo runs" htmlFor="mc-runs" hint="0 turns it off">
                <Input
                  id="mc-runs"
                  type="number"
                  min={0}
                  max={1000}
                  className="num"
                  value={config.monteCarloRuns}
                  onChange={(e) => set("monteCarloRuns", e.target.valueAsNumber || 0)}
                />
              </Field>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3">
              <Button onClick={handleRun} disabled={running || !config.ticker}>
                {running ? "Running…" : "Run backtest"}
              </Button>
              <div className="flex items-center gap-2">
                <Checkbox id="drawdown-halt" checked={config.drawdownHalt} onCheckedChange={(v) => set("drawdownHalt", v === true)} />
                <Label htmlFor="drawdown-halt" className="text-[13px] font-normal">
                  Halt new entries after a 10% drawdown
                </Label>
                <span className="text-2xs text-muted-foreground">(not exportable)</span>
              </div>
              <div className="flex items-center gap-2 text-[13px]">
                <IntervalSelect value={config.interval} onChange={(v) => set("interval", v)} className="h-8 w-28" />
                <Button variant="link" onClick={handleFetch} disabled={fetching || !config.ticker}>
                  {fetching ? "Fetching…" : "Fetch and score data"}
                </Button>
                {freshQuality !== null && (
                  <span className={cn("num text-2xs", qualityColor(freshQuality))}>{(freshQuality * 100).toFixed(0)}% quality</span>
                )}
              </div>
            </div>
          </div>

          <div>
            <StrategyParamsPanel strategy={config.strategy} params={config.params[config.strategy]} onChange={setParam} />
            <RiskSettingsPanel settings={config.risk} onChange={(risk) => set("risk", risk)} />
          </div>

          <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="min-w-0 space-y-8">
              {currentRun ? (
                <>
                  <RunSummary
                    run={currentRun}
                    actions={
                      <Button variant="outline" size="sm" disabled={saved} onClick={() => addToHistory([currentRun])}>
                        {saved ? "Saved to history" : "Save to history"}
                      </Button>
                    }
                  />
                  <RunDetails run={currentRun.result} />
                  {currentRun.result.monte_carlo && <MonteCarloSummary mc={currentRun.result.monte_carlo} />}
                </>
              ) : (
                <EmptyState
                  title="No results yet"
                  description="Set up a run above and press Run backtest. Fetching data first scores its quality for the research checks."
                />
              )}
            </div>

            <aside className="space-y-8">
              <ResearchChecks hasResult={!!currentRun} qualityScore={qualityForRun} riskSettings={(submitted ?? config).risk} />
              <ExportPanel result={currentRun?.result ?? null} ticker={currentRun?.ticker ?? ""} strategy={currentRun?.strategy ?? ""} />
            </aside>
          </div>
        </TabsContent>

        <TabsContent value="batch">
          <BatchBacktest />
        </TabsContent>

        <TabsContent value="optimize">
          <ParameterOptimize
            ticker={config.ticker}
            strategy={config.strategy}
            startDate={config.startDate}
            endDate={config.endDate}
            initialCapital={config.initialCapital}
            onApplyParams={(best) =>
              setConfig((c) => ({ ...c, params: { ...c.params, [c.strategy]: { ...c.params[c.strategy], ...best } } }))
            }
          />
        </TabsContent>
      </Tabs>
    </Page>
  );
}

function RunDetails({ run }: { run: BacktestResult }) {
  return (
    <Tabs defaultValue="drawdown">
      <TabsList>
        <TabsTrigger value="drawdown">Drawdown</TabsTrigger>
        <TabsTrigger value="monthly">Monthly returns</TabsTrigger>
        <TabsTrigger value="trades">Trades</TabsTrigger>
        <TabsTrigger value="metrics">All metrics</TabsTrigger>
      </TabsList>
      <TabsContent value="drawdown">
        <DrawdownChart equityCurve={run.equity_curve} />
      </TabsContent>
      <TabsContent value="monthly">
        <MonthlyReturnsHeatmap equityCurve={run.equity_curve} />
      </TabsContent>
      <TabsContent value="trades">
        <TradeTable trades={pairTradesFIFO(run.trades)} />
      </TabsContent>
      <TabsContent value="metrics">
        <MetricsBreakdown metrics={run.metrics} />
      </TabsContent>
    </Tabs>
  );
}
