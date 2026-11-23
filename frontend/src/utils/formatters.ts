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

/**
 * Parse a bar date (a calendar day) into a Date at UTC midnight of that day.
 *
 * The backend sends two shapes: RFC 1123 with GMT for equity-curve points
 * ("Mon, 08 Jul 2024 00:00:00 GMT") and timezone-less ISO for order
 * timestamps ("2024-07-08 00:00:00"). JS reads the latter as LOCAL time, so a
 * single parse-then-format rule shifts one shape by a day in some timezones
 * (UTC formatting showed Jul 8 fills as "Jul 7" east of UTC; local formatting
 * showed Jan 1 as "Dec 31" west of UTC). Leading YYYY-MM-DD is taken
 * literally; anything else is parsed and read in UTC.
 */
export function parseBarDate(dateStr: string | undefined | null): Date | null {
  if (!dateStr) return null;
  const ymd = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateStr);
  if (ymd) return new Date(Date.UTC(Number(ymd[1]), Number(ymd[2]) - 1, Number(ymd[3])));
  const parsed = new Date(dateStr);
  if (isNaN(parsed.getTime())) return null;
  return new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()));
}

export function formatDate(dateStr: string | undefined | null): string {
  const date = parseBarDate(dateStr);
  if (!date) return "-";
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
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
