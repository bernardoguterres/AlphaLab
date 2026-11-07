import type { PositionSizing, RiskSettings } from "@/types";
import { SIZINGS } from "@/utils/defaults";

/** One-line summaries of what a run is simulated with, for collapsed panels and result headers. */

export function riskSummary(s: RiskSettings): string {
  const trailing = s.trailing_stop_enabled ? `trailing ${s.trailing_stop_pct}%` : "no trailing stop";
  return `Position ${s.max_position_size_pct}% · stop ${s.stop_loss_pct}% · target ${s.take_profit_pct}% · ${trailing}`;
}

/** The risk summary plus sizing and the drawdown halt: everything a run was simulated with. */
export function runSettingsSummary(risk: RiskSettings, sizing: PositionSizing, drawdownHalt: boolean): string {
  const sizingLabel = SIZINGS.find((x) => x.value === sizing)?.label.toLowerCase() ?? sizing;
  return `${riskSummary(risk)} · ${sizingLabel} · ${drawdownHalt ? "halt after a 10% drawdown" : "no drawdown halt"}`;
}
