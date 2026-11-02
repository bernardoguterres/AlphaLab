import type { CachedTicker } from "@/types";

/** Matches the backend's cache_expiry_hours (config.yaml). */
export const CACHE_EXPIRY_HOURS = 24;

export type Freshness = "fresh" | "expired" | "unknown";

export function cacheAgeMs(item: CachedTicker, now = Date.now()): number | null {
  const updated = new Date(item.last_updated).getTime();
  return Number.isNaN(updated) ? null : now - updated;
}

export function freshness(item: CachedTicker, now = Date.now()): Freshness {
  const age = cacheAgeMs(item, now);
  if (age === null) return "unknown";
  return age <= CACHE_EXPIRY_HOURS * 3_600_000 ? "fresh" : "expired";
}

/** "3h ago", "2 days ago". */
export function formatAge(ms: number): string {
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "under an hour ago";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/** Newest and oldest last_updated across the cache, or null when it's empty. */
export function cacheSpan(items: CachedTicker[]): { newest: string; oldest: string } | null {
  const times = items.map((c) => new Date(c.last_updated).getTime()).filter((t) => !Number.isNaN(t));
  if (times.length === 0) return null;
  return { newest: new Date(Math.max(...times)).toISOString(), oldest: new Date(Math.min(...times)).toISOString() };
}
