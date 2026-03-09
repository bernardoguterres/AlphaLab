/**
 * Strategy Export Schema v1.0 - TypeScript Types
 *
 * Single source of truth for strategy configuration exchange between
 * AlphaLab (backtesting) and AlphaLive (live execution).
 *
 * Mirrors backend/strategy_schema.py Pydantic models exactly.
 */

// ============================================================================
// Strategy Parameters (Per-Strategy)
// ============================================================================

export interface MACrossoverParams {
  /** Short MA period (2-500) */
  short_window: number;
  /** Long MA period (3-500, must be > short_window) */
  long_window: number;
  /** Require volume > avg for signal */
  volume_confirmation: boolean;
  /** Volume MA period (5-100, default: 20) */
  volume_avg_period?: number;
  /** Min % separation before cross (0.0-10.0, default: 0.0) */
  min_separation_pct?: number;
  /** Min days between signals (0-100, default: 5) */
  cooldown_days?: number;
}

export interface RSIMeanReversionParams {
  /** RSI calculation period (2-100) */
  rsi_period: number;
  /** RSI buy threshold (1-49) */
  oversold: number;
  /** RSI sell threshold (51-99, must be > oversold) */
  overbought: number;
  /** Require price near BB for entry */
  use_bb_confirmation: boolean;
  /** Bollinger Band period (5-100, default: 20) */
  bb_period?: number;
  /** BB standard deviations (1.0-4.0, default: 2.0) */
  bb_std?: number;
  /** Filter choppy markets (default: false) */
  use_adx_filter?: boolean;
  /** Min ADX for signal (10-50, default: 25) */
  adx_threshold?: number;
  /** Stop-loss distance (× ATR, 0.5-10.0) */
  stop_loss_atr_mult: number;
  /** Max position holding period (1-365 days) */
  max_holding_days: number;
}

export interface MomentumBreakoutParams {
  /** Breakout lookback period (5-200 bars) */
  lookback: number;
  /** Required volume surge (100-1000% of avg) */
  volume_surge_pct: number;
  /** Min RSI for confirmation (30-80) */
  rsi_min: number;
  /** Initial stop-loss (× ATR, 0.5-10.0) */
  stop_loss_atr_mult: number;
  /** Trailing stop distance (× ATR, 0.5-10.0) */
  trailing_stop_atr_mult: number;
  /** Min days between signals (0-100, default: 3) */
  cooldown_days?: number;
}

export interface BollingerBreakoutParams {
  /** Bollinger Band period (5-100) */
  bb_period: number;
  /** BB standard deviations (1.0-4.0) */
  bb_std: number;
  /** Volume surge threshold (100-1000%) */
  volume_surge_pct: number;
  /** Min RSI for long breakout (30-70) */
  rsi_min: number;
  /** Max RSI for long breakout (50-90, must be > rsi_min) */
  rsi_max: number;
  /** Stop-loss distance (× ATR, 0.5-10.0) */
  stop_loss_atr_mult: number;
  /** Take profit target (× ATR, 1.0-20.0) */
  take_profit_atr_mult: number;
  /** Min days between signals (0-100, default: 3) */
  cooldown_days?: number;
}

export interface VWAPReversionParams {
  /** VWAP reset period */
  vwap_period: "daily" | "weekly" | "intraday";
  /** Min deviation from VWAP (0.5-5.0 std dev) */
  deviation_threshold: number;
  /** Min volume (50-200% of avg) */
  volume_min_pct: number;
  /** RSI oversold threshold (10-40) */
  rsi_oversold: number;
  /** RSI overbought threshold (60-90, must be > rsi_oversold) */
  rsi_overbought: number;
  /** Stop-loss (0.5-10.0% of entry) */
  stop_loss_pct: number;
  /** Take profit (0.5-20.0% of entry) */
  take_profit_pct: number;
  /** Max position holding time (1-168 hours) */
  max_holding_hours: number;
}

// ============================================================================
// Strategy Configuration Block
// ============================================================================

export type StrategyName =
  | "ma_crossover"
  | "rsi_mean_reversion"
  | "momentum_breakout"
  | "bollinger_breakout"
  | "vwap_reversion";

