import { useState } from "react";
import { toast } from "sonner";
import type { BacktestResult, PositionSizing, RiskSettings, StrategyType } from "@/types";
import { DEFAULT_RISK_SETTINGS } from "@/types";
import { ApiOfflineNotice } from "@/components/layout/ApiOfflineNotice";
import { Page } from "@/components/layout/Page";
import { BENCHMARK_COLOR, SERIES_COLORS } from "@/components/charts/chartTheme";
import { RiskSettingsPanel } from "@/components/backtest/RiskSettingsPanel";
import { OverlayEquityChart, type OverlayView } from "@/components/comparison/OverlayEquityChart";
import { CapitalField, DateRangeFields, DrawdownHaltField, SizingField, TickerField } from "@/components/forms/RunFields";
import { Button } from "@/components/ui/button";
import { Table, Td, Th } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Section } from "@/components/ui/section";
import { Segmented } from "@/components/ui/segmented";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Swatch } from "@/components/ui/swatch";
import { Tag } from "@/components/ui/tag";
import { compareStrategies, errorMessage, fetchData } from "@/services/api";
import { historyItem, useBacktestStore } from "@/stores/backtestStore";
import { DEFAULT_CAPITAL, DEFAULT_DRAWDOWN_HALT, DEFAULT_END, DEFAULT_SIZING, DEFAULT_START, DEFAULT_TICKER } from "@/utils/defaults";
import { formatNumber, formatPercent, pnlColor } from "@/utils/formatters";
import { runSettingsSummary } from "@/utils/runSettings";
import { STRATEGIES, STRATEGY_TYPES, strategyName, strategySpec } from "@/utils/strategies";

const MIN_STRATEGIES = 2;
const MAX_STRATEGIES = SERIES_COLORS.length;

/** Ways to pick a leader. Every getter is "higher is better" (drawdowns are negative). */
const RANKINGS = [
  { value: "sharpe", label: "Sharpe ratio", get: (r: BacktestResult) => r.metrics.risk.sharpe_ratio, format: formatNumber },
  { value: "return", label: "Total return", get: (r: BacktestResult) => r.total_return_pct, format: formatPercent },
  { value: "drawdown", label: "Smallest drawdown", get: (r: BacktestResult) => r.metrics.drawdown.max_drawdown_pct, format: formatPercent },
  { value: "winRate", label: "Win rate", get: (r: BacktestResult) => r.metrics.trades.win_rate * 100, format: (v: number) => formatPercent(v, 2, false) },
  { value: "profitFactor", label: "Profit factor", get: (r: BacktestResult) => r.metrics.trades.profit_factor, format: formatNumber },
] as const;

type Ranking = (typeof RANKINGS)[number];

const VIEWS: { value: OverlayView; label: string }[] = [
  { value: "equity", label: "Equity" },
  { value: "drawdown", label: "Drawdown" },
  { value: "rollingSharpe", label: "Rolling Sharpe" },
];

/** What every strategy in a comparison was simulated with; the same fields as a Backtest run. */
interface RunSettings {
  risk: RiskSettings;
  sizing: PositionSizing;
  drawdownHalt: boolean;
}

const DEFAULT_RUN_SETTINGS: RunSettings = { risk: DEFAULT_RISK_SETTINGS, sizing: DEFAULT_SIZING, drawdownHalt: DEFAULT_DRAWDOWN_HALT };

function leader(entries: [string, BacktestResult][], ranking: Ranking): [string, BacktestResult] {
  return entries.reduce((best, entry) => (ranking.get(entry[1]) > ranking.get(best[1]) ? entry : best));
}

