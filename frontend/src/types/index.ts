export interface EquityCurvePoint {
  date: string;
  value: number;
}

// Paired round-trip trade (entry + matching exit), as rendered by TradeTable.
// Not what the backend sends directly - see RawOrder below and
// utils/tradePairing.ts's pairTradesFIFO(), which derives this shape from
// the raw per-order ledger, mirroring the backend's own FIFO buy/sell
// matching in alphalab/backtest/metrics.py's _trade_metrics().
export interface Trade {
  entry_date: string;
  exit_date: string;
  shares: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
}

// Raw per-order ledger entry - what BacktestResult.trades actually contains
// (Portfolio._log_trade()/Order.to_dict() in portfolio.py/order.py): one
// row per individual BUY or SELL order, not a paired trade. Previously
// BacktestResult.trades was typed as Trade[] directly and passed straight
// into TradeTable, which expected entry_date/exit_date/action/entry_price/
// exit_price/pnl/pnl_pct - none of which exist on this shape, so every
// cell in the Trade Table silently rendered "-" for every backtest.
export interface RawOrder {
  ticker: string;
  side: "buy" | "sell";
  shares: number;
  order_type: string;
  status: string;
  filled_price: number | null;
  commission: number;
  slippage: number;
  timestamp: string | null;
  filled_timestamp: string | null;
  reason: string;
  portfolio_cash: number;
}

export interface BacktestMetrics {
  returns: {
    total_return_pct: number;
    cagr_pct: number;
    mean_daily_return: number;
    skewness: number;
    kurtosis: number;
  };
  risk: {
    volatility_annual_pct: number;
    sharpe_ratio: number;
    sharpe_ratio_zero_rf?: number;
    sortino_ratio: number;
    calmar_ratio: number;
    var_95_pct: number;
    cvar_95_pct: number;
  };
  drawdown: {
    max_drawdown_pct: number;
    avg_drawdown_pct: number;
    max_drawdown_duration_days: number;
    recovery_days: number;
  };
  trades: {
    win_rate: number;
    avg_win: number;
    avg_loss: number;
    profit_factor: number;
    expectancy: number;
    best_trade: number;
    worst_trade: number;
  };
  consistency: {
    profitable_months_pct: number;
    longest_win_streak: number;
    longest_loss_streak: number;
    ulcer_index: number;
  };
  assumptions?: {
    cash_return_pct: number;
    risk_free_rate_pct: number;
    periods_per_year: number;
    average_exposure_pct?: number;
    note?: string;
  };
  vs_benchmark: {
    beta: number;
    alpha_annual_pct: number;
    active_return_t_stat: number;
    active_return_p_value: number;
    active_return_significant: boolean;
    tracking_error_pct: number;
    information_ratio: number;
    up_capture_pct: number;
    down_capture_pct: number;
  };
}

// Audit bug 3.12: previously declared percentile_25/median/percentile_75,
// which the backend has never returned (engine.py's _monte_carlo() only
// computes percentile_5/95) - and every field here was rendered through
// formatPercent() despite being a dollar amount (final portfolio value
// across simulated runs), producing outputs like "+125430.00%". Backend
// is the source of truth (it's a coherent, already-correct distribution
// of final dollar values); this type and its renderer (Backtest.tsx) now
// match what engine.py's _monte_carlo() actually returns.
export interface MonteCarloResult {
  method?: string; // "circular_moving_block_bootstrap"
  question?: string;
  seed?: number;
  block_length?: number;
  runs: number;
  mean_final_value: number;
  median_final_value: number;
  std_final_value: number;
  min_final_value: number;
  max_final_value: number;
  prob_profit: number; // 0-1 fraction
  percentile_5: number;
  percentile_95: number;
}