export type StrategyParams =
  | MACrossoverParams
  | RSIMeanReversionParams
  | MomentumBreakoutParams
  | BollingerBreakoutParams
  | VWAPReversionParams;

export interface StrategyConfig {
  /** Strategy identifier */
  name: StrategyName;
  /** Strategy-specific parameters */
  parameters: StrategyParams;
  /** Human-readable summary (max 500 chars, optional) */
  description?: string;
}

// ============================================================================
// Risk, Execution, Safety Limits
// ============================================================================

export interface RiskConfig {
  /** Max loss per position (0.1-50.0%) */
  stop_loss_pct: number;
  /** Profit target per position (0.1-200.0%) */
  take_profit_pct: number;
  /** Max % of portfolio per position (1.0-100.0%) */
  max_position_size_pct: number;
  /** Max portfolio loss per day (0.1-50.0%, halts trading if exceeded) */
  max_daily_loss_pct: number;
  /** Max concurrent positions per ticker (1-50) */
  max_open_positions: number;
  /** Max total concurrent positions (1-100) */
  portfolio_max_positions: number;
  /** Enable trailing stop-loss */
  trailing_stop_enabled: boolean;
  /** Trailing stop distance (0.1-50.0%, required if enabled=true) */
  trailing_stop_pct: number;
  /** Broker commission per trade (0.0-100.0 USD) */
  commission_per_trade: number;
}

export interface ExecutionConfig {
  /** Order execution type */
  order_type: "market" | "limit";
  /** Offset from current price (0.0-5.0%, required if order_type='limit') */
  limit_offset_pct: number;
  /** Min bars between signals for same ticker (0-100) */
  cooldown_bars: number;
}

export interface SafetyLimitsConfig {
  /** Max trades per day (1-1000, default: 20). Exceeded → auto-pause + CRITICAL alert */
  max_trades_per_day?: number;
  /** Max broker API calls/hour (10-10000, default: 500). 80% → WARNING, 100% → pause */
  max_api_calls_per_hour?: number;
  /** Max time for signal generation (0.1-60.0 seconds, default: 5.0). Exceeded → skip signal */
  signal_generation_timeout_seconds?: number;
  /** Consecutive API failures before degraded mode (1-10, default: 3) */
  broker_degraded_mode_threshold_failures?: number;
}

// ============================================================================
// Metadata
// ============================================================================

export interface BacktestPeriod {
  /** Start date (YYYY-MM-DD) */
  start: string;
  /** End date (YYYY-MM-DD) */
  end: string;
}

export interface PerformanceMetrics {
  /** Risk-adjusted return (-10.0 to 10.0) */
  sharpe_ratio: number;
  /** Downside risk-adjusted return (-10.0 to 10.0) */
  sortino_ratio: number;
  /** Total backtest return (-100.0 to 10000.0%) */
  total_return_pct: number;
  /** Maximum drawdown (-100.0 to 0.0%, negative value) */
  max_drawdown_pct: number;
  /** Percentage of winning trades (0.0-100.0%) */
  win_rate_pct: number;
  /** Gross profit / gross loss (0.0-100.0) */
  profit_factor: number;
  /** Total number of trades (0-100000) */
  total_trades: number;
  /** CAGR / max drawdown (-10.0 to 10.0) */
  calmar_ratio: number;
}

export interface MetadataConfig {
  /** Export source (always "AlphaLab") */
  exported_from: "AlphaLab";
  /** Export timestamp (ISO 8601 UTC) */
  exported_at: string;
  /** AlphaLab version (e.g., "0.2.0") */
  alphalab_version: string;
  /** Unique backtest identifier */
  backtest_id: string;
  /** Backtest date range */
  backtest_period: BacktestPeriod;
  /** Backtest performance metrics */
  performance: PerformanceMetrics;
}

// ============================================================================
// Root Schema
// ============================================================================