export default function Compare() {
  const addToHistory = useBacktestStore((s) => s.addToHistory);
  const [ticker, setTicker] = useState(DEFAULT_TICKER);
  const [startDate, setStartDate] = useState(DEFAULT_START);
  const [endDate, setEndDate] = useState(DEFAULT_END);
  const [capital, setCapital] = useState(DEFAULT_CAPITAL);
  const [selected, setSelected] = useState<StrategyType[]>(["ma_crossover", "rsi_mean_reversion"]);
  const [settings, setSettings] = useState(DEFAULT_RUN_SETTINGS);
  const [view, setView] = useState<OverlayView>("equity");
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<{
    ticker: string;
    settings: RunSettings;
    byStrategy: Record<string, BacktestResult>;
  } | null>(null);

  const setSetting = <K extends keyof RunSettings>(key: K, value: RunSettings[K]) => setSettings((s) => ({ ...s, [key]: value }));

  const handleRun = async () => {
    setRunning(true);
    try {
      await fetchData([ticker], startDate, endDate, "1d");
      const response = await compareStrategies({
        ticker,
        strategies: selected,
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        position_sizing: settings.sizing,
        risk_settings: settings.risk,
        drawdown_halt_enabled: settings.drawdownHalt,
      });
      setResults({ ticker, settings, byStrategy: response.data });
    } catch (error) {
      toast.error(errorMessage(error, "Comparison failed"));
    } finally {
      setRunning(false);
    }
  };

  const handleSave = () => {
    if (!results) return;
    addToHistory(Object.entries(results.byStrategy).map(([strategy, r]) => historyItem(r, results.ticker, strategy)));
    toast.success("Saved every strategy in this comparison to the Overview");
  };

  const unselected = STRATEGY_TYPES.filter((s) => !selected.includes(s));
  const entries = results ? Object.entries(results.byStrategy) : [];

  return (
    <Page
      title="Compare"
      actions={
        <Button variant="outline" onClick={handleSave} disabled={!results}>
          Save to history
        </Button>
      }
    >
      <ApiOfflineNotice />

      <div className="space-y-5">
        <div className="grid max-w-5xl grid-cols-2 gap-4 md:grid-cols-5">
          <TickerField value={ticker} onChange={setTicker} />
          <DateRangeFields start={startDate} end={endDate} onStartChange={setStartDate} onEndChange={setEndDate} />
          <CapitalField value={capital} onChange={setCapital} />
          <SizingField value={settings.sizing} onChange={(v) => setSetting("sizing", v)} />
        </div>

        <Field label={`Strategies (${MIN_STRATEGIES} to ${MAX_STRATEGIES}), benchmarked against buy & hold of the same ticker`}>
          <div className="flex flex-wrap items-center gap-2">
            {selected.map((s, i) => (
              <Tag
                key={s}
                onRemove={selected.length > MIN_STRATEGIES ? () => setSelected(selected.filter((x) => x !== s)) : undefined}
                removeLabel={`Remove ${STRATEGIES[s].name}`}
              >
                <Swatch color={SERIES_COLORS[i]} />
                {STRATEGIES[s].name}
              </Tag>
            ))}
            {selected.length < MAX_STRATEGIES && (
              <Select value="" onValueChange={(v) => setSelected([...selected, v as StrategyType])}>
                <SelectTrigger aria-label="Add a strategy" className="h-7 w-40 text-[13px]">
                  <SelectValue placeholder="Add strategy" />
                </SelectTrigger>
                <SelectContent>
                  {unselected.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STRATEGIES[s].name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </Field>

        <div>
          <RiskSettingsPanel settings={settings.risk} onChange={(risk) => setSetting("risk", risk)} />
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <Button onClick={handleRun} disabled={running || !ticker}>
            {running ? "Running…" : "Run comparison"}
          </Button>
          <DrawdownHaltField checked={settings.drawdownHalt} onChange={(v) => setSetting("drawdownHalt", v)} />
        </div>
      </div>

      {results ? (
        <>
          <p className="num text-2xs text-muted-foreground">
            Simulated with: {runSettingsSummary(results.settings.risk, results.settings.sizing, results.settings.drawdownHalt)}
          </p>
          <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_340px]">
            <Section title={`${results.ticker}, ${entries.length} strategies`} aside={<Segmented label="Chart" options={VIEWS} value={view} onChange={setView} />}>
              <OverlayEquityChart results={results.byStrategy} view={view} />
              <p className="mt-2 flex flex-wrap gap-4 text-2xs text-muted-foreground">
                {entries.map(([name], i) => (
                  <span key={name}>
                    <Swatch color={SERIES_COLORS[i]} />
                    {strategyName(name)}
                  </span>
                ))}
                <span>
                  <Swatch color={BENCHMARK_COLOR} />
                  Buy & hold
                </span>
              </p>
            </Section>
            <Leaders entries={entries} benchmarkReturn={entries[0][1].benchmark?.total_return_pct ?? null} />
          </div>
          <ResultsTable entries={entries} />
        </>
      ) : (
        <EmptyState title="No comparison yet" description="Pick two or three strategies and run them on the same data, costs and window." />
      )}
    </Page>
  );
}

function Leaders({ entries, benchmarkReturn }: { entries: [string, BacktestResult][]; benchmarkReturn: number | null }) {
  const beat = benchmarkReturn === null ? null : entries.filter(([, r]) => r.total_return_pct > benchmarkReturn).length;

  return (
    <Section title="Leaders">
      <Table>
        <tbody>
          {RANKINGS.map((ranking) => {
            const [name, r] = leader(entries, ranking);
            return (
              <tr key={ranking.value}>
                <Td className="text-muted-foreground">{ranking.label}</Td>
                <Td>{strategyName(name)}</Td>
                <Td num align="right">
                  {ranking.format(ranking.get(r))}
                </Td>
              </tr>
            );
          })}
          {benchmarkReturn !== null && (
            <tr>
              <Td className="text-muted-foreground">Beat buy & hold</Td>
              <Td>
                {beat} of {entries.length}
              </Td>
              <Td num align="right">
                {formatPercent(benchmarkReturn)}
              </Td>
            </tr>
          )}
        </tbody>
      </Table>
      <p className="mt-3 text-2xs text-muted-foreground">In-sample on this window only; none of this is validated out of sample.</p>
    </Section>
  );
}

function ResultsTable({ entries }: { entries: [string, BacktestResult][] }) {
  const blocked = entries.flatMap(([name]) => {
    const block = strategySpec(name)?.exportBlock;
    return block ? [{ name, ...block }] : [];
  });

  return (
    <Section title="Metrics">
      <Table>
        <thead>
          <tr>
            <Th>Strategy</Th>
            <Th align="right">Return</Th>
            <Th align="right">Sharpe</Th>
            <Th align="right">Max drawdown</Th>
            <Th align="right">Win rate</Th>
            <Th align="right">Profit factor</Th>
            <Th align="right">Trades</Th>
            <Th>AlphaLive</Th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, r], i) => (
            <tr key={name}>
              <Td>
                <Swatch color={SERIES_COLORS[i]} />
                {strategyName(name)}
              </Td>
              <Td num align="right" className={pnlColor(r.total_return_pct)}>
                {formatPercent(r.total_return_pct)}
              </Td>
              <Td num align="right">
                {formatNumber(r.metrics.risk.sharpe_ratio)}
              </Td>
              <Td num align="right">
                {formatPercent(r.metrics.drawdown.max_drawdown_pct)}
              </Td>
              <Td num align="right">
                {formatPercent(r.metrics.trades.win_rate * 100, 2, false)}
              </Td>
              <Td num align="right">
                {formatNumber(r.metrics.trades.profit_factor)}
              </Td>
              <Td num align="right">
                {r.total_trades}
              </Td>
              <Td className={strategySpec(name)?.exportBlock ? "text-loss" : "text-muted-foreground"}>
                {strategySpec(name)?.exportBlock?.label ?? "Export from Backtest"}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {blocked.map((b) => (
        <p key={b.name} className="mt-3 text-2xs text-muted-foreground">
          <span className="text-foreground">{strategyName(b.name)}</span>: {b.reason}
        </p>
      ))}
    </Section>
  );
}
