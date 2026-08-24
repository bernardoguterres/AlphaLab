import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBacktestStore } from "@/stores/backtestStore";
import { getAvailableData } from "@/services/api";
import { Button } from "@/components/ui/button";
import {
  Lock, CheckCircle2, Database, RefreshCw, ArrowRight, Info, Loader2,
  TrendingUp, Percent, Shield, Clock, FileJson,
} from "lucide-react";

// AlphaLab has no settings-persistence mechanism (no API stores research
// defaults, and Backtest Studio's own form state can't be wired from here
// without touching that page - out of scope for this task). Every value
// below is real and verified, but read-only:
//   - backend/config.yaml literals (initial_capital, commission, slippage,
//     risk_free_rate, cache_expiry_hours) - loaded backend-side only via
//     load_config(), never exposed through any API, so these are static
//     transcriptions of the real file, not a live fetch.
//   - DEFAULT_RISK_SETTINGS / Backtest Studio's own default form state -
//     documented here, actually editable only on the Backtest page itself.
//   - cachedTickers - genuinely live, from the same store DataManager uses.
//   - real, fixed backend rules (next-bar execution, export schema, the
//     rsi_simple/vwap_reversion export block).
// Nothing here is saved anywhere - there is no Save button because there
// is nothing to save.

function SettingsSection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="card-elevated p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-primary">{icon}</span>
        <h2 className="text-sm font-bold tracking-tight">{title}</h2>
      </div>
      <div>{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  caption,
  locked,
  verified,
}: {
  label: string;
  value: string;
  caption?: string;
  locked?: boolean;
  verified?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-border/30 last:border-0">
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        {caption && <p className="text-[10px] text-muted-foreground/85 mt-0.5 leading-snug">{caption}</p>}
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {locked && <Lock className="h-3 w-3 text-muted-foreground/70" />}
        <span className="font-mono-numbers text-xs font-semibold text-foreground">{value}</span>
        {verified && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-gain">
            <CheckCircle2 className="h-3 w-3" /> Verified
          </span>
        )}
      </div>
    </div>
  );
}

