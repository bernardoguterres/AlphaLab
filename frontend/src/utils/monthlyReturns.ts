import type { EquityCurvePoint } from "@/types";

/**
 * Month-over-month return, keyed "year-month" (month 0-based): each month is
 * measured from the PREVIOUS month's last value to its own last value (the
 * first month from its first point). Measuring first-to-last point inside the
 * month dropped every move between the previous close and the month's first
 * bar - on monthly bars every cell was 0 - so the compounded year total was
 * wrong too (2021: +1.06% shown vs -7.53% actual). Dates are bar dates at UTC
 * midnight, so UTC getters keep them in the right month in any timezone.
 */
export function monthlyReturns(curve: EquityCurvePoint[]): Map<string, number> {
  const months = new Map<string, { base: number; last: number }>();
  let prevMonthEnd: number | undefined;
  let currentKey: string | undefined;
  for (const point of curve) {
    const d = new Date(point.date);
    const key = `${d.getUTCFullYear()}-${d.getUTCMonth()}`;
    if (key !== currentKey) {
      if (currentKey !== undefined) prevMonthEnd = months.get(currentKey)!.last;
      months.set(key, { base: prevMonthEnd ?? point.value, last: point.value });
      currentKey = key;
    } else {
      months.get(key)!.last = point.value;
    }
  }
  return new Map([...months].map(([key, { base, last }]) => [key, ((last - base) / base) * 100]));
}
