import { TrendingUp, RefreshCcw, Zap, Waves, Target, type LucideIcon } from "lucide-react";
import type { StrategyType } from "@/types";

export const STRATEGY_META: Record<StrategyType, { category: string; icon: LucideIcon; accent: string }> = {
  ma_crossover: { category: "Trend Following", icon: TrendingUp, accent: "text-primary" },
  rsi_mean_reversion: { category: "Mean Reversion", icon: RefreshCcw, accent: "text-lab-secondary" },
  momentum_breakout: { category: "Momentum", icon: Zap, accent: "text-warning" },
  bollinger_breakout: { category: "Volatility Breakout", icon: Waves, accent: "text-gain" },
  vwap_reversion: { category: "Mean Reversion", icon: Target, accent: "text-lab-secondary" },
};

// Icon-chip gradient per accent class — shared with StrategyCard so selector
// controls and data cards read as the same visual system.
export const STRATEGY_ACCENT_GRADIENT: Record<string, string> = {
  "text-primary": "from-primary to-lab-deep",
  "text-lab-secondary": "from-lab-secondary to-primary",
  "text-warning": "from-warning to-orange-500",
  "text-gain": "from-gain to-lab-secondary",
};
