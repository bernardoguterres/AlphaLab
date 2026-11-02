import { useEffect, useState } from "react";
import type { Trade } from "@/types";
import { Table, Td, Th } from "@/components/ui/data-table";
import { cn } from "@/lib/utils";
import { formatCurrency, formatDate, formatPercent, pnlColor } from "@/utils/formatters";

const PER_PAGE = 15;
const DAY_MS = 86_400_000;

type SortKey = "entry_date" | "pnl" | "pnl_pct";

function holdingDays(trade: Trade): number {
  return Math.round((new Date(trade.exit_date).getTime() - new Date(trade.entry_date).getTime()) / DAY_MS);
}

export function TradeTable({ trades }: { trades: Trade[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("entry_date");
  const [descending, setDescending] = useState(true);
  const [page, setPage] = useState(0);

  // A new result can have fewer pages than the one we were paging through.
  useEffect(() => setPage(0), [trades]);

  if (trades.length === 0) {
    return <p className="py-8 text-[13px] text-muted-foreground">No completed round trips in this window.</p>;
  }

  const value = (t: Trade) => (sortKey === "entry_date" ? new Date(t.entry_date).getTime() : t[sortKey]);
  const sorted = [...trades].sort((a, b) => (descending ? value(b) - value(a) : value(a) - value(b)));
  const rows = sorted.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
  const totalPages = Math.ceil(trades.length / PER_PAGE);

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setDescending((d) => !d);
    else {
      setSortKey(key);
      setDescending(true);
    }
  };

  const sortable = (key: SortKey, label: string, align: "left" | "right" = "right") => (
    <Th align={align} aria-sort={sortKey === key ? (descending ? "descending" : "ascending") : undefined}>
      <button type="button" onClick={() => sortBy(key)} className="hover:text-foreground">
        {label}
        {sortKey === key && (descending ? " ↓" : " ↑")}
      </button>
    </Th>
  );

  return (
    <div>
      <Table>
        <thead>
          <tr>
            {sortable("entry_date", "Entry", "left")}
            <Th>Exit</Th>
            <Th align="right">Days</Th>
            <Th align="right">Shares</Th>
            <Th align="right">Entry price</Th>
            <Th align="right">Exit price</Th>
            {sortable("pnl", "P&L")}
            {sortable("pnl_pct", "Return")}
          </tr>
        </thead>
        <tbody>
          {rows.map((trade) => (
            <tr key={`${trade.entry_date}-${trade.exit_date}`}>
              <Td num>{formatDate(trade.entry_date)}</Td>
              <Td num>{formatDate(trade.exit_date)}</Td>
              <Td num align="right" className="text-muted-foreground">
                {holdingDays(trade)}
              </Td>
              <Td num align="right">
                {trade.shares}
              </Td>
              <Td num align="right">
                {formatCurrency(trade.entry_price)}
              </Td>
              <Td num align="right">
                {formatCurrency(trade.exit_price)}
              </Td>
              <Td num align="right" className={pnlColor(trade.pnl)}>
                {formatCurrency(trade.pnl)}
              </Td>
              <Td num align="right" className={pnlColor(trade.pnl_pct)}>
                {formatPercent(trade.pnl_pct)}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {totalPages > 1 && (
        <nav aria-label="Trade pages" className="mt-3 flex items-center justify-between text-2xs text-muted-foreground">
          <span>{trades.length} round trips</span>
          <div className="flex gap-0.5">
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                type="button"
                aria-current={page === i ? "page" : undefined}
                onClick={() => setPage(i)}
                className={cn("num rounded-sm px-2 py-1", page === i ? "bg-muted text-foreground" : "hover:text-foreground")}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </nav>
      )}
    </div>
  );
}
