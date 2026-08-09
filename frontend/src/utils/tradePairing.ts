import type { RawOrder, Trade } from "@/types";

// Mirrors alphalab/backtest/metrics.py's PerformanceMetrics._trade_metrics()
// FIFO buy/sell matching exactly, so the Trade Table's per-trade P&L stays
// consistent with the backend-computed avg_win/avg_loss/best_trade/
// worst_trade shown in the Trades metrics tab. Single-ticker only (matches
// BacktestEngine, which runs one ticker per backtest) - does not track
// partial-fill remainders back into the queue, same simplification the
// backend's own version makes.
export function pairTradesFIFO(orders: RawOrder[]): Trade[] {
  const filled = orders.filter((o) => o.status === "filled");
  const trades: Trade[] = [];
  const buyQueue: RawOrder[] = [];

  for (const order of filled) {
    if (order.side === "buy") {
      buyQueue.push(order);
      continue;
    }
    if (order.side === "sell" && buyQueue.length > 0) {
      const buy = buyQueue.shift()!;
      const buyPrice = buy.filled_price ?? 0;
      const sellPrice = order.filled_price ?? 0;
      const shares = Math.min(buy.shares, order.shares);
      const pnl = (sellPrice - buyPrice) * shares - (buy.commission + order.commission);
      const pnlPct = buyPrice !== 0 ? ((sellPrice - buyPrice) / buyPrice) * 100 : 0;

      trades.push({
        entry_date: buy.filled_timestamp ?? buy.timestamp ?? "",
        exit_date: order.filled_timestamp ?? order.timestamp ?? "",
        action: "BUY",
        shares,
        entry_price: buyPrice,
        exit_price: sellPrice,
        pnl,
        pnl_pct: pnlPct,
      });
    }
  }

  return trades;
}
