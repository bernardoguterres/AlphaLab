import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { CachedTicker } from "@/types";
import { ApiOfflineNotice } from "@/components/layout/ApiOfflineNotice";
import { Page } from "@/components/layout/Page";
import { DateRangeFields, IntervalSelect } from "@/components/forms/RunFields";
import { Button } from "@/components/ui/button";
import { Table, Td, Th } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Section } from "@/components/ui/section";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { errorMessage, fetchData } from "@/services/api";
import { useBacktestStore } from "@/stores/backtestStore";
import { CACHE_EXPIRY_HOURS, cacheAgeMs, formatAge, freshness, type Freshness } from "@/utils/cache";
import { DEFAULT_END, DEFAULT_START, INTERVALS } from "@/utils/defaults";
import { formatDate, qualityColor } from "@/utils/formatters";

const MAX_TICKERS = 20;
const PAGE_SIZE = 25;

type SortKey = "updated" | "ticker" | "records";

const SORTS: Record<SortKey, (a: CachedTicker, b: CachedTicker) => number> = {
  updated: (a, b) => new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime(),
  ticker: (a, b) => a.ticker.localeCompare(b.ticker),
  records: (a, b) => b.records - a.records,
};

const intervalLabel = (value: string) => INTERVALS.find((i) => i.value === value)?.label ?? value;
const parseTickers = (text: string) => [...new Set(text.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean))];

export default function DataManager() {
  const { cachedTickers, refreshCachedTickers } = useBacktestStore();
  // Quality scores only come back from a fetch; the cache listing doesn't carry them.
  const [quality, setQuality] = useState<Record<string, number>>({});

  useEffect(() => {
    refreshCachedTickers();
  }, [refreshCachedTickers]);

  const recordQuality = (data: Record<string, { quality_score: number }>) =>
    setQuality((q) => ({ ...q, ...Object.fromEntries(Object.entries(data).map(([t, d]) => [t, d.quality_score])) }));

  /** Fetches and caches, reports per-ticker errors, then reloads the listing. */
  const fetchAndCache = async (tickers: string[], start: string, end: string, interval: string) => {
    try {
      const response = await fetchData(tickers, start, end, interval);
      const fetched = Object.keys(response.data ?? {});
      if (fetched.length) {
        recordQuality(response.data);
        toast.success(`Cached ${fetched.join(", ")}`);
      }
      response.errors?.forEach((e) => toast.error(e));
      await refreshCachedTickers();
    } catch (error) {
      toast.error(errorMessage(error, "Fetching data failed"));
    }
  };

  return (
    <Page
      title="Data"
      actions={
        <Button variant="outline" onClick={() => refreshCachedTickers()}>
          Reload list
        </Button>
      }
    >
      <ApiOfflineNotice />
      <FetchForm onFetch={fetchAndCache} />
      <DatasetTable items={cachedTickers} quality={quality} onRefresh={(c) => fetchAndCache([c.ticker], c.start_date, c.end_date, c.interval)} />
      <p className="text-2xs text-muted-foreground">
        Adjusted OHLCV from Yahoo Finance via yfinance. Daily, weekly and monthly bars only; no intraday data. Cached datasets
        expire after {CACHE_EXPIRY_HOURS} hours.
      </p>
    </Page>
  );
}

type FetchHandler = (tickers: string[], start: string, end: string, interval: string) => Promise<void>;

function FetchForm({ onFetch }: { onFetch: FetchHandler }) {
  const [text, setText] = useState("AAPL, MSFT, GOOGL");
  const [start, setStart] = useState(DEFAULT_START);
  const [end, setEnd] = useState(DEFAULT_END);
  const [barSize, setBarSize] = useState("1d");
  const [busy, setBusy] = useState(false);
  const tickers = parseTickers(text);
  const tooMany = tickers.length > MAX_TICKERS;

  const submit = async () => {
    setBusy(true);
    await onFetch(tickers, start, end, barSize);
    setBusy(false);
  };

  return (
    <Section title="Fetch market data">
      <div className="grid max-w-5xl grid-cols-2 items-end gap-4 md:grid-cols-6">
        <div className="col-span-2">
          <Field
            label={`Tickers, comma-separated (${tickers.length}/${MAX_TICKERS})`}
            htmlFor="fetch-tickers"
            hint={tooMany ? <span className="text-loss">At most {MAX_TICKERS} per fetch.</span> : undefined}
          >
            <Input id="fetch-tickers" className="num uppercase" value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
        </div>
        <DateRangeFields start={start} end={end} onStartChange={setStart} onEndChange={setEnd} />
        <Field label="Interval" htmlFor="fetch-interval">
          <IntervalSelect id="fetch-interval" value={barSize} onChange={setBarSize} />
        </Field>
        <Button onClick={submit} disabled={busy || tickers.length === 0 || tooMany}>
          {busy ? "Fetching…" : "Fetch"}
        </Button>
      </div>
    </Section>
  );
}

