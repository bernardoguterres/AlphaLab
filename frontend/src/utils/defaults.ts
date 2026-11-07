import type { PositionSizing } from "@/types";

/**
 * Form defaults shared by Backtest, Compare, Batch, Data and the Settings
 * reference page. Risk defaults are DEFAULT_RISK_SETTINGS in @/types, which
 * mirrors the backend's RiskSettings model (a backend test keeps them equal).
 */
export const DEFAULT_TICKER = "AAPL";
export const DEFAULT_START = "2020-01-01";
export const DEFAULT_END = "2024-12-31";
export const DEFAULT_CAPITAL = 100_000;
export const DEFAULT_SIZING: PositionSizing = "equal_weight";
/** Backtest and Compare halt new entries after a 10% drawdown unless told not to. */
export const DEFAULT_DRAWDOWN_HALT = true;

export const SIZINGS: { value: PositionSizing; label: string }[] = [
  { value: "equal_weight", label: "Equal weight" },
  { value: "volatility_weighted", label: "Volatility weighted" },
];

export const INTERVALS = [
  { value: "1d", label: "Daily" },
  { value: "1wk", label: "Weekly" },
  { value: "1mo", label: "Monthly" },
] as const;
