import type { StrategyParams, StrategyType } from "@/types";

/**
 * Single source of truth for everything the UI knows about a strategy: its
 * name, the editable parameters (with defaults and slider bounds), the
 * ranges the optimizer sweeps, and whether AlphaLive can accept an export.
 */

interface Range {
  min: number;
  max: number;
  step: number;
}

interface NumberParam extends Range {
  key: string;
  label: string;
  kind: "number";
  default: number;
  /** Grid-search range; omitted for parameters the optimizer never varies. */
  optimize?: Range;
}

interface BooleanParam {
  key: string;
  label: string;
  kind: "boolean";
  default: boolean;
}

type ParamSpec = (NumberParam | BooleanParam) & {
  /** Only shown while this boolean parameter is on. */
  shownWhen?: string;
};

interface StrategySpec {
  name: string;
  category: string;
  description: string;
  params: ParamSpec[];
  /**
   * Mirrors the 422 refusals of POST /api/strategies/export
   * (backend/alphalab/api/blueprints/backtest.py). The server enforces this;
   * the UI only previews it.
   */
  exportBlock?: { label: string; reason: string };
}

const num = (key: string, label: string, value: number, bounds: Range, optimize?: Range): ParamSpec => ({
  key,
  label,
  kind: "number",
  default: value,
  ...bounds,
  optimize,
});

const bool = (key: string, label: string, value: boolean): ParamSpec => ({ key, label, kind: "boolean", default: value });

const range = (min: number, max: number, step = 1): Range => ({ min, max, step });

export const STRATEGIES: Record<StrategyType, StrategySpec> = {
  ma_crossover: {
    name: "MA Crossover",
    category: "Trend following",
    description: "Trades when the short moving average crosses the long one.",
    params: [
      num("short_window", "Short window", 50, range(10, 100), range(20, 50, 10)),
      num("long_window", "Long window", 200, range(50, 300), range(100, 200, 50)),
      bool("volume_confirmation", "Volume confirmation", true),
      num("cooldown_days", "Cooldown days", 5, range(0, 30)),
    ],
  },
  rsi_mean_reversion: {
    name: "RSI Mean Reversion",
    category: "Mean reversion",
    description: "Buys oversold and sells overbought RSI readings.",
    params: [
      num("rsi_period", "RSI period", 14, range(7, 30), range(10, 20, 5)),
      num("oversold", "Oversold", 30, range(20, 40), range(20, 35, 5)),
      num("overbought", "Overbought", 70, range(60, 80), range(65, 80, 5)),
      bool("use_bb_confirmation", "Bollinger band confirmation", true),
      num("adx_threshold", "ADX threshold", 25, range(20, 40)),
    ],
  },
  rsi_simple: {
    name: "RSI Simple",
    category: "Mean reversion",
    description: "Plain RSI thresholds with no confirmation filters, for frequent trading.",
    params: [
      num("period", "RSI period", 14, range(5, 30), range(10, 20, 5)),
      num("oversold", "Oversold", 40, range(10, 40), range(30, 45, 5)),
      num("overbought", "Overbought", 60, range(60, 90), range(55, 70, 5)),
    ],
    exportBlock: {
      label: "Research only",
      reason: "AlphaLive has no matching strategy, so the export would be rejected. Use RSI Mean Reversion to deploy an RSI strategy.",
    },
  },
  momentum_breakout: {
    name: "Momentum Breakout",
    category: "Momentum",
    description: "Enters on price breakouts confirmed by a volume surge.",
    params: [
      num("lookback", "Lookback", 20, range(10, 60), range(10, 40, 10)),
      num("volume_surge_pct", "Volume surge %", 150, range(100, 300), range(120, 200, 20)),
      num("rsi_min", "Minimum RSI", 50, range(40, 60), range(40, 60, 5)),
      num("stop_loss_atr_mult", "Stop loss (× ATR)", 2, range(1, 5, 0.1)),
    ],
  },
  bollinger_breakout: {
    name: "Bollinger Breakout",
    category: "Volatility breakout",
    description: "Trades consecutive closes outside the Bollinger bands.",
    params: [
      num("bb_period", "Band period", 20, range(5, 100), range(10, 30, 10)),
      num("bb_std_dev", "Band width (σ)", 2, range(0.5, 4, 0.1), range(1.5, 3, 0.5)),
      num("confirmation_bars", "Confirmation bars", 2, range(1, 5), range(1, 3, 1)),
      bool("volume_filter", "Volume filter", true),
      { ...num("volume_threshold", "Volume threshold", 1.5, range(1, 3, 0.1)), shownWhen: "volume_filter" },
      num("cooldown_days", "Cooldown days", 3, range(0, 10)),
    ],
  },
  vwap_reversion: {
    name: "VWAP Reversion",
    category: "Mean reversion",
    description: "Trades deviations from the volume-weighted average price.",
    params: [
      num("vwap_period", "VWAP period", 20, range(5, 50), range(10, 30, 10)),
      num("deviation_threshold", "Deviation (σ)", 2, range(0.5, 5, 0.1), range(1, 3, 0.5)),
      num("rsi_period", "RSI period", 14, range(5, 30), range(10, 20, 5)),
      num("oversold", "Oversold", 30, range(10, 40)),
      num("overbought", "Overbought", 70, range(60, 90)),
      num("cooldown_days", "Cooldown days", 3, range(0, 10)),
    ],
    exportBlock: {
      label: "Intraday required",
      reason: "Needs 1-hour or 15-minute bars. AlphaLab only fetches daily, weekly and monthly data, so it can be backtested but not exported.",
    },
  },
  bollinger_rsi_combo: {
    name: "Bollinger RSI Combo",
    category: "Mean reversion",
    description: "Enters when price touches the lower band and RSI is oversold; exits at the middle band or overbought RSI.",
    params: [
      num("bb_period", "Band period", 20, range(5, 50), range(10, 30, 10)),
      num("bb_std", "Band width (σ)", 2, range(1, 4, 0.1)),
      num("rsi_period", "RSI period", 14, range(5, 30), range(10, 20, 5)),
      num("rsi_oversold", "RSI oversold", 45, range(20, 49), range(35, 49, 7)),
      num("rsi_overbought", "RSI overbought", 55, range(51, 80)),
      bool("exit_at_middle", "Exit at middle band", true),
    ],
  },
  trend_adaptive_rsi: {
    name: "Trend Adaptive RSI",
    category: "Adaptive trend",
    description: "RSI thresholds that shift with the trend regime: up, down or range.",
    params: [
      num("rsi_period", "RSI period", 14, range(5, 30), range(10, 20, 5)),
      num("trend_sma", "Trend SMA", 50, range(20, 200), range(30, 100, 10)),
      num("trend_lookback", "Trend lookback", 5, range(1, 20), range(3, 10, 2)),
      num("uptrend_buy", "Uptrend buy", 45, range(20, 49)),
      num("uptrend_sell", "Uptrend sell", 65, range(51, 80)),
      num("downtrend_buy", "Downtrend buy", 35, range(10, 49)),
      num("downtrend_sell", "Downtrend sell", 55, range(51, 70)),
      num("range_buy", "Range buy", 35, range(20, 49)),
      num("range_sell", "Range sell", 65, range(51, 80)),
    ],
  },
  greenblatt_weekly: {
    name: "Greenblatt Weekly",
    category: "Value factor",
    description: "Magic Formula screen on weekly bars with a golden-cross/RSI entry, a 52-week minimum hold and a trailing stop.",
    // fast_sma/slow_sma must be one of FeatureEngineer's precomputed SMA
    // windows (10/20/50/100/200, see docs/STRATEGY_SCHEMA.md); the backend
    // validates that, the slider step only keeps the common cases reachable.
    params: [
      num("fast_sma", "Fast SMA (weeks)", 10, range(10, 100, 10), range(10, 20, 10)),
      num("slow_sma", "Slow SMA (weeks)", 50, range(20, 200, 10), range(50, 100, 50)),
      num("rsi_period", "RSI period", 14, range(5, 30)),
      num("rsi_oversold", "RSI oversold", 35, range(20, 49)),
      num("rsi_overbought", "RSI overbought", 65, range(51, 80)),
      num("min_hold_bars", "Minimum hold (weeks)", 52, range(4, 104), range(26, 78, 26)),
      num("trailing_stop_pct", "Trailing stop (fraction)", 0.2, range(0.05, 0.5, 0.05)),
      bool("exit_rsi_overbought", "Exit on overbought RSI", false),
      bool("exit_sma_cross", "Exit on SMA death cross", false),
    ],
  },
};

