/** Form defaults shared by Backtest, Compare, Batch, Data and the Settings reference page. */
export const DEFAULT_TICKER = "AAPL";
export const DEFAULT_START = "2020-01-01";
export const DEFAULT_END = "2024-12-31";
export const DEFAULT_CAPITAL = 100_000;

export const INTERVALS = [
  { value: "1d", label: "Daily" },
  { value: "1wk", label: "Weekly" },
  { value: "1mo", label: "Monthly" },
] as const;
