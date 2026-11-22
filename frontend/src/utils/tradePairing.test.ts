import { describe, it, expect } from "vitest";
import { pairTradesFIFO } from "./tradePairing";
import type { RawOrder } from "@/types";

// Regression test: BacktestResult.trades was previously typed as Trade[]
// (entry_date/exit_date/action/entry_price/exit_price/pnl/pnl_pct) and
// passed straight into TradeTable, but the backend actually sends a raw
// per-order ledger (Portfolio._log_trade()/Order.to_dict()) with
// ticker/side/filled_price/commission/timestamp/status - none of the
// fields TradeTable expected. Every cell in the Trade Table silently
// rendered "-" for every backtest. pairTradesFIFO() mirrors the backend's
// own FIFO buy/sell matching in metrics.py's _trade_metrics() to derive
// the paired Trade shape the table actually needs.

function order(overrides: Partial<RawOrder>): RawOrder {
  return {
    ticker: "AAPL",
    side: "buy",
    shares: 10,
    order_type: "market",
    status: "filled",
    filled_price: 100,
    commission: 0,
    slippage: 0.05,
    timestamp: "2020-01-01",
    filled_timestamp: "2020-01-01",
    reason: "",
    portfolio_cash: 90000,
    ...overrides,
  };
}

describe("pairTradesFIFO", () => {
  it("pairs a buy with its matching sell into one round-trip trade", () => {
    const orders: RawOrder[] = [
      order({ side: "buy", filled_price: 100, filled_timestamp: "2020-01-01", shares: 10 }),
      order({ side: "sell", filled_price: 110, filled_timestamp: "2020-02-01", shares: 10 }),
    ];

    const trades = pairTradesFIFO(orders);

    expect(trades).toHaveLength(1);
    expect(trades[0]).toMatchObject({
      entry_date: "2020-01-01",
      exit_date: "2020-02-01",
      shares: 10,
      entry_price: 100,
      exit_price: 110,
      pnl: 100, // (110-100)*10
      pnl_pct: 10, // (110-100)/100 * 100
    });
  });

  it("subtracts commission from both legs, matching the backend formula", () => {
    const orders: RawOrder[] = [
      order({ side: "buy", filled_price: 100, shares: 10, commission: 1.5 }),
      order({ side: "sell", filled_price: 110, shares: 10, commission: 1.5 }),
    ];

    const trades = pairTradesFIFO(orders);
    // (110-100)*10 - (1.5+1.5) = 97
    expect(trades[0].pnl).toBe(97);
  });

  it("ignores non-filled orders", () => {
    const orders: RawOrder[] = [
      order({ side: "buy", status: "rejected" }),
      order({ side: "sell", status: "filled" }), // no matching buy in queue
    ];
    expect(pairTradesFIFO(orders)).toHaveLength(0);
  });

  it("matches multiple round trips in FIFO order", () => {
    const orders: RawOrder[] = [
      order({ side: "buy", filled_price: 100, filled_timestamp: "2020-01-01" }),
      order({ side: "sell", filled_price: 105, filled_timestamp: "2020-01-15" }),
      order({ side: "buy", filled_price: 108, filled_timestamp: "2020-02-01" }),
      order({ side: "sell", filled_price: 112, filled_timestamp: "2020-02-15" }),
    ];

    const trades = pairTradesFIFO(orders);

    expect(trades).toHaveLength(2);
    expect(trades[0].entry_price).toBe(100);
    expect(trades[0].exit_price).toBe(105);
    expect(trades[1].entry_price).toBe(108);
    expect(trades[1].exit_price).toBe(112);
  });

  it("returns no trades for a dangling buy with no sell yet", () => {
    const orders: RawOrder[] = [order({ side: "buy" })];
    expect(pairTradesFIFO(orders)).toHaveLength(0);
  });
});

// B12 (Nov 2026 audit): one-buy-one-sell pairing dropped add-on lots and
// mispaired them with later sells. These mirror metrics.py round_trips().
describe("pairTradesFIFO round trips (quantity FIFO, like the backend)", () => {
  it("keeps an add-on buy inside the round trip", () => {
    const trades = pairTradesFIFO([
      order({ side: "buy", shares: 10, filled_price: 100, filled_timestamp: "2020-01-01" }),
      order({ side: "buy", shares: 5, filled_price: 110, filled_timestamp: "2020-01-05" }),
      order({ side: "sell", shares: 15, filled_price: 120, filled_timestamp: "2020-02-01" }),
    ]);
    expect(trades).toHaveLength(1);
    expect(trades[0].pnl).toBeCloseTo(250); // 10*20 + 5*10
    expect(trades[0].shares).toBe(15);
    expect(trades[0].entry_price).toBeCloseTo(1550 / 15);
    expect(trades[0].exit_price).toBe(120);
    expect(trades[0].entry_date).toBe("2020-01-01");
    expect(trades[0].exit_date).toBe("2020-02-01");
  });

  it("closes the trip only when the position is flat after partial sells", () => {
    const trades = pairTradesFIFO([
      order({ side: "buy", shares: 10, filled_price: 100 }),
      order({ side: "sell", shares: 4, filled_price: 110, filled_timestamp: "2020-01-10" }),
      order({ side: "sell", shares: 6, filled_price: 90, filled_timestamp: "2020-01-20" }),
    ]);
    expect(trades).toHaveLength(1);
    expect(trades[0].pnl).toBeCloseTo(4 * 10 + 6 * -10);
    expect(trades[0].exit_date).toBe("2020-01-20");
  });

  it("nets the commission of every order in the round trip", () => {
    const trades = pairTradesFIFO([
      order({ side: "buy", shares: 10, filled_price: 100, commission: 1 }),
      order({ side: "buy", shares: 10, filled_price: 100, commission: 1 }),
      order({ side: "sell", shares: 20, filled_price: 100, commission: 1 }),
    ]);
    expect(trades[0].pnl).toBeCloseTo(-3);
  });

  it("does not mix lots across tickers", () => {
    const trades = pairTradesFIFO([
      order({ ticker: "AAPL", side: "buy", shares: 10, filled_price: 100 }),
      order({ ticker: "MSFT", side: "buy", shares: 10, filled_price: 300 }),
      order({ ticker: "AAPL", side: "sell", shares: 10, filled_price: 110 }),
      order({ ticker: "MSFT", side: "sell", shares: 10, filled_price: 290 }),
    ]);
    expect(trades.map((t) => t.pnl)).toEqual([100, -100]);
  });
});
