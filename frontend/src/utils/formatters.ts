export function formatPercent(value: number | undefined | null, decimals = 2): string {
  if (value == null || isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

export function formatCurrency(value: number | undefined | null): string {
  if (value == null || isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number | undefined | null, decimals = 2): string {
  if (value == null || isNaN(value)) return "—";
  return value.toFixed(decimals);
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function strategyDisplayName(strategy: string): string {
  const map: Record<string, string> = {
    ma_crossover: "MA Crossover",
    rsi_mean_reversion: "RSI Mean Reversion",
    momentum_breakout: "Momentum Breakout",
  };
  return map[strategy] || strategy;
}

export function qualityColor(score: number): string {
  if (score >= 0.95) return "text-gain";
  if (score >= 0.85) return "text-warning";
  return "text-loss";
}

export function pnlColor(value: number): string {
  if (value > 0) return "text-gain";
  if (value < 0) return "text-loss";
  return "text-muted-foreground";
}
