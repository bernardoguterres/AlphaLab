export interface EquityCurvePoint {
  date: string;
  value: number;
}

export interface Trade {
  entry_date: string;
  exit_date: string;
  action: "BUY" | "SELL";
  shares: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
}

export interface BacktestMetrics {
  returns: {
    total_return_pct: number;
    cagr: number;
    mean_return: number;
    skewness: number;
    kurtosis: number;
  };
  risk: {
    volatility: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    calmar_ratio: number;
    var_95: number;
    cvar_95: number;
  };
  drawdown: {
    max_drawdown: number;
    avg_drawdown: number;
    max_drawdown_duration: number;
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
  vs_benchmark: {
    beta: number;
    alpha: number;
    alpha_p_value: number;
    tracking_error: number;
    information_ratio: number;
    up_capture: number;
    down_capture: number;
  };
}

export interface MonteCarloResult {
  percentile_5: number;
  percentile_25: number;
  median: number;
  percentile_75: number;
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
  trades: Trade[];
  metrics: BacktestMetrics;
  benchmark: {
    equity_curve: EquityCurvePoint[];
    total_return_pct: number;
  };
  monte_carlo: MonteCarloResult | null;
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

export type StrategyType = "ma_crossover" | "rsi_mean_reversion" | "momentum_breakout" | "bollinger_breakout" | "vwap_reversion";

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

export type StrategyParams = MACrossoverParams | RSIMeanReversionParams | MomentumBreakoutParams | BollingerBreakoutParams | VWAPReversionParams;

export interface CachedTicker {
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
  position_sizing: "equal_weight" | "risk_parity" | "volatility_weighted";
  monte_carlo_runs: number;
  risk_settings?: RiskSettings;
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
  position_sizing: "equal_weight" | "risk_parity" | "volatility_weighted";
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

export interface WalkForwardResult {
  params: Record<string, number>;
  avg_out_of_sample_score: number;
  fold_scores: number[];
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

export interface PortfolioStrategy {
  backtest_id: string;
  ticker: string;
  strategy: string;
}

export interface PortfolioConstraints {
  max_weight_per_strategy: number;
  min_weight_per_strategy: number;
  target_return: number | null;
}

export interface PortfolioOptimizeRequest {
  strategies: PortfolioStrategy[];
  method: "max_sharpe" | "min_variance" | "equal_weight" | "risk_parity";
  constraints?: PortfolioConstraints;
}

export interface EfficientFrontierPoint {
  return: number;
  risk: number;
  sharpe_ratio: number;
}

export interface PortfolioOptimizeResponse {
  status: "ok" | "error";
  data: {
    optimal_weights: number[];
    expected_return: number;
    expected_risk: number;
    sharpe_ratio: number;
    strategy_labels: string[];
    efficient_frontier: EfficientFrontierPoint[];
  };
  message?: string;
}

export interface TelegramSettings {
  enabled: boolean;
  alert_trades: boolean;
  alert_daily_summary: boolean;
  alert_errors: boolean;
  alert_drawdown: boolean;
  alert_signals: boolean;
  drawdown_threshold_pct: number;
}

export interface AlpacaSettings {
  paper_trading: boolean;
  api_key_configured?: boolean;
  secret_key_configured?: boolean;
}

export interface NotificationSettings {
  telegram: TelegramSettings;
  alpaca: AlpacaSettings;
}

export interface NotificationSettingsResponse {
  status: "ok" | "error";
  data: NotificationSettings;
  message?: string;
}

export interface SaveSettingsResponse {
  status: "ok" | "error";
  message?: string;
}

export interface TestConnectionResponse {
  status: "ok" | "error";
  message?: string;
  data?: {
    account_number?: string;
    status?: string;
    buying_power?: number;
    cash?: number;
    paper_trading?: boolean;
  };
}

export const STRATEGY_INFO: Record<StrategyType, { name: string; description: string }> = {
  ma_crossover: {
    name: "MA Crossover",
    description: "Trades when short-term moving average crosses long-term moving average",
  },
  rsi_mean_reversion: {
    name: "RSI Mean Reversion",
    description: "Buys oversold conditions and sells overbought using RSI indicator",
  },
  momentum_breakout: {
    name: "Momentum Breakout",
    description: "Enters positions on price breakouts confirmed by volume surge",
  },
  bollinger_breakout: {
    name: "Bollinger Breakout",
    description: "Trades consecutive closes outside Bollinger Bands with volume confirmation",
  },
  vwap_reversion: {
    name: "VWAP Reversion",
    description: "Mean reversion strategy trading deviations from Volume-Weighted Average Price",
  },
};

export const DEFAULT_PARAMS: Record<StrategyType, StrategyParams> = {
  ma_crossover: {
    short_window: 50,
    long_window: 200,
    volume_confirmation: true,
    cooldown_days: 5,
  },
  rsi_mean_reversion: {
    rsi_period: 14,
    oversold: 30,
    overbought: 70,
    use_bb_confirmation: true,
    adx_threshold: 25,
  },
  momentum_breakout: {
    lookback: 20,
    volume_surge_pct: 150,
    rsi_min: 50,
    stop_loss_atr_mult: 2.0,
  },
  bollinger_breakout: {
    bb_period: 20,
    bb_std_dev: 2.0,
    confirmation_bars: 2,
    volume_filter: true,
    volume_threshold: 1.5,
    cooldown_days: 3,
  },
  vwap_reversion: {
    vwap_period: 20,
    deviation_threshold: 2.0,
    rsi_period: 14,
    oversold: 30,
    overbought: 70,
    cooldown_days: 3,
  },
};
