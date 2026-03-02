import { useState } from "react";
import type { Trade } from "@/types";
import { formatCurrency, formatDate, pnlColor } from "@/utils/formatters";
import { cn } from "@/lib/utils";
import { ArrowUpDown } from "lucide-react";

interface TradeTableProps {
  trades: Trade[];
}

type SortKey = "entry_date" | "pnl" | "pnl_pct";

export function TradeTable({ trades }: TradeTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("entry_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const perPage = 15;

  const sorted = [...trades].sort((a, b) => {
    const mul = sortDir === "asc" ? 1 : -1;
    if (sortKey === "entry_date") return mul * (new Date(a.entry_date).getTime() - new Date(b.entry_date).getTime());
    return mul * (a[sortKey] - b[sortKey]);
  });

  const paged = sorted.slice(page * perPage, (page + 1) * perPage);
  const totalPages = Math.ceil(trades.length / perPage);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
  };

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/50">
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground cursor-pointer" onClick={() => toggleSort("entry_date")}>
                <span className="flex items-center gap-1">Entry <ArrowUpDown className="h-3 w-3" /></span>
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Exit</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Type</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Shares</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Entry $</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Exit $</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground cursor-pointer" onClick={() => toggleSort("pnl")}>
                <span className="flex items-center justify-end gap-1">P&L <ArrowUpDown className="h-3 w-3" /></span>
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground cursor-pointer" onClick={() => toggleSort("pnl_pct")}>
                <span className="flex items-center justify-end gap-1">P&L % <ArrowUpDown className="h-3 w-3" /></span>
              </th>
            </tr>
          </thead>
          <tbody>
            {paged.map((trade, i) => (
              <tr key={i} className={cn("border-b border-border/50 hover:bg-secondary/30", trade.pnl >= 0 ? "bg-gain/5" : "bg-loss/5")}>
                <td className="px-3 py-2 font-mono-numbers text-xs">{formatDate(trade.entry_date)}</td>
                <td className="px-3 py-2 font-mono-numbers text-xs">{formatDate(trade.exit_date)}</td>
                <td className="px-3 py-2">
                  <span className={cn("text-xs font-semibold px-1.5 py-0.5 rounded", trade.action === "BUY" ? "bg-gain/20 text-gain" : "bg-loss/20 text-loss")}>
                    {trade.action}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono-numbers text-xs">{trade.shares}</td>
                <td className="px-3 py-2 text-right font-mono-numbers text-xs">{formatCurrency(trade.entry_price)}</td>
                <td className="px-3 py-2 text-right font-mono-numbers text-xs">{formatCurrency(trade.exit_price)}</td>
                <td className={cn("px-3 py-2 text-right font-mono-numbers text-xs font-semibold", pnlColor(trade.pnl))}>{formatCurrency(trade.pnl)}</td>
                <td className={cn("px-3 py-2 text-right font-mono-numbers text-xs font-semibold", pnlColor(trade.pnl_pct))}>{trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{trades.length} trades total</span>
          <div className="flex gap-1">
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                onClick={() => setPage(i)}
                className={cn("px-2 py-1 rounded", page === i ? "bg-primary text-primary-foreground" : "hover:bg-secondary")}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