export interface BacktestResult {
  backtest_id: string;
  strategy: string;
  ticker?: string;
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  total_trades: number;
  equity_curve: EquityCurvePoint[];
  trades: RawOrder[];
  metrics: BacktestMetrics;
  benchmark: {
    equity_curve: EquityCurvePoint[];
    total_return_pct: number;
  };
  monte_carlo: MonteCarloResult | null;
  // threshold_pct is the halt actually simulated (null = disabled)
  drawdown_halt?: {
    threshold_pct: number | null;
    halted: boolean;
    halted_at: string | null;
    halted_drawdown_pct: number | null;
  } | null;
}

export interface BacktestHistoryItem {
  id: string;
  date: string;
  ticker: string;
  strategy: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  result: BacktestResult;
}

export type StrategyType = "ma_crossover" | "rsi_mean_reversion" | "rsi_simple" | "momentum_breakout" | "bollinger_breakout" | "vwap_reversion" | "bollinger_rsi_combo" | "trend_adaptive_rsi" | "greenblatt_weekly";

export interface MACrossoverParams {
  short_window: number;
  long_window: number;
  volume_confirmation: boolean;
  cooldown_days: number;
}

export interface RSIMeanReversionParams {
  rsi_period: number;
  oversold: number;
  overbought: number;
  use_bb_confirmation: boolean;
  adx_threshold: number;
}

export interface RSISimpleParams {
  period: number;
  oversold: number;
  overbought: number;
}

export interface MomentumBreakoutParams {
  lookback: number;
  volume_surge_pct: number;
  rsi_min: number;
  stop_loss_atr_mult: number;
}

export interface BollingerBreakoutParams {
  bb_period: number;
  bb_std_dev: number;
  confirmation_bars: number;
  volume_filter: boolean;
  volume_threshold: number;
  cooldown_days: number;
}

export interface VWAPReversionParams {
  vwap_period: number;
  deviation_threshold: number;
  rsi_period: number;
  oversold: number;
  overbought: number;
  cooldown_days: number;
}

export interface BollingerRSIComboParams {
  bb_period: number;
  bb_std: number;
  rsi_period: number;
  rsi_oversold: number;
  rsi_overbought: number;
  exit_at_middle: boolean;
}

export interface TrendAdaptiveRSIParams {
  rsi_period: number;
  trend_sma: number;
  trend_lookback: number;
  uptrend_buy: number;
  uptrend_sell: number;
  downtrend_buy: number;
  downtrend_sell: number;
  range_buy: number;
  range_sell: number;
}

export interface GreenblattWeeklyParams {
  fast_sma: number;
  slow_sma: number;
  rsi_period: number;
  rsi_oversold: number;
  rsi_overbought: number;
  min_hold_bars: number;
  trailing_stop_pct: number;
  exit_rsi_overbought: boolean;
  exit_sma_cross: boolean;
}

export type StrategyParams = MACrossoverParams | RSIMeanReversionParams | RSISimpleParams | MomentumBreakoutParams | BollingerBreakoutParams | VWAPReversionParams | BollingerRSIComboParams | TrendAdaptiveRSIParams | GreenblattWeeklyParams;

export interface CachedTicker {
  /** The backend's cache key, unique per ticker, interval and window. */
  key: string;
  ticker: string;
  interval: string;
  start_date: string;
  end_date: string;
  records: number;
  last_updated: string;
}

export interface FetchDataResponse {
  status: "ok" | "error";
  data: Record<string, { records: number; quality_score: number }>;
  errors: string[];
  message?: string;
}

export interface RiskSettings {
  stop_loss_pct: number;
  take_profit_pct: number;
  max_position_size_pct: number;
  max_daily_loss_pct: number;
  max_open_positions: number;
  trailing_stop_enabled: boolean;
  trailing_stop_pct: number;
  commission_per_trade: number;
}

export const DEFAULT_RISK_SETTINGS: RiskSettings = {
  stop_loss_pct: 2.0,
  take_profit_pct: 5.0,
  max_position_size_pct: 10.0,
  max_daily_loss_pct: 3.0,
  max_open_positions: 5,
  trailing_stop_enabled: false,
  trailing_stop_pct: 3.0,
  commission_per_trade: 0.0,
};