export interface StrategyExportSchema {
  /** Schema version (currently "1.0") */
  schema_version: "1.0";
  /** Strategy configuration block */
  strategy: StrategyConfig;
  /** Primary ticker symbol (1-10 chars) */
  ticker: string;
  /** Trading timeframe */
  timeframe: "1Day" | "1Hour" | "15Min";
  /** Risk management parameters */
  risk: RiskConfig;
  /** Order execution settings */
  execution: ExecutionConfig;
  /** Safety limits (optional, defaults applied if missing) */
  safety_limits?: SafetyLimitsConfig;
  /** Backtest provenance and performance */
  metadata: MetadataConfig;
}

// ============================================================================
// Utility Types & Constants
// ============================================================================

export const STRATEGY_STATUS: Record<StrategyName, "implemented" | "planned"> = {
  ma_crossover: "implemented",
  rsi_mean_reversion: "implemented",
  momentum_breakout: "implemented",
  bollinger_breakout: "planned",
  vwap_reversion: "planned",
};

export const DEFAULT_SAFETY_LIMITS: Required<SafetyLimitsConfig> = {
  max_trades_per_day: 20,
  max_api_calls_per_hour: 500,
  signal_generation_timeout_seconds: 5.0,
  broker_degraded_mode_threshold_failures: 3,
};

/**
 * Type guard to check if a strategy is implemented in AlphaLab.
 */
export function isImplementedStrategy(name: StrategyName): boolean {
  return STRATEGY_STATUS[name] === "implemented";
}

/**
 * Validate strategy export schema structure (basic type check).
 * For full validation, use Pydantic backend model.
 */
export function isValidStrategyExport(data: unknown): data is StrategyExportSchema {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;

  return (
    obj.schema_version === "1.0" &&
    typeof obj.strategy === "object" &&
    typeof obj.ticker === "string" &&
    (obj.timeframe === "1Day" || obj.timeframe === "1Hour" || obj.timeframe === "15Min") &&
    typeof obj.risk === "object" &&
    typeof obj.execution === "object" &&
    typeof obj.metadata === "object"
  );
}

/**
 * Apply default safety limits if missing from schema.
 */
export function applySafetyLimitsDefaults(
  schema: StrategyExportSchema
): Required<StrategyExportSchema> {
  return {
    ...schema,
    safety_limits: {
      ...DEFAULT_SAFETY_LIMITS,
      ...schema.safety_limits,
    },
  };
}

// ============================================================================
// Example Data
// ============================================================================

export const EXAMPLE_MA_CROSSOVER_EXPORT: StrategyExportSchema = {
  schema_version: "1.0",
  strategy: {
    name: "ma_crossover",
    parameters: {
      short_window: 50,
      long_window: 200,
      volume_confirmation: true,
      cooldown_days: 5,
    },
    description: "Golden Cross strategy for SPY",
  },
  ticker: "SPY",
  timeframe: "1Day",
  risk: {
    stop_loss_pct: 3.0,
    take_profit_pct: 10.0,
    max_position_size_pct: 25.0,
    max_daily_loss_pct: 5.0,
    max_open_positions: 1,
    portfolio_max_positions: 5,
    trailing_stop_enabled: false,
    trailing_stop_pct: 0.0,
    commission_per_trade: 0.0,
  },
  execution: {
    order_type: "market",
    limit_offset_pct: 0.0,
    cooldown_bars: 5,
  },
  safety_limits: {
    max_trades_per_day: 20,
    max_api_calls_per_hour: 500,
    signal_generation_timeout_seconds: 5.0,
    broker_degraded_mode_threshold_failures: 3,
  },
  metadata: {
    exported_from: "AlphaLab",
    exported_at: "2026-03-08T14:30:00Z",
    alphalab_version: "0.2.0",
    backtest_id: "bt_spy_ma_20260308",
    backtest_period: {
      start: "2020-01-01",
      end: "2024-12-31",
    },
    performance: {
      sharpe_ratio: 1.23,
      sortino_ratio: 1.65,
      total_return_pct: 28.4,
      max_drawdown_pct: -11.2,
      win_rate_pct: 54.5,
      profit_factor: 1.52,
      total_trades: 22,
      calmar_ratio: 2.54,
    },
  },
};
