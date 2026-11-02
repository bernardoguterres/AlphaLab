import { useState } from "react";
import { toast } from "sonner";
import type { BatchBacktestResponse, StrategyType } from "@/types";
import { DEFAULT_RISK_SETTINGS } from "@/types";
import { DateRangeFields, StrategyField } from "@/components/forms/RunFields";
import { Button } from "@/components/ui/button";
import { Table, Td, Th } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { Section } from "@/components/ui/section";
import { Stat, StatGrid } from "@/components/ui/stat";
import { Tag } from "@/components/ui/tag";
import { errorMessage, runBatchBacktest } from "@/services/api";
import { useBacktestStore } from "@/stores/backtestStore";
import { DEFAULT_CAPITAL, DEFAULT_END, DEFAULT_START } from "@/utils/defaults";
import { downloadJson, isoDate } from "@/utils/download";
import { formatNumber, formatPercent, pnlColor } from "@/utils/formatters";
import { DEFAULT_PARAMS } from "@/utils/strategies";

const MAX_TICKERS = 20;
const QUICK_PICKS = 10;

/** One strategy, default parameters, many tickers. */
export function BatchBacktest() {
  const cachedTickers = useBacktestStore((s) => s.cachedTickers);
  const [strategy, setStrategy] = useState<StrategyType>("ma_crossover");
  const [startDate, setStartDate] = useState(DEFAULT_START);
  const [endDate, setEndDate] = useState(DEFAULT_END);
  const [tickers, setTickers] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [running, setRunning] = useState(false);
  const [batch, setBatch] = useState<BatchBacktestResponse["data"] | null>(null);

  const addTicker = (raw: string) => {
    const ticker = raw.trim().toUpperCase();
    if (ticker && !tickers.includes(ticker)) setTickers([...tickers, ticker]);
  };
  const submitDraft = () => {
    addTicker(draft);
    setDraft("");
  };
  const quickPicks = [...new Set(cachedTickers.map((c) => c.ticker))].filter((t) => !tickers.includes(t)).slice(0, QUICK_PICKS);

  const handleRun = async () => {
    if (tickers.length > MAX_TICKERS) {
      toast.error(`A batch can include at most ${MAX_TICKERS} tickers`);
      return;
    }
    setRunning(true);
    setBatch(null);
    try {
      const response = await runBatchBacktest({
        tickers,
        strategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: DEFAULT_CAPITAL,
        params: DEFAULT_PARAMS[strategy],
        position_sizing: "equal_weight",
        risk_settings: DEFAULT_RISK_SETTINGS,
      });
      setBatch(response.data);
    } catch (error) {
      toast.error(errorMessage(error, "Batch backtest failed"));
    } finally {
      setRunning(false);
    }
  };

  const exportTopFive = () => {
    if (!batch) return;
    const top = batch.results.slice(0, 5).map((row) => ({ ...row, strategy }));
    downloadJson(top, `batch_top5_${strategy}_${isoDate()}.json`);
  };

  return (
    <div className="space-y-8">
      <div className="grid max-w-4xl grid-cols-2 gap-4 md:grid-cols-4">
        <div className="col-span-2">
          <StrategyField value={strategy} onChange={setStrategy} />
        </div>
        <DateRangeFields start={startDate} end={endDate} onStartChange={setStartDate} onEndChange={setEndDate} />
        <div className="col-span-2">
          <Field label={`Tickers (${tickers.length}/${MAX_TICKERS})`} htmlFor="batch-ticker">
            <div className="flex gap-2">
              <Input
                id="batch-ticker"
                className="num uppercase placeholder:normal-case"
                placeholder="Enter ticker"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submitDraft()}
              />
              <Button variant="outline" onClick={submitDraft}>
                Add
              </Button>
            </div>
          </Field>
        </div>
        <div className="col-span-2 flex flex-wrap items-end gap-1.5 md:col-span-2">
          {quickPicks.length > 0 && <span className="mr-1 pb-1.5 text-2xs text-muted-foreground">Cached:</span>}
          {quickPicks.map((t) => (
            <Button key={t} variant="ghost" size="sm" className="num" onClick={() => addTicker(t)}>
              + {t}
            </Button>
          ))}
        </div>
      </div>

      {tickers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tickers.map((t) => (
            <Tag key={t} onRemove={() => setTickers(tickers.filter((x) => x !== t))} removeLabel={`Remove ${t}`}>
              <span className="num">{t}</span>
            </Tag>
          ))}
        </div>
      )}

      <Button onClick={handleRun} disabled={running || tickers.length === 0}>
        {running ? "Running batch…" : `Run batch backtest (${tickers.length} tickers)`}
      </Button>

      {batch ? (
        <BatchResults batch={batch} onExport={exportTopFive} />
      ) : (
        !running && (
          <EmptyState title="No batch run yet" description="Add tickers and run the batch to rank them by Sharpe ratio using the default parameters." />
        )
      )}
    </div>
  );
}

function BatchResults({ batch, onExport }: { batch: BatchBacktestResponse["data"]; onExport: () => void }) {
  const { batch_summary: summary, results, errors } = batch;

  return (
    <div className="space-y-8">
      <Section
        title="Summary"
        aside={
          <Button variant="link" size="sm" onClick={onExport}>
            Export top 5 (JSON)
          </Button>
        }
      >
        <StatGrid>
          <Stat label="Tested" value={`${summary.successful}/${summary.total_tickers}`} hint={summary.failed > 0 ? `${summary.failed} failed` : undefined} />
          <Stat label="Profitable" value={formatPercent(summary.profitable_pct, 2, false)} hint={`${summary.profitable_count} tickers`} />
          <Stat label="Average Sharpe" value={formatNumber(summary.avg_sharpe_ratio)} />
          {summary.best_ticker && <Stat label="Best" value={summary.best_ticker} hint={`Sharpe ${formatNumber(summary.best_sharpe)}`} />}
          {summary.worst_ticker && <Stat label="Worst" value={summary.worst_ticker} hint={`Sharpe ${formatNumber(summary.worst_sharpe)}`} />}
          <Stat label="Runtime" value={`${summary.runtime_seconds}s`} />
        </StatGrid>
      </Section>

      <Section title="Results by Sharpe ratio">
        <Table>
          <thead>
            <tr>
              <Th>Ticker</Th>
              <Th align="right">Return</Th>
              <Th align="right">Sharpe</Th>
              <Th align="right">Max drawdown</Th>
              <Th align="right">Win rate</Th>
              <Th align="right">Trades</Th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.ticker}>
                <Td num>{r.ticker}</Td>
                <Td num align="right" className={pnlColor(r.total_return_pct)}>
                  {formatPercent(r.total_return_pct)}
                </Td>
                <Td num align="right">
                  {formatNumber(r.sharpe_ratio)}
                </Td>
                <Td num align="right">
                  {formatPercent(r.max_drawdown_pct)}
                </Td>
                <Td num align="right">
                  {/* win_rate is a 0-1 fraction */}
                  {formatPercent(r.win_rate * 100, 2, false)}
                </Td>
                <Td num align="right">
                  {r.total_trades}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>

      {errors.length > 0 && (
        <Notice tone="loss" title={`${errors.length} ticker${errors.length === 1 ? "" : "s"} failed`}>
          <ul className="space-y-0.5">
            {errors.map((e) => (
              <li key={e.ticker}>
                <span className="num text-foreground">{e.ticker}</span> {e.error}
              </li>
            ))}
          </ul>
        </Notice>
      )}
    </div>
  );
}