export interface BacktestRequest {
  ticker: string;
  strategy: StrategyType;
  start_date: string;
  end_date: string;
  initial_capital: number;
  params: StrategyParams;
  position_sizing: "equal_weight" | "volatility_weighted";
  monte_carlo_runs: number;
  risk_settings?: RiskSettings;
  drawdown_halt_enabled?: boolean;
}

export interface CompareRequest {
  ticker: string;
  strategies: StrategyType[];
  start_date: string;
  end_date: string;
  initial_capital: number;
}

export interface BatchBacktestRequest {
  tickers: string[];
  strategy: StrategyType;
  start_date: string;
  end_date: string;
  initial_capital: number;
  params: StrategyParams;
  position_sizing: "equal_weight" | "volatility_weighted";
  risk_settings?: RiskSettings;
}

export interface BatchBacktestResult {
  ticker: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  final_value: number;
  metrics: BacktestMetrics;
}

export interface BatchSummary {
  total_tickers: number;
  successful: number;
  failed: number;
  profitable_count: number;
  profitable_pct: number;
  avg_sharpe_ratio: number;
  best_ticker: string | null;
  best_sharpe: number | null;
  worst_ticker: string | null;
  worst_sharpe: number | null;
  runtime_seconds: number;
}

export interface BatchBacktestResponse {
  status: "ok" | "error";
  data: {
    results: BatchBacktestResult[];
    batch_summary: BatchSummary;
    errors: { ticker: string; error: string }[];
  };
  message?: string;
}

export interface CompareResponse {
  status: "ok" | "error";
  data: Record<string, BacktestResult>;
  message?: string;
}

export interface ParameterOptimizeRequest {
  ticker: string;
  strategy: StrategyType;
  start_date: string;
  end_date: string;
  param_grid: Record<string, number[]>;
  initial_capital: number;
  optimization_target: "sharpe_ratio" | "total_return_pct" | "max_drawdown_pct" | "win_rate";
  walk_forward: boolean;
  n_folds: number;
}

export interface ParameterOptimizeResult {
  params: Record<string, number>;
  score: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
}

// One entry per walk-forward FOLD (not per parameter combination) -
// each fold selects its own best-scoring params using only that fold's
// train window, then evaluates just that selection on the held-out test
// window. See backend parameter_optimizer.py's _walk_forward_optimize
// docstring (bug 3.3 fix, 2026-07-14) for why a per-combination table
// is no longer meaningful once selection is leakage-free.
export interface WalkForwardResult {
  fold: number;
  train_start: string | null;
  train_end: string | null;
  test_start: string | null;
  test_end: string | null;
  selected_params: Record<string, number>;
  train_score: number;
  avg_out_of_sample_score: number | null;
}

export interface ParameterOptimizeResponse {
  status: "ok" | "error";
  data: {
    best_params: Record<string, number>;
    best_score: number;
    all_results: ParameterOptimizeResult[] | WalkForwardResult[];
    optimization_target: string;
    walk_forward: boolean;
    n_folds?: number;
    final_backtest?: {
      total_return_pct: number;
      sharpe_ratio: number;
      max_drawdown_pct: number;
    };
  };
  message?: string;
}

export interface HeatmapRequest {
  ticker: string;
  strategy: StrategyType;
  start_date: string;
  end_date: string;
  param1_name: string;
  param1_min: number;
  param1_max: number;
  param1_step: number;
  param2_name: string;
  param2_min: number;
  param2_max: number;
  param2_step: number;
  fixed_params: Record<string, number>;
  initial_capital: number;
}

export interface HeatmapResponse {
  status: "ok" | "error";
  data: {
    param1_name: string;
    param1_values: number[];
    param2_name: string;
    param2_values: number[];
    heatmap_data: (number | null)[][];
  };
  message?: string;
}