export default function Settings() {
  const navigate = useNavigate();
  const { cachedTickers, setCachedTickers, isBackendOnline } = useBacktestStore();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshCacheSummary = async () => {
    setIsRefreshing(true);
    try {
      const data = await getAvailableData();
      setCachedTickers(Array.isArray(data) ? data : []);
    } catch {
      // Backend might not be running - cache summary just stays as-is.
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    refreshCacheSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const uniqueTickers = new Set(cachedTickers.map((t) => t.ticker)).size;

  return (
    <div className="page-shell py-5 space-y-3.5 animate-in-stagger">
      {/* Compact header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground leading-none">Research Settings</h1>
          <p className="text-xs text-muted-foreground/90 mt-1.5">Reference defaults for backtesting, data, and export</p>
        </div>
      </div>

      {/* Honesty banner - no fake Save/Reset controls */}
      <div className="card-elevated p-3.5 flex items-start gap-3">
        <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />
        <p className="text-xs text-muted-foreground/90 leading-relaxed">
          These values reflect AlphaLab's current engine defaults. Change supported per-run assumptions in{" "}
          <button onClick={() => navigate("/backtest")} className="text-primary hover:underline font-medium">Backtest Studio</button>.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3.5">
        <SettingsSection title="Research Defaults" icon={<TrendingUp className="h-4 w-4" />}>
          <Field label="Benchmark" value="Buy & Hold (same ticker)" caption="Not SPY, not configurable - the engine always benchmarks against buy-and-hold of the ticker under test." locked />
          <Field label="Initial Capital" value="$100,000" caption="Engine default (config.yaml) - editable per run in Backtest Studio." />
          <Field label="Default Interval" value="Daily" caption="Backtest Studio's default - Weekly and Monthly are also selectable per run." />
          <Field label="Risk-Free Rate" value="4.00%" caption="Engine default (config.yaml) - used in Sharpe/Sortino calculations." />
          <Field label="Default Test Window" value="Jan 2020 - Dec 2024" caption="Backtest Studio's default date range - fully editable per run." />
        </SettingsSection>

        <SettingsSection title="Execution Cost Assumptions" icon={<Percent className="h-4 w-4" />}>
          <Field label="Commission per Trade" value="$0.00" caption="Engine default (config.yaml) - editable per run via Backtest Studio's Risk Settings." />
          <Field label="Slippage" value="0.05%" caption="Engine default (config.yaml) - applied to every run, not user-configurable anywhere in the app." locked />
          <Field label="Execution Timing" value="Next bar" caption="Signals at bar N execute at bar N+1's open - architecturally invariant, cannot be changed." locked verified />
        </SettingsSection>

        <SettingsSection title="Portfolio & Risk Defaults" icon={<Shield className="h-4 w-4" />}>
          <Field label="Max Position Size" value="10%" />
          <Field label="Max Concurrent Positions" value="5" />
          <Field label="Stop Loss" value="2%" />
          <Field label="Take Profit" value="5%" />
          <Field label="Trailing Stop" value="Off" />
          <p className="text-[10px] text-muted-foreground/85 pt-2.5 mt-1 border-t border-border/30">
            Backtest Studio's default Risk Settings - all fully editable per run there.
          </p>
        </SettingsSection>

        <SettingsSection title="Data & Cache" icon={<Database className="h-4 w-4" />}>
          <Field label="Data Provider" value="Yahoo Finance" caption="Adjusted OHLCV via yfinance." locked />
          <Field label="Cache Expiry" value="24 hours" caption="Engine default (config.yaml) - governs when a cached dataset is refetched, not user-configurable." locked />
          <div className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Cache Summary</p>
              <p className="text-[10px] text-muted-foreground/85 mt-0.5">Live from the current cache.</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="font-mono-numbers text-xs font-semibold">
                {cachedTickers.length} dataset{cachedTickers.length === 1 ? "" : "s"} / {uniqueTickers} ticker{uniqueTickers === 1 ? "" : "s"}
              </span>
              <button
                onClick={refreshCacheSummary}
                disabled={isRefreshing}
                title="Refresh cache summary"
                aria-label="Refresh cache summary"
                className="text-muted-foreground hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
              >
                {isRefreshing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
          <Button variant="outline" size="sm" className="w-full gap-2 mt-1" onClick={() => navigate("/data")}>
            <Database className="h-3.5 w-3.5" /> Manage Cached Data <ArrowRight className="h-3 w-3 ml-auto" />
          </Button>
        </SettingsSection>

        <SettingsSection title="AlphaLive Export Defaults" icon={<FileJson className="h-4 w-4" />}>
          <Field label="Export Format" value="Strategy JSON (v1.0)" caption="Fixed schema - not configurable." locked />
          <Field label="Cost Assumptions" value="Always included" caption="Every export embeds the run's real commission and risk settings." locked />
          <Field label="Validation Before Export" value="Enforced" caption="rsi_simple (research-only) and vwap_reversion (intraday required) are always blocked; every other strategy passes." locked verified />
          <p className="text-[10px] text-muted-foreground/85 pt-2.5 mt-1 border-t border-border/30">
            Exports are configuration files for AlphaLive to consume for paper trading / testing - AlphaLab itself never places an order.
          </p>
        </SettingsSection>

        <SettingsSection title="Connection" icon={<Clock className="h-4 w-4" />}>
          <Field label="Backend" value={isBackendOnline ? "Online" : "Offline"} caption="Flask API at localhost:5050." />
          <p className="text-[10px] text-muted-foreground/85 pt-2.5 mt-1 border-t border-border/30 leading-relaxed">
            Broker, execution, and notification settings are managed in AlphaLive.
          </p>
        </SettingsSection>
      </div>
    </div>
  );
}
