import { useEffect, useMemo, useState } from "react";
import { useBacktestStore } from "@/stores/backtestStore";
import { getAvailableData, fetchData } from "@/services/api";
import type { CachedTicker } from "@/types";
import { formatDate, formatDateTime } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Loader2, Database, RefreshCw, Search, Download, Layers, Hash, CalendarClock,
  ChevronLeft, ChevronRight, AlertTriangle,
} from "lucide-react";
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

const INTERVAL_DESCRIPTIONS: Record<string, string> = {
  "1d": "1 trading day",
  "1wk": "1 week",
  "1mo": "1 calendar month",
};

// Matches the backend's real cache expiry (config.yaml's cache_expiry_hours:
// 24) - the same threshold the Overview page uses, so "fresh" means the
// same thing everywhere in the app rather than two different cutoffs.
const FRESH_WINDOW_MS = 24 * 60 * 60 * 1000;

function IntervalBadge({ interval }: { interval: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase", INTERVAL_STYLES[interval] || "bg-secondary text-muted-foreground border-border")}>
      {interval}
    </span>
  );
}

type Freshness = "fresh" | "expired" | "unknown";

function freshnessOf(item: CachedTicker): { state: Freshness; ageMs: number | null } {
  const ts = new Date(item.last_updated).getTime();
  if (isNaN(ts)) return { state: "unknown", ageMs: null };
  const age = Date.now() - ts;
  return { state: age <= FRESH_WINDOW_MS ? "fresh" : "expired", ageMs: age };
}

function FreshnessBadge({ item }: { item: CachedTicker }) {
  const { state, ageMs } = freshnessOf(item);
  if (state === "unknown") {
    return <span className="text-[10px] text-muted-foreground/85">Unavailable</span>;
  }
  const hours = Math.floor((ageMs ?? 0) / (60 * 60 * 1000));
  const days = Math.floor((ageMs ?? 0) / (24 * 60 * 60 * 1000));
  return (
    <div>
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
          state === "fresh" ? "bg-gain/10 text-gain" : "bg-warning/10 text-warning"
        )}
      >
        {state === "fresh" ? "Fresh" : "Expired"}
      </span>
      <p className="text-[10px] text-muted-foreground/85 mt-0.5">
        {hours < 1 ? "< 1 hour ago" : hours < 24 ? `${hours}h ago` : `${days} day${days === 1 ? "" : "s"} ago`}
      </p>
    </div>
  );
}

type SortKey = "last_updated" | "ticker" | "records";