interface DatasetTableProps {
  items: CachedTicker[];
  quality: Record<string, number>;
  onRefresh: (item: CachedTicker) => Promise<void>;
}

function DatasetTable({ items, quality, onRefresh }: DatasetTableProps) {
  const [search, setSearch] = useState("");
  const [barSize, setBarSize] = useState("all");
  const [fresh, setFresh] = useState<"all" | Freshness>("all");
  const [sort, setSort] = useState<SortKey>("updated");
  const [page, setPage] = useState(0);
  const [refreshing, setRefreshing] = useState<string | null>(null);

  const rows = useMemo(
    () =>
      items
        .filter((c) => c.ticker.toLowerCase().includes(search.toLowerCase()))
        .filter((c) => barSize === "all" || c.interval === barSize)
        .filter((c) => fresh === "all" || freshness(c) === fresh)
        .sort(SORTS[sort]),
    [items, search, barSize, fresh, sort],
  );

  useEffect(() => setPage(0), [search, barSize, fresh]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const visible = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  const expired = items.filter((c) => freshness(c) === "expired").length;

  const refresh = async (item: CachedTicker) => {
    setRefreshing(item.key);
    await onRefresh(item);
    setRefreshing(null);
  };

  return (
    <Section
      title="Cached datasets"
      aside={
        <span className="num">
          {items.length} datasets · {new Set(items.map((c) => c.ticker)).size} tickers ·{" "}
          {items.reduce((sum, c) => sum + c.records, 0).toLocaleString()} bars
          {expired > 0 && <span className="text-warning"> · {expired} expired</span>}
        </span>
      }
    >
      <div className="mb-3 flex flex-wrap gap-2">
        <Input placeholder="Search ticker" aria-label="Search ticker" className="h-8 w-44" value={search} onChange={(e) => setSearch(e.target.value)} />
        <FilterSelect label="Interval" value={barSize} onChange={setBarSize} options={[{ value: "all", label: "All intervals" }, ...INTERVALS]} />
        <FilterSelect
          label="Freshness"
          value={fresh}
          onChange={(v) => setFresh(v as "all" | Freshness)}
          options={[
            { value: "all", label: "Any age" },
            { value: "fresh", label: "Fresh" },
            { value: "expired", label: "Expired" },
          ]}
        />
        <FilterSelect
          label="Sort"
          value={sort}
          onChange={(v) => setSort(v as SortKey)}
          options={[
            { value: "updated", label: "Newest first" },
            { value: "ticker", label: "Ticker A–Z" },
            { value: "records", label: "Most bars" },
          ]}
        />
      </div>

      {visible.length === 0 ? (
        <EmptyState
          title={items.length === 0 ? "Nothing cached yet" : "No datasets match these filters"}
          description={items.length === 0 ? "Fetch market data above to build the local cache." : undefined}
        />
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Ticker</Th>
              <Th>Interval</Th>
              <Th>Coverage</Th>
              <Th align="right">Bars</Th>
              <Th>Updated</Th>
              <Th align="right">Quality</Th>
              <Th align="right">
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {visible.map((c) => {
              const age = cacheAgeMs(c);
              const score = quality[c.ticker];
              return (
                <tr key={c.key}>
                  <Td num>{c.ticker}</Td>
                  <Td className="text-muted-foreground">{intervalLabel(c.interval)}</Td>
                  <Td num className="text-muted-foreground">
                    {formatDate(c.start_date)} – {formatDate(c.end_date)}
                  </Td>
                  <Td num align="right">
                    {c.records.toLocaleString()}
                  </Td>
                  <Td className={freshness(c) === "expired" ? "text-warning" : "text-muted-foreground"}>{age === null ? "-" : formatAge(age)}</Td>
                  <Td num align="right" className={score === undefined ? "text-muted-foreground" : qualityColor(score)}>
                    {score === undefined ? "-" : `${(score * 100).toFixed(0)}%`}
                  </Td>
                  <Td align="right">
                    <Button variant="link" size="sm" disabled={refreshing === c.key} onClick={() => refresh(c)}>
                      {refreshing === c.key ? "Refreshing…" : "Refresh"}
                    </Button>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      )}

      {pages > 1 && (
        <nav aria-label="Dataset pages" className="mt-3 flex items-center justify-end gap-3 text-2xs text-muted-foreground">
          <Button variant="ghost" size="sm" disabled={current === 0} onClick={() => setPage(current - 1)}>
            Previous
          </Button>
          <span className="num">
            {current + 1} / {pages}
          </span>
          <Button variant="ghost" size="sm" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            Next
          </Button>
        </nav>
      )}
    </Section>
  );
}

interface FilterSelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: string }[];
}

function FilterSelect({ label, value, onChange, options }: FilterSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label} className="h-8 w-36 text-[13px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
