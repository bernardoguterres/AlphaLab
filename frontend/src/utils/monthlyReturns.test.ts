import { describe, expect, it } from "vitest";

import { monthlyReturns } from "@/utils/monthlyReturns";
import { formatDate } from "@/utils/formatters";

// B13 (Nov 2026 audit): months were measured first-to-last point inside the
// month, dropping the move from the previous month-end to the month's first
// bar; the compounded year total was therefore wrong too.
describe("monthlyReturns", () => {
  it("chains each month from the previous month's last value", () => {
    const r = monthlyReturns([
      { date: "2021-01-04", value: 100 },
      { date: "2021-01-29", value: 110 },
      { date: "2021-02-01", value: 99 }, // gap down at the month boundary
      { date: "2021-02-26", value: 99 },
    ]);
    expect(r.get("2021-0")).toBeCloseTo(10);
    expect(r.get("2021-1")).toBeCloseTo(-10); // 110 -> 99, not 0
  });

  it("gives non-zero months on monthly bars (one point per month)", () => {
    const r = monthlyReturns([
      { date: "2021-01-01", value: 100 },
      { date: "2021-02-01", value: 105 },
      { date: "2021-03-01", value: 94.5 },
    ]);
    expect(r.get("2021-1")).toBeCloseTo(5);
    expect(r.get("2021-2")).toBeCloseTo(-10);
  });

  it("keeps first-of-month bar dates in their month (UTC)", () => {
    const r = monthlyReturns([
      { date: "2021-01-29T00:00:00Z", value: 100 },
      { date: "2021-02-01T00:00:00Z", value: 102 },
    ]);
    expect([...r.keys()]).toEqual(["2021-0", "2021-1"]);
  });
});

describe("formatDate", () => {
  it("formats bar dates as their calendar day in any timezone", () => {
    expect(formatDate("2020-01-01")).toBe("Jan 1, 2020");
  });
});

// Trade timestamps arrive timezone-less ("2024-07-08 00:00:00"); JS reads
// them as local time. They must keep their calendar day in every timezone.
describe("bar dates in both backend shapes", () => {
  it.each([
    ["2024-07-08 00:00:00", "Jul 8, 2024"],
    ["2024-07-08T00:00:00", "Jul 8, 2024"],
    ["2024-07-08", "Jul 8, 2024"],
    ["Mon, 08 Jul 2024 00:00:00 GMT", "Jul 8, 2024"],
    ["Wed, 01 Jan 2020 00:00:00 GMT", "Jan 1, 2020"],
  ])("formatDate(%s) = %s", (input, expected) => {
    expect(formatDate(input)).toBe(expected);
  });

  it("keeps timezone-less first-of-month points in their month", () => {
    const r = monthlyReturns([
      { date: "2024-06-28 00:00:00", value: 100 },
      { date: "2024-07-01 00:00:00", value: 105 },
    ]);
    expect([...r.keys()]).toEqual(["2024-5", "2024-6"]);
  });
});