export default function DataManager() {
  const { cachedTickers, setCachedTickers, isBackendOnline } = useBacktestStore();
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [intervalFilter, setIntervalFilter] = useState<string>("all");
  const [freshnessFilter, setFreshnessFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<SortKey>("last_updated");
  const [page, setPage] = useState(0);
  const [perPage, setPerPage] = useState(25);

  // Fetch form (unchanged fields/behavior, now inside a modal)
  const [fetchOpen, setFetchOpen] = useState(false);
  const [tickers, setTickers] = useState("AAPL, MSFT, GOOGL");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [interval, setInterval] = useState("1d");
  const [isFetching, setIsFetching] = useState(false);
  const [fetchProgress, setFetchProgress] = useState(0);

  // Real quality_score evidence only exists for tickers actually fetched
  // this session (POST /api/data/fetch's response) - never persisted onto
  // the cached-dataset listing itself (GET /api/data/available has no such
  // field), so this is the only honest source for a "Quality" column.
  const [sessionQuality, setSessionQuality] = useState<Record<string, number>>({});
  const [refetchingKey, setRefetchingKey] = useState<string | null>(null);

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

    try {
      const result = await fetchData(tickerList, startDate, endDate, interval);
      setFetchProgress(100);
      const successCount = Object.keys(result.data || {}).length;
      if (successCount > 0) {
        toast.success(`Fetched data for ${successCount} ticker(s)`);
        setSessionQuality((prev) => {
          const next = { ...prev };
          Object.entries(result.data).forEach(([t, d]) => { next[t] = d.quality_score; });
          return next;
        });
        setFetchOpen(false);
      }
      if (result.errors?.length) result.errors.forEach((e) => toast.error(e));
      await loadCachedData();
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Failed to fetch data");
    } finally {
      setIsFetching(false);
    }
  };

  const handleRefetchRow = async (item: CachedTicker) => {
    const key = `${item.ticker}-${item.interval}`;
    setRefetchingKey(key);
    try {
      const result = await fetchData([item.ticker], item.start_date, item.end_date, item.interval);
      const data = result.data?.[item.ticker];
      if (data) {
        toast.success(`Refreshed ${item.ticker} (${data.records} records)`);
        setSessionQuality((prev) => ({ ...prev, [item.ticker]: data.quality_score }));
      }
      if (result.errors?.length) result.errors.forEach((e) => toast.error(e));
      await loadCachedData();
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || `Failed to refresh ${item.ticker}`);
    } finally {
      setRefetchingKey(null);
    }
  };

  // Real derived stats
  const uniqueTickerCount = new Set(cachedTickers.map((t) => t.ticker)).size;
  const totalRecords = cachedTickers.reduce((sum, t) => sum + (t.records || 0), 0);
  const mostRecentUpdate = cachedTickers.reduce<string | null>((latest, t) => {
    const ts = new Date(t.last_updated).getTime();
    if (isNaN(ts)) return latest;
    if (!latest || ts > new Date(latest).getTime()) return t.last_updated;
    return latest;
  }, null);

  const freshCount = cachedTickers.filter((t) => freshnessOf(t).state === "fresh").length;
  const expiredCount = cachedTickers.filter((t) => freshnessOf(t).state === "expired").length;
  const unknownFreshnessCount = cachedTickers.length - freshCount - expiredCount;

  const filteredSorted = useMemo(() => {
    let rows = cachedTickers.filter((t) => t.ticker.toLowerCase().includes(searchQuery.toLowerCase()));
    if (intervalFilter !== "all") rows = rows.filter((t) => t.interval === intervalFilter);
    if (freshnessFilter !== "all") rows = rows.filter((t) => freshnessOf(t).state === freshnessFilter);

    const sorted = [...rows].sort((a, b) => {
      if (sortBy === "ticker") return a.ticker.localeCompare(b.ticker);
      if (sortBy === "records") return b.records - a.records;
      return new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime();
    });
    return sorted;
  }, [cachedTickers, searchQuery, intervalFilter, freshnessFilter, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filteredSorted.length / perPage));
  const pageClamped = Math.min(page, totalPages - 1);
  const pageRows = filteredSorted.slice(pageClamped * perPage, (pageClamped + 1) * perPage);

  const tickerChips = tickers.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);

  return (
    <div className="page-shell py-5 space-y-3.5 animate-in-stagger">
      {/* Compact header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground leading-none">Data Manager</h1>
          <p className="text-xs text-muted-foreground/90 mt-1.5">Inspect, refresh, and manage historical market data</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-1.5" onClick={loadCachedData} disabled={isLoading}>
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} /> Refresh All
          </Button>
          <Button size="sm" className="gap-2" onClick={() => setFetchOpen(true)}>
            <Download className="h-4 w-4" /> Fetch Data
          </Button>
        </div>
      </div>

      {!isBackendOnline && (
        <div className="card-elevated p-3.5 flex items-center gap-3 border-loss/30 bg-loss/[0.03]">
          <AlertTriangle className="h-4 w-4 text-loss shrink-0" />
          <div>
            <p className="text-xs font-medium">Backend not reachable</p>
            <p className="text-[11px] text-muted-foreground">Is the Flask server running on localhost:5050?</p>
          </div>
        </div>
      )}

      {/* Compact summary strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCell icon={<Layers className="h-4 w-4" />} label="Cached Datasets" value={cachedTickers.length.toString()} />
        <SummaryCell icon={<Hash className="h-4 w-4" />} label="Unique Tickers" value={uniqueTickerCount.toString()} />
        <SummaryCell icon={<Database className="h-4 w-4" />} label="Total Records" value={totalRecords.toLocaleString()} />
        <SummaryCell icon={<CalendarClock className="h-4 w-4" />} label="Freshest Update" value={mostRecentUpdate ? formatDate(mostRecentUpdate) : "-"} />
      </div>

      {/* Search + filters */}
      <div className="card-elevated p-3 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={searchQuery} onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }} placeholder="Search ticker..." className="pl-8 h-9 text-sm" />
        </div>
        <Select value={intervalFilter} onValueChange={(v) => { setIntervalFilter(v); setPage(0); }}>
          <SelectTrigger className="h-9 w-[130px] text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All intervals</SelectItem>
            <SelectItem value="1d">Daily</SelectItem>
            <SelectItem value="1wk">Weekly</SelectItem>
            <SelectItem value="1mo">Monthly</SelectItem>
          </SelectContent>
        </Select>
        <Select value={freshnessFilter} onValueChange={(v) => { setFreshnessFilter(v); setPage(0); }}>
          <SelectTrigger className="h-9 w-[130px] text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All freshness</SelectItem>
            <SelectItem value="fresh">Fresh</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={(v: SortKey) => setSortBy(v)}>
          <SelectTrigger className="h-9 w-[150px] text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="last_updated">Sort: Last updated</SelectItem>
            <SelectItem value="ticker">Sort: Ticker</SelectItem>
            <SelectItem value="records">Sort: Records</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3.5 items-start">
        {/* Cached datasets table - dominant content */}
        <div className="xl:col-span-2 card-elevated overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="section-label">Cached Datasets</h2>
          </div>
          {filteredSorted.length === 0 ? (
            <EmptyState
              size="sm"
              icon={Database}
              title={cachedTickers.length === 0 ? "No cached data" : "No matches found"}
              description={cachedTickers.length === 0 ? "Fetch market data to start building your local cache for backtesting." : "Try a different search or filter."}
              action={cachedTickers.length === 0 ? <Button size="sm" className="gap-2" onClick={() => setFetchOpen(true)}><Download className="h-3.5 w-3.5" /> Fetch data</Button> : undefined}
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-secondary/20">
                      <th className="px-4 py-2 text-left label-caps">Ticker</th>
                      <th className="px-3 py-2 text-left label-caps">Interval</th>
                      <th className="px-3 py-2 text-left label-caps">Coverage</th>
                      <th className="px-3 py-2 text-right label-caps">Records</th>
                      <th className="px-3 py-2 text-left label-caps">Last Updated</th>
                      <th className="px-3 py-2 text-left label-caps">Freshness</th>
                      <th className="px-3 py-2 text-left label-caps">Quality</th>
                      <th className="px-4 py-2 text-center label-caps">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((item, index) => {
                      const key = `${item.ticker}-${item.interval}`;
                      const quality = sessionQuality[item.ticker];
                      return (
                        <tr key={`${key}-${item.start_date}-${index}`} className="border-b border-border/50 hover:bg-secondary/40 transition-colors">
                          <td className="px-4 py-2.5 font-semibold font-mono-numbers">{item.ticker}</td>
                          <td className="px-3 py-2.5"><IntervalBadge interval={item.interval} /></td>
                          <td className="px-3 py-2.5 font-mono-numbers text-xs text-muted-foreground whitespace-nowrap">
                            {formatDate(item.start_date)} - {formatDate(item.end_date)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono-numbers">{item.records.toLocaleString()}</td>
                          <td className="px-3 py-2.5 font-mono-numbers text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(item.last_updated)}</td>
                          <td className="px-3 py-2.5"><FreshnessBadge item={item} /></td>
                          <td className="px-3 py-2.5">
                            {quality != null ? (
                              <span className={cn("font-mono-numbers text-xs font-semibold", quality >= 0.9 ? "text-gain" : quality >= 0.7 ? "text-warning" : "text-loss")}>
                                {(quality * 100).toFixed(0)}%
                              </span>
                            ) : (
                              <span className="text-[10px] text-muted-foreground/85">Unavailable</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <button
                              onClick={() => handleRefetchRow(item)}
                              disabled={refetchingKey === key}
                              title={`Refetch ${item.ticker} (${INTERVAL_LABELS[item.interval] ?? item.interval})`}
                              aria-label={`Refetch ${item.ticker} (${INTERVAL_LABELS[item.interval] ?? item.interval})`}
                              className="text-muted-foreground hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed p-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                            >
                              {refetchingKey === key ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between px-4 py-2.5 border-t border-border/50 flex-wrap gap-2">
                <span className="text-[11px] text-muted-foreground">
                  Showing {pageClamped * perPage + 1} to {Math.min((pageClamped + 1) * perPage, filteredSorted.length)} of {filteredSorted.length} datasets
                </span>
                <div className="flex items-center gap-2">
                  <Select value={perPage.toString()} onValueChange={(v) => { setPerPage(Number(v)); setPage(0); }}>
                    <SelectTrigger className="h-7 w-[110px] text-[11px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="10">10 per page</SelectItem>
                      <SelectItem value="25">25 per page</SelectItem>
                      <SelectItem value="50">50 per page</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={pageClamped === 0} className="p-1 rounded border border-border/60 disabled:opacity-30 hover:bg-secondary/40">
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <span className="text-[11px] font-mono-numbers px-1.5">{pageClamped + 1} / {totalPages}</span>
                    <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={pageClamped >= totalPages - 1} className="p-1 rounded border border-border/60 disabled:opacity-30 hover:bg-secondary/40">
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right rail */}
        <div className="space-y-3.5">
          <div className="card-elevated p-4">
            <h2 className="section-label mb-3">Data Health</h2>
            {cachedTickers.length === 0 ? (
              <p className="text-xs text-muted-foreground/85">No cached data to evaluate yet.</p>
            ) : (
              <>
                <div className="h-1.5 rounded-full bg-secondary/60 overflow-hidden mb-2.5 flex">
                  <div className="h-full bg-gain" style={{ width: `${(freshCount / cachedTickers.length) * 100}%` }} />
                  <div className="h-full bg-warning" style={{ width: `${(expiredCount / cachedTickers.length) * 100}%` }} />
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-gain" /> Fresh (&le; 24h)</span>
                    <span className="font-mono-numbers font-semibold">{freshCount}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-warning" /> Expired (&gt; 24h)</span>
                    <span className="font-mono-numbers font-semibold">{expiredCount}</span>
                  </div>
                  {unknownFreshnessCount > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" /> Unavailable</span>
                      <span className="font-mono-numbers font-semibold">{unknownFreshnessCount}</span>
                    </div>
                  )}
                </div>
                <p className="text-[10px] text-muted-foreground/85 mt-2.5 pt-2.5 border-t border-border/40">Based on last-updated timestamp, matching the backend's 24-hour cache expiry.</p>
              </>
            )}
          </div>

          <div className="card-elevated p-4">
            <h2 className="section-label mb-3">Supported Intervals</h2>
            <div className="space-y-2.5">
              {Object.entries(INTERVAL_LABELS).map(([key, label]) => (
                <div key={key} className="flex items-center gap-2.5 text-xs">
                  <IntervalBadge interval={key} />
                  <div className="min-w-0">
                    <p className="text-foreground font-medium">{label}</p>
                    <p className="text-[10px] text-muted-foreground">{INTERVAL_DESCRIPTIONS[key]}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card-elevated p-4">
            <h2 className="section-label mb-3">Data Source</h2>
            <p className="text-sm font-semibold text-foreground">Yahoo Finance</p>
            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">Adjusted OHLCV via yfinance. Daily, weekly, and monthly bars only - no intraday data.</p>
            <div className="mt-3 pt-3 border-t border-border/40 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Backend</span>
              <StatusBadge label={isBackendOnline ? "Online" : "Offline"} tone={isBackendOnline ? "gain" : "loss"} dot pulse={isBackendOnline} />
            </div>
          </div>
        </div>
      </div>

      {/* Fetch Data modal - same fields, validation and behavior as before, just relocated */}
      <Dialog open={fetchOpen} onOpenChange={setFetchOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Fetch New Data</DialogTitle>
            <DialogDescription>Cache OHLCV data for backtesting and comparison.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs">Tickers (comma-separated, max 20)</Label>
              <Input value={tickers} onChange={(e) => setTickers(e.target.value.toUpperCase())} placeholder="AAPL, MSFT, GOOGL" className="mt-1 font-mono-numbers" />
              {tickerChips.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {tickerChips.slice(0, 20).map((t, i) => (
                    <span key={`${t}-${i}`} className="inline-flex items-center text-[10px] font-mono-numbers font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">{t}</span>
                  ))}
                  {tickerChips.length > 20 && <span className="text-[10px] text-loss font-medium px-1">+{tickerChips.length - 20} over limit</span>}
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Start Date</Label>
                <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-1" />
              </div>
              <div>
                <Label className="text-xs">End Date</Label>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="mt-1" />
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
            {isFetching && <Progress value={fetchProgress} className="h-1" />}
            <Button className="w-full gap-2 shadow-md shadow-primary/15" onClick={handleFetch} disabled={isFetching}>
              {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
              {isFetching ? "Fetching..." : "Fetch Data"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SummaryCell({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card-elevated p-3 flex items-center gap-2.5">
      <div className="rounded-lg bg-secondary/60 p-2 text-primary shrink-0">{icon}</div>
      <div className="min-w-0">
        <p className="label-caps truncate">{label}</p>
        <p className="text-lg font-bold font-mono-numbers text-foreground leading-tight truncate">{value}</p>
      </div>
    </div>
  );
}
