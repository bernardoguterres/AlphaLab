import { describe, it, expect } from "vitest";
import {
  formatPercent,
  formatCurrency,
  formatNumber,
  formatDate,
  qualityColor,
  pnlColor,
} from "./formatters";

describe("formatPercent", () => {
  it("prefixes positive values with +", () => {
    expect(formatPercent(13.75)).toBe("+13.75%");
  });

  it("keeps the minus sign on negatives", () => {
    expect(formatPercent(-4.2)).toBe("-4.20%");
  });

  it("treats zero as positive", () => {
    expect(formatPercent(0)).toBe("+0.00%");
  });

  it("omits the sign for unsigned quantities", () => {
    expect(formatPercent(55, 1, false)).toBe("55.0%");
  });

  it("respects the decimals argument", () => {
    expect(formatPercent(1.23456, 1)).toBe("+1.2%");
  });

  it("returns dash for null, undefined, and NaN", () => {
    expect(formatPercent(null)).toBe("-");
    expect(formatPercent(undefined)).toBe("-");
    expect(formatPercent(NaN)).toBe("-");
  });
});

describe("formatCurrency", () => {
  it("formats whole dollars with grouping", () => {
    expect(formatCurrency(100000)).toBe("$100,000");
  });

  it("rounds to whole dollars", () => {
    expect(formatCurrency(1234.56)).toBe("$1,235");
  });

  it("handles negatives", () => {
    expect(formatCurrency(-500)).toBe("-$500");
  });

  it("returns dash for null/undefined/NaN", () => {
    expect(formatCurrency(null)).toBe("-");
    expect(formatCurrency(undefined)).toBe("-");
    expect(formatCurrency(NaN)).toBe("-");
  });
});

describe("formatNumber", () => {
  it("formats with default 2 decimals", () => {
    expect(formatNumber(1.2345)).toBe("1.23");
  });

  it("returns dash for null", () => {
    expect(formatNumber(null)).toBe("-");
  });
});

describe("formatDate", () => {
  it("formats ISO dates", () => {
    expect(formatDate("2026-07-10")).toMatch(/Jul \d{1,2}, 2026/);
  });

  it("returns dash for empty and invalid input", () => {
    expect(formatDate("")).toBe("-");
    expect(formatDate(null)).toBe("-");
    expect(formatDate("not-a-date")).toBe("-");
  });
});

describe("qualityColor / pnlColor", () => {
  it("maps quality score bands to colors", () => {
    expect(qualityColor(0.99)).toBe("text-gain");
    expect(qualityColor(0.9)).toBe("text-warning");
    expect(qualityColor(0.5)).toBe("text-loss");
  });

  it("maps pnl sign to colors", () => {
    expect(pnlColor(10)).toBe("text-gain");
    expect(pnlColor(-10)).toBe("text-loss");
    expect(pnlColor(0)).toBe("text-muted-foreground");
  });
});
