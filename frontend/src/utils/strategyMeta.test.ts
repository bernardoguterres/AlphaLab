import { describe, it, expect } from "vitest";
import { STRATEGY_META, STRATEGY_ACCENT_GRADIENT } from "./strategyMeta";
import { strategyDisplayName } from "./formatters";

describe("STRATEGY_META", () => {
  const ids = Object.keys(STRATEGY_META);

  it("covers all 9 strategies", () => {
    // 9, not 8, since rsi_simple was registered as its own reachable
    // strategy (audit bug 3.8, 2026-07-14).
    expect(ids).toHaveLength(9);
  });

  it("every strategy has a category, icon, and accent", () => {
    for (const id of ids) {
      const meta = STRATEGY_META[id as keyof typeof STRATEGY_META];
      expect(meta.category, id).toBeTruthy();
      expect(meta.icon, id).toBeTruthy();
      expect(meta.accent, id).toMatch(/^text-/);
    }
  });

  it("every accent has a matching icon-chip gradient", () => {
    // StrategyCard looks the accent up in STRATEGY_ACCENT_GRADIENT - a
    // missing entry renders a chip with no gradient.
    for (const id of ids) {
      const accent = STRATEGY_META[id as keyof typeof STRATEGY_META].accent;
      expect(STRATEGY_ACCENT_GRADIENT[accent], `${id} (${accent})`).toBeTruthy();
    }
  });

  it("every strategy in META has a display name", () => {
    for (const id of ids) {
      expect(strategyDisplayName(id), id).not.toBe(id);
    }
  });
});
