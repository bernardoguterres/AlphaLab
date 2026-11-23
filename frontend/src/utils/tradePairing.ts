import type { RawOrder, Trade } from "@/types";

// Mirrors alphalab/backtest/metrics.py's PerformanceMetrics.round_trips()
// exactly, so the Trade Table's per-trade P&L matches the backend's
// avg_win/avg_loss/best_trade/worst_trade: per ticker, FIFO by quantity,
// one Trade per completed round trip (flat -> long -> flat). Add-on buys and
// partial sells stay inside the round trip and every order's commission is
// netted. The previous version paired one buy order with one sell order,
// dropping add-on lots and pairing them with later sells as stale entries
// (rsi_simple: table sum -$27,319 vs backend +$1,151).
interface OpenTrip {
  lots: [number, number][]; // [remaining qty, price]
  pnl: number;
  entryDate: string;
  boughtQty: number;
  boughtValue: number;
  soldQty: number;
  soldValue: number;
}

const EPS = 1e-9;

export function pairTradesFIFO(orders: RawOrder[]): Trade[] {
  const trades: Trade[] = [];
  const trips = new Map<string, OpenTrip>();

  for (const order of orders) {
    if (order.status !== "filled") continue;
    const ticker = order.ticker ?? "";
    const qty = Number(order.shares) || 0;
    const price = order.filled_price ?? 0;
    const date = order.filled_timestamp ?? order.timestamp ?? "";
    let trip = trips.get(ticker);

    if (order.side === "buy") {
      if (!trip) {
        trip = { lots: [], pnl: 0, entryDate: date, boughtQty: 0, boughtValue: 0, soldQty: 0, soldValue: 0 };
        trips.set(ticker, trip);
      }
      trip.pnl -= order.commission ?? 0;
      trip.lots.push([qty, price]);
      trip.boughtQty += qty;
      trip.boughtValue += qty * price;
      continue;
    }

    if (order.side !== "sell" || !trip || trip.lots.length === 0) continue;
    trip.pnl -= order.commission ?? 0;
    let remaining = qty;
    while (remaining > EPS && trip.lots.length > 0) {
      const lot = trip.lots[0];
      const take = Math.min(remaining, lot[0]);
      trip.pnl += (price - lot[1]) * take;
      trip.soldQty += take;
      trip.soldValue += take * price;
      lot[0] -= take;
      remaining -= take;
      if (lot[0] <= EPS) trip.lots.shift();
    }

    if (trip.lots.length === 0) {
      const entryPrice = trip.boughtQty > 0 ? trip.boughtValue / trip.boughtQty : 0;
      const exitPrice = trip.soldQty > 0 ? trip.soldValue / trip.soldQty : 0;
      trades.push({
        entry_date: trip.entryDate,
        exit_date: date,
        shares: trip.boughtQty,
        entry_price: entryPrice,
        exit_price: exitPrice,
        pnl: trip.pnl,
        pnl_pct: entryPrice !== 0 ? ((exitPrice - entryPrice) / entryPrice) * 100 : 0,
      });
      trips.delete(ticker);
    }
  }

  return trades;
}