export const STRATEGY_TYPES = Object.keys(STRATEGIES) as StrategyType[];

function defaultParams(strategy: StrategyType): StrategyParams {
  return Object.fromEntries(STRATEGIES[strategy].params.map((p) => [p.key, p.default])) as unknown as StrategyParams;
}

export const DEFAULT_PARAMS = Object.fromEntries(STRATEGY_TYPES.map((s) => [s, defaultParams(s)])) as Record<
  StrategyType,
  StrategyParams
>;

export function optimizeRanges(strategy: StrategyType): Record<string, Range> {
  return Object.fromEntries(
    STRATEGIES[strategy].params.flatMap((p) => (p.kind === "number" && p.optimize ? [[p.key, p.optimize]] : [])),
  );
}

export function paramLabel(strategy: StrategyType, key: string): string {
  return STRATEGIES[strategy].params.find((p) => p.key === key)?.label ?? key;
}

/** "Short window 50 · Long window 200 · Cooldown days 5": the first three numeric parameters. */
export function paramSummary(strategy: StrategyType, params: StrategyParams): string {
  const values = params as unknown as Record<string, number | boolean>;
  return STRATEGIES[strategy].params
    .filter((p) => p.kind === "number")
    .slice(0, 3)
    .map((p) => `${p.label} ${values[p.key]}`)
    .join(" · ");
}

/** Looks up a strategy by id, accepting the API's own casing too ("MA_Crossover"). */
export function strategySpec(id: string): StrategySpec | undefined {
  return STRATEGIES[id.toLowerCase() as StrategyType];
}

export function strategyName(id: string): string {
  return strategySpec(id)?.name ?? id;
}
