import { useState, useEffect } from "react";
import { useBacktestStore } from "@/stores/backtestStore";
import { getAvailableData, fetchData } from "@/services/api";
import { formatDate } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";
import { MetricCard } from "@/components/metrics/MetricCard";
import { StatusBadge } from "@/components/ui/status-badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { Loader2, Database, RefreshCw, Search, Download, Layers, Hash, Clock, Server, CalendarClock } from "lucide-react";
import { cn } from "@/lib/utils";

const INTERVAL_STYLES: Record<string, string> = {
  "1d": "bg-primary/10 text-primary border-primary/30",
  "1wk": "bg-gain/10 text-gain border-gain/30",
  "1mo": "bg-warning/10 text-warning border-warning/30",
};

const INTERVAL_LABELS: Record<string, string> = {
  "1d": "Daily",
  "1wk": "Weekly",
  "1mo": "Monthly",
};

function IntervalBadge({ interval }: { interval: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase",
        INTERVAL_STYLES[interval] || "bg-secondary text-muted-foreground border-border"
      )}
    >
      {interval}
    </span>
  );
}

export default function DataManager() {
  const { cachedTickers, setCachedTickers, isBackendOnline } = useBacktestStore();
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch form
  const [tickers, setTickers] = useState("AAPL, MSFT, GOOGL");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [interval, setInterval] = useState("1d");
  const [isFetching, setIsFetching] = useState(false);
  const [fetchProgress, setFetchProgress] = useState(0);

  const loadCachedData = async () => {
    setIsLoading(true);
    try {
      const data = await getAvailableData();
      setCachedTickers(Array.isArray(data) ? data : []);
    } catch {
      // Backend might not be running
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCachedData();
  }, []);

  const handleFetch = async () => {
    const tickerList = tickers.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);
    if (tickerList.length === 0) { toast.error("Enter at least one ticker"); return; }
    if (tickerList.length > 20) { toast.error("Maximum 20 tickers at once"); return; }

    setIsFetching(true);
    setFetchProgress(0);

    // Fetch all at once
    try {
      const result = await fetchData(tickerList, startDate, endDate, interval);
      setFetchProgress(100);
      const successCount = Object.keys(result.data || {}).length;
      if (successCount > 0) toast.success(`Fetched data for ${successCount} ticker(s)`);
      if (result.errors?.length) result.errors.forEach((e) => toast.error(e));
      await loadCachedData();
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Failed to fetch data");
    } finally {
      setIsFetching(false);
    }
  };

  const filtered = cachedTickers.filter((t) =>
    t.ticker.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Real derived stats - no fake numbers
  const uniqueTickerCount = new Set(cachedTickers.map((t) => t.ticker)).size;
  const totalRecords = cachedTickers.reduce((sum, t) => sum + (t.records || 0), 0);
  const mostRecentUpdate = cachedTickers.reduce<string | null>((latest, t) => {
    const ts = new Date(t.last_updated).getTime();
    if (isNaN(ts)) return latest;
    if (!latest || ts > new Date(latest).getTime()) return t.last_updated;
    return latest;
  }, null);

  const now = Date.now();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;
  const datasetsWithValidTimestamp = cachedTickers.filter((t) => !isNaN(new Date(t.last_updated).getTime()));
  const freshCount = datasetsWithValidTimestamp.filter((t) => now - new Date(t.last_updated).getTime() <= sevenDaysMs).length;
  // Only meaningful once at least one dataset actually has a parseable last_updated value -
  // otherwise "0%" would misleadingly read as "stale" when it's really "unknown".
  const freshnessPct = datasetsWithValidTimestamp.length > 0
    ? Math.round((freshCount / datasetsWithValidTimestamp.length) * 100)
    : null;

  const tickerChips = tickers.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);

  return (
    <div className="page-shell py-8 space-y-6 animate-in-stagger">
      {/* Page header / command strip */}
      <div className="hero-panel px-6 py-6 sm:px-8 sm:py-7">
        <div className="glow-blob h-36 w-36 -bottom-14 right-1/4 opacity-20 bg-lab-secondary" />
        <div className="flex items-start justify-between flex-wrap gap-5 relative">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 mb-2.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              <span className="text-[11px] font-semibold text-primary uppercase tracking-widest">Market Data Warehouse</span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight gradient-text leading-tight">
              Data Manager
            </h1>
            <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
              Fetch, cache, and manage the OHLCV market data your backtests and comparisons run against.
            </p>
            <div className="flex items-center gap-2 mt-4 flex-wrap">
              <StatusBadge
                label={isBackendOnline ? "Backend Online" : "Backend Offline"}
                tone={isBackendOnline ? "gain" : "loss"}
                dot
                pulse={isBackendOnline}
                className="normal-case tracking-normal"
              />
              <StatusBadge label={`${cachedTickers.length} datasets cached`} tone="primary" className="normal-case tracking-normal" />
              <StatusBadge label="Daily · Weekly · Monthly" tone="neutral" className="normal-case tracking-normal" />
            </div>
          </div>
          <Button variant="outline" className="gap-2 shrink-0" onClick={loadCachedData} disabled={isLoading}>
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Cached Datasets" value={cachedTickers.length.toString()} icon={<Layers className="h-4 w-4" />} tone="primary" accent />
        <MetricCard label="Unique Tickers" value={uniqueTickerCount.toString()} icon={<Hash className="h-4 w-4" />} tone="cyan" accent />
        <MetricCard label="Total Records" value={totalRecords.toLocaleString()} icon={<Database className="h-4 w-4" />} tone="gain" accent />
        <MetricCard
          label="Last Refresh"
          value={mostRecentUpdate ? formatDate(mostRecentUpdate) : "-"}
          subValue={
            mostRecentUpdate
              ? "Most recently cached dataset"
              : cachedTickers.length === 0
                ? "No data cached yet"
                : "No valid timestamp available"
          }
          icon={<Clock className="h-4 w-4" />}
          tone="warning"
          accent
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-start">
        <div className="xl:col-span-2 space-y-5">
          {/* Fetch Data panel */}
          <div className="card-elevated p-4 sm:p-5 space-y-4">
            <div className="flex items-center gap-2">
              <Download className="h-3.5 w-3.5 text-primary" />
              <h2 className="section-label">Fetch New Data</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="col-span-2">
                <Label className="text-xs">Tickers (comma-separated, max 20)</Label>
                <Input value={tickers} onChange={(e) => setTickers(e.target.value.toUpperCase())} placeholder="AAPL, MSFT, GOOGL" className="mt-1 font-mono-numbers" />
                {tickerChips.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {tickerChips.slice(0, 20).map((t, i) => (
                      <span key={`${t}-${i}`} className="inline-flex items-center text-[10px] font-mono-numbers font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                        {t}
                      </span>
                    ))}
                    {tickerChips.length > 20 && (
                      <span className="text-[10px] text-loss font-medium px-1">+{tickerChips.length - 20} over limit</span>
                    )}
                  </div>
                )}
              </div>
              <div>
                <Label className="text-xs">Start Date</Label>
                <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-1" />
              </div>
              <div>
                <Label className="text-xs">End Date</Label>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="mt-1" />
              </div>
            </div>
            <div className="flex items-end gap-4 flex-wrap">
              <div className="w-40">
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
              <Button className="gap-2 shadow-md shadow-primary/15" onClick={handleFetch} disabled={isFetching}>
                {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                {isFetching ? "Fetching..." : "Fetch Data"}
              </Button>
            </div>
            {isFetching && <Progress value={fetchProgress} className="h-1" />}
          </div>

          {/* Dataset browser */}
          <div className="card-elevated overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3.5 border-b border-border flex-wrap gap-2">
              <h2 className="text-[15px] font-bold tracking-tight flex items-center gap-2">
                <Server className="h-3.5 w-3.5 text-lab-secondary" />
                {filtered.length} Cached Dataset{filtered.length === 1 ? "" : "s"}
              </h2>
              <div className="relative w-60">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter by ticker..."
                  className="pl-8 h-8 text-xs"
                />
              </div>
            </div>
            {filtered.length === 0 ? (
              <EmptyState
                icon={Database}
                title={cachedTickers.length === 0 ? "No cached data" : "No matches found"}
                description={
                  cachedTickers.length === 0
                    ? "Fetch market data above to start building your local cache for backtesting."
                    : "Try a different ticker search query."
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-secondary/20">
                      <th className="px-4 py-2.5 text-left label-caps">Ticker</th>
                      <th className="px-4 py-2.5 text-left label-caps">Interval</th>
                      <th className="px-4 py-2.5 text-left label-caps">Start</th>
                      <th className="px-4 py-2.5 text-left label-caps">End</th>
                      <th className="px-4 py-2.5 text-right label-caps">Records</th>
                      <th className="px-4 py-2.5 text-right label-caps">Last Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((item, index) => (
                      <tr key={`${item.ticker}-${item.interval}-${item.start_date}-${item.end_date}-${index}`} className="border-b border-border/50 hover:bg-secondary/40 transition-colors">
                        <td className="px-4 py-2.5 font-semibold font-mono-numbers">{item.ticker}</td>
                        <td className="px-4 py-2.5"><IntervalBadge interval={item.interval} /></td>
                        <td className="px-4 py-2.5 font-mono-numbers text-xs text-muted-foreground">{formatDate(item.start_date)}</td>
                        <td className="px-4 py-2.5 font-mono-numbers text-xs text-muted-foreground">{formatDate(item.end_date)}</td>
                        <td className="px-4 py-2.5 text-right font-mono-numbers">{item.records.toLocaleString()}</td>
                        <td className="px-4 py-2.5 text-right font-mono-numbers text-xs text-muted-foreground">{formatDate(item.last_updated)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Data status sidebar */}
        <div className="space-y-5">
          <div className="card-elevated p-4">
            <h2 className="section-label mb-3 flex items-center gap-1.5">
              <Server className="h-3.5 w-3.5" /> System Status
            </h2>
            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Backend</span>
                <StatusBadge
                  label={isBackendOnline ? "Online" : "Offline"}
                  tone={isBackendOnline ? "gain" : "loss"}
                  dot
                  pulse={isBackendOnline}
                />
              </div>
              <Separator className="bg-border/50" />
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Cached datasets</span>
                <span className="font-mono-numbers font-semibold">{cachedTickers.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Unique tickers</span>
                <span className="font-mono-numbers font-semibold">{uniqueTickerCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Total records</span>
                <span className="font-mono-numbers font-semibold">{totalRecords.toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div className="card-elevated p-4">
            <h2 className="section-label mb-3 flex items-center gap-1.5">
              <CalendarClock className="h-3.5 w-3.5" /> Cache Freshness
            </h2>
            {freshnessPct !== null ? (
              <>
                <div className="h-1.5 rounded-full bg-secondary/60 overflow-hidden mb-2.5">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      freshnessPct >= 70 ? "bg-gain" : freshnessPct >= 40 ? "bg-warning" : "bg-loss"
                    )}
                    style={{ width: `${freshnessPct}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  <span className="font-mono-numbers font-semibold text-foreground">{freshnessPct}%</span> of datasets refreshed in the last 7 days
                </p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground/70">
                {cachedTickers.length === 0
                  ? "No cached data to evaluate yet."
                  : "Cached datasets don't include a valid last-updated timestamp yet."}
              </p>
            )}
          </div>

          <div className="card-elevated p-4">
            <h2 className="section-label mb-3">Supported Intervals</h2>
            <div className="space-y-2">
              {Object.entries(INTERVAL_LABELS).map(([key, label]) => (
                <div key={key} className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{label}</span>
                  <IntervalBadge interval={key} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
