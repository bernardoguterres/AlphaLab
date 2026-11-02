/** Signed by default, for changes; pass signed=false for shares and rates (win rate, volatility). */
export function formatPercent(value: number | undefined | null, decimals = 2, signed = true): string {
  if (value == null || isNaN(value)) return "-";
  return `${signed && value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

export function formatCurrency(value: number | undefined | null): string {
  if (value == null || isNaN(value)) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number | undefined | null, decimals = 2): string {
  if (value == null || isNaN(value)) return "-";
  return value.toFixed(decimals);
}

export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(dateStr: string | undefined | null): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "-";
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export type QualityLevel = "good" | "fair" | "poor";

/** Bands for the 0-1 data quality score returned by POST /api/data/fetch. */
export function qualityLevel(score: number): QualityLevel {
  if (score >= 0.95) return "good";
  if (score >= 0.85) return "fair";
  return "poor";
}

const QUALITY_COLOR: Record<QualityLevel, string> = { good: "text-gain", fair: "text-warning", poor: "text-loss" };

export function qualityColor(score: number): string {
  return QUALITY_COLOR[qualityLevel(score)];
}

export function pnlColor(value: number): string {
  if (value > 0) return "text-gain";
  if (value < 0) return "text-loss";
  return "text-muted-foreground";
}
