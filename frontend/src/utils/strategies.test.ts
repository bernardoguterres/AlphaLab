import { describe, it, expect } from "vitest";
import { STRATEGIES, STRATEGY_TYPES, DEFAULT_PARAMS, optimizeRanges, paramSummary, strategyName } from "./strategies";

describe("strategy registry", () => {
  it("covers all 9 backend strategies", () => {
    expect(STRATEGY_TYPES).toHaveLength(9);
  });

  it("keeps every default inside its own slider bounds", () => {
    for (const id of STRATEGY_TYPES) {
      for (const p of STRATEGIES[id].params) {
        if (p.kind !== "number") continue;
        expect(p.default, `${id}.${p.key}`).toBeGreaterThanOrEqual(p.min);
        expect(p.default, `${id}.${p.key}`).toBeLessThanOrEqual(p.max);
      }
    }
  });

  it("only sweeps numeric parameters, with a positive step", () => {
    for (const id of STRATEGY_TYPES) {
      const ranges = optimizeRanges(id);
      expect(Object.keys(ranges).length, id).toBeGreaterThanOrEqual(2);
      for (const [key, r] of Object.entries(ranges)) {
        expect(typeof (DEFAULT_PARAMS[id] as unknown as Record<string, unknown>)[key], `${id}.${key}`).toBe("number");
        expect(r.step, `${id}.${key}`).toBeGreaterThan(0);
      }
    }
  });

  it("points shownWhen at a boolean parameter of the same strategy", () => {
    for (const id of STRATEGY_TYPES) {
      for (const p of STRATEGIES[id].params.filter((x) => x.shownWhen)) {
        const parent = STRATEGIES[id].params.find((x) => x.key === p.shownWhen);
        expect(parent?.kind, `${id}.${p.key}`).toBe("boolean");
      }
    }
  });

  it("blocks export for exactly the strategies the backend refuses", () => {
    const blocked = STRATEGY_TYPES.filter((id) => STRATEGIES[id].exportBlock);
    expect(blocked.sort()).toEqual(["rsi_simple", "vwap_reversion"]);
  });

  it("summarises the first three numeric parameters", () => {
    expect(paramSummary("ma_crossover", DEFAULT_PARAMS.ma_crossover)).toBe(
      "Short window 50 · Long window 200 · Cooldown days 5",
    );
  });
});

describe("strategyName", () => {
  it("maps ids and the API's own casing to display names", () => {
    expect(strategyName("ma_crossover")).toBe("MA Crossover");
    expect(strategyName("MA_Crossover")).toBe("MA Crossover");
    expect(strategyName("greenblatt_weekly")).toBe("Greenblatt Weekly");
  });

  it("falls back to the raw id for unknown strategies", () => {
    expect(strategyName("mystery_strategy")).toBe("mystery_strategy");
  });
});
