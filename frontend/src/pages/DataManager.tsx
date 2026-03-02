import { useState, useEffect } from "react";
import { useBacktestStore } from "@/stores/backtestStore";
import { getAvailableData, fetchData } from "@/services/api";
import { formatDate } from "@/utils/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { Loader2, Database, RefreshCw, Search } from "lucide-react";

export default function DataManager() {
  const { cachedTickers, setCachedTickers } = useBacktestStore();
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

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Data Manager</h1>
          <p className="text-sm text-muted-foreground mt-0.5">View and manage cached market data</p>
        </div>
        <Button variant="outline" size="sm" className="gap-2" onClick={loadCachedData} disabled={isLoading}>
          <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Fetch Section */}
      <div className="card-elevated p-5 space-y-4">
        <h2 className="text-sm font-semibold">Fetch New Data</h2>
        <div className="grid grid-cols-4 gap-4">
          <div className="col-span-2">
            <Label className="text-xs">Tickers (comma-separated, max 20)</Label>
            <Input value={tickers} onChange={(e) => setTickers(e.target.value.toUpperCase())} placeholder="AAPL, MSFT, GOOGL" className="mt-1 font-mono-numbers" />
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
        <div className="flex items-center gap-4">
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
          <Button className="gap-2 mt-5" onClick={handleFetch} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            {isFetching ? "Fetching..." : "Fetch Data"}
          </Button>
        </div>
        {isFetching && <Progress value={fetchProgress} className="h-1" />}
      </div>

      {/* Cached Data Table */}
      <div className="card-elevated">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">{filtered.length} Cached Datasets</h2>
          <div className="relative w-60">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by ticker..."
              className="pl-8 h-8 text-xs"
            />
          </div>
        </div>
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Database className="h-10 w-10 text-muted-foreground/50 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">
              {cachedTickers.length === 0 ? "No cached data" : "No matches found"}
            </p>
            <p className="text-xs text-muted-foreground/70 mt-1">
              {cachedTickers.length === 0 ? "Fetch some data to get started" : "Try a different search query"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Ticker</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Interval</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Start</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">End</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Records</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground">Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={`${item.ticker}-${item.interval}`} className="border-b border-border/50 hover:bg-secondary/30">
                    <td className="px-4 py-2 font-semibold font-mono-numbers">{item.ticker}</td>
                    <td className="px-4 py-2 text-muted-foreground">{item.interval}</td>
                    <td className="px-4 py-2 font-mono-numbers text-xs">{formatDate(item.start_date)}</td>
                    <td className="px-4 py-2 font-mono-numbers text-xs">{formatDate(item.end_date)}</td>
                    <td className="px-4 py-2 text-right font-mono-numbers">{item.records.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right font-mono-numbers text-xs text-muted-foreground">{formatDate(item.last_updated)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
