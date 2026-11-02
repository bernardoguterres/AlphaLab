import { useNavigate } from "react-router-dom";
import type { BacktestHistoryItem } from "@/types";
import { ApiOfflineNotice } from "@/components/layout/ApiOfflineNotice";
import { Page } from "@/components/layout/Page";
import { RunSummary } from "@/components/backtest/RunSummary";
import { ExportButton } from "@/components/export/ExportButton";
import { Button } from "@/components/ui/button";
import { Table, Td, Th } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { KeyValue, KeyValueList } from "@/components/ui/key-value";
import { Section } from "@/components/ui/section";
import { useBacktestStore } from "@/stores/backtestStore";
import { CACHE_EXPIRY_HOURS, cacheSpan, freshness } from "@/utils/cache";
import { formatDate, formatDateTime, formatNumber, formatPercent, pnlColor } from "@/utils/formatters";
import { strategyName } from "@/utils/strategies";

const RECENT_RUNS = 8;

export default function Dashboard() {
  const navigate = useNavigate();
  const { history, setCurrentRun } = useBacktestStore();
  const latest = history[0];

  const openRun = (run: BacktestHistoryItem) => {
    setCurrentRun(run);
    navigate("/backtest");
  };

  return (
    <Page
      title="Overview"
      actions={
        <>
          <Button variant="outline" onClick={() => navigate("/compare")}>
            Compare strategies
          </Button>
          <Button onClick={() => navigate("/backtest")}>New backtest</Button>
        </>
      }
    >
      <ApiOfflineNotice />

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-10">
          {latest ? (
            <RunSummary
              run={latest}
              actions={
                <Button variant="outline" size="sm" onClick={() => openRun(latest)}>
                  Open in Backtest
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No saved runs yet"
              description="Runs you save from Backtest, or comparisons you save from Compare, are listed here."
              action={<Button onClick={() => navigate("/backtest")}>Run a backtest</Button>}
            />
          )}

          {history.length > 0 && (
            <Section
              title="Saved runs"
              aside={history.length > RECENT_RUNS ? `Latest ${RECENT_RUNS} of ${history.length}` : `${history.length} in this browser`}
            >
              <Table>
                <thead>
                  <tr>
                    <Th>Saved</Th>
                    <Th>Ticker</Th>
                    <Th>Strategy</Th>
                    <Th align="right">Return</Th>
                    <Th align="right">Sharpe</Th>
                    <Th align="right">Max drawdown</Th>
                    <Th align="right">Trades</Th>
                    <Th align="right">
                      <span className="sr-only">Actions</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, RECENT_RUNS).map((run) => (
                    <tr key={run.id} className="hover:bg-muted/50">
                      <Td num className="text-muted-foreground">
                        {formatDate(run.date)}
                      </Td>
                      <Td num>{run.ticker}</Td>
                      <Td>{strategyName(run.strategy)}</Td>
                      <Td num align="right" className={pnlColor(run.total_return_pct)}>
                        {formatPercent(run.total_return_pct)}
                      </Td>
                      <Td num align="right">
                        {formatNumber(run.sharpe_ratio)}
                      </Td>
                      <Td num align="right">
                        {formatPercent(run.max_drawdown)}
                      </Td>
                      <Td num align="right">
                        {run.total_trades}
                      </Td>
                      <Td align="right" className="space-x-4">
                        <Button variant="link" size="sm" onClick={() => openRun(run)}>
                          Open
                        </Button>
                        <ExportButton backtestId={run.result.backtest_id} strategy={run.strategy} ticker={run.ticker} variant="link" label="Export" />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Section>
          )}
        </div>

        <aside>
          <CacheSummary />
        </aside>
      </div>
    </Page>
  );
}

function CacheSummary() {
  const navigate = useNavigate();
  const cachedTickers = useBacktestStore((s) => s.cachedTickers);
  const expired = cachedTickers.filter((c) => freshness(c) === "expired").length;
  const span = cacheSpan(cachedTickers);

  return (
    <Section
      title="Market data cache"
      aside={
        <Button variant="link" size="sm" onClick={() => navigate("/data")}>
          Manage
        </Button>
      }
    >
      <KeyValueList>
        <KeyValue label="Datasets" value={cachedTickers.length} />
        <KeyValue label="Tickers" value={new Set(cachedTickers.map((c) => c.ticker)).size} />
        <KeyValue label={`Older than ${CACHE_EXPIRY_HOURS}h`} value={expired} tone={expired > 0 ? "text-warning" : undefined} />
        <KeyValue label="Newest" value={span ? formatDateTime(span.newest) : "-"} />
        <KeyValue label="Oldest" value={span ? formatDateTime(span.oldest) : "-"} />
      </KeyValueList>
    </Section>
  );
}
