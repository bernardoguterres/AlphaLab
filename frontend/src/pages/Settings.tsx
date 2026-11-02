import { Link } from "react-router-dom";
import { DEFAULT_RISK_SETTINGS } from "@/types";
import { Page } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { KeyValue, KeyValueList } from "@/components/ui/key-value";
import { Section } from "@/components/ui/section";
import { useBacktestStore } from "@/stores/backtestStore";
import { CACHE_EXPIRY_HOURS } from "@/utils/cache";
import { DEFAULT_CAPITAL, DEFAULT_END, DEFAULT_START } from "@/utils/defaults";
import { formatCurrency, formatDate } from "@/utils/formatters";
import { STRATEGIES, STRATEGY_TYPES } from "@/utils/strategies";

// The engine values below are transcribed from backend/config.yaml, which no
// endpoint exposes. Nothing on this page is editable or saved: per-run
// assumptions are changed in Backtest.

const FIXED = "Fixed";
const PER_RUN = "Set per run in Backtest";

export default function Settings() {
  const { cachedTickers, isBackendOnline } = useBacktestStore();
  const risk = DEFAULT_RISK_SETTINGS;
  const blocked = STRATEGY_TYPES.filter((s) => STRATEGIES[s].exportBlock).map((s) => STRATEGIES[s].name);

  return (
    <Page title="Settings">
      <p className="max-w-prose text-[13px] text-muted-foreground">
        A reference for AlphaLab's defaults and fixed rules. Change the per-run ones in{" "}
        <Button asChild variant="link">
          <Link to="/backtest">Backtest</Link>
        </Button>
        .
      </p>

      <div className="grid gap-x-12 gap-y-8 lg:grid-cols-2">
        <Section title="Research defaults">
          <KeyValueList>
            <KeyValue plain label="Benchmark" value="Buy & hold, same ticker" note={FIXED} />
            <KeyValue label="Starting capital" value={formatCurrency(DEFAULT_CAPITAL)} note={PER_RUN} />
            <KeyValue label="Test window" value={`${formatDate(DEFAULT_START)} – ${formatDate(DEFAULT_END)}`} note={PER_RUN} />
            <KeyValue plain label="Bar interval" value="Daily" note="Weekly and monthly are also available" />
            <KeyValue label="Risk-free rate" value="4.00%" note="Used by Sharpe and Sortino" />
          </KeyValueList>
        </Section>

        <Section title="Execution costs">
          <KeyValueList>
            <KeyValue label="Commission per trade" value={formatCurrency(risk.commission_per_trade)} note={PER_RUN} />
            <KeyValue label="Slippage" value="0.05%" note="Applied to every fill; not configurable" />
            <KeyValue plain label="Fill timing" value="Next bar open" note="A signal on bar N fills at bar N+1; not configurable" />
          </KeyValueList>
        </Section>

        <Section title="Risk defaults">
          <KeyValueList>
            <KeyValue label="Max position size" value={`${risk.max_position_size_pct}%`} />
            <KeyValue label="Max open positions" value={risk.max_open_positions} />
            <KeyValue label="Stop loss" value={`${risk.stop_loss_pct}%`} />
            <KeyValue label="Take profit" value={`${risk.take_profit_pct}%`} />
            <KeyValue label="Max daily loss" value={`${risk.max_daily_loss_pct}%`} />
            <KeyValue label="Trailing stop" value={risk.trailing_stop_enabled ? `${risk.trailing_stop_pct}%` : "Off"} />
          </KeyValueList>
          <p className="mt-2 text-2xs text-muted-foreground">{PER_RUN}.</p>
        </Section>

        <Section title="Market data">
          <KeyValueList>
            <KeyValue plain label="Provider" value="Yahoo Finance" note="Adjusted OHLCV via yfinance" />
            <KeyValue label="Cache expiry" value={`${CACHE_EXPIRY_HOURS} hours`} note={FIXED} />
            <KeyValue
              label="Cached now"
              value={`${cachedTickers.length} datasets, ${new Set(cachedTickers.map((c) => c.ticker)).size} tickers`}
              note={
                <Link to="/data" className="underline decoration-muted-foreground underline-offset-2 hover:text-foreground">
                  Manage in Data
                </Link>
              }
            />
          </KeyValueList>
        </Section>

        <Section title="AlphaLive export">
          <KeyValueList>
            <KeyValue plain label="Format" value="Strategy JSON" note="AlphaLive's schema; fixed" />
            <KeyValue plain label="Included" value="Parameters, costs, risk" note="Exactly what the run simulated" />
            <KeyValue plain label="Never exportable" value={blocked.join(", ")} note="AlphaLive cannot run them" />
          </KeyValueList>
          <p className="mt-2 text-2xs text-muted-foreground">AlphaLab never places orders. AlphaLive does, from an exported file.</p>
        </Section>

        <Section title="Connection">
          <KeyValueList>
            <KeyValue
              plain
              label="API"
              value={isBackendOnline === null ? "Checking…" : isBackendOnline ? "Connected" : "Offline"}
              note="Flask, 127.0.0.1:5050"
              tone={isBackendOnline === false ? "text-loss" : undefined}
            />
          </KeyValueList>
          <p className="mt-2 text-2xs text-muted-foreground">Broker, execution and notification settings live in AlphaLive.</p>
        </Section>
      </div>
    </Page>
  );
}
