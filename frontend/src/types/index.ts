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

export type StrategyType = "ma_crossover" | "rsi_mean_reversion" | "momentum_breakout";

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

export type StrategyParams = MACrossoverParams | RSIMeanReversionParams | MomentumBreakoutParams;

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

export interface BacktestRequest {
  ticker: string;
  strategy: StrategyType;
  start_date: string;
  end_date: string;
  initial_capital: number;
  params: StrategyParams;
  position_sizing: "equal_weight" | "risk_parity" | "volatility_weighted";
  monte_carlo_runs: number;
}

export interface CompareRequest {
  ticker: string;
  strategies: StrategyType[];
  start_date: string;
  end_date: string;
  initial_capital: number;
}

export interface CompareResponse {
  status: "ok" | "error";
  data: Record<string, BacktestResult>;
  message?: string;
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
};
