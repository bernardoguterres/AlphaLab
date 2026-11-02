import type { RiskSettings } from "@/types";
import { Section } from "@/components/ui/section";
import { cn } from "@/lib/utils";
import { qualityLevel, type QualityLevel } from "@/utils/formatters";

type Status = "pass" | "check" | "fail" | "open";

const STATUS: Record<Status, { label: string; className: string }> = {
  pass: { label: "Pass", className: "text-gain" },
  check: { label: "Check", className: "text-warning" },
  fail: { label: "Low", className: "text-loss" },
  open: { label: "Open", className: "text-muted-foreground" },
};

const QUALITY_STATUS: Record<QualityLevel, Status> = { good: "pass", fair: "check", poor: "fail" };

interface ResearchChecksProps {
  hasResult: boolean;
  /** Quality score fetched for exactly the submitted ticker and window, else null. */
  qualityScore: number | null;
  riskSettings: RiskSettings;
}

export function ResearchChecks({ hasResult, qualityScore, riskSettings }: ResearchChecksProps) {
  // These three hold by construction for any completed run.
  const structural: Status = hasResult ? "pass" : "open";
  const quality: Status = !hasResult || qualityScore === null ? "open" : QUALITY_STATUS[qualityLevel(qualityScore)];

  const checks: { title: string; detail: string; status: Status }[] = [
    {
      title: "Next-bar execution",
      detail: "A signal on bar N fills at bar N+1's open, so there is no look-ahead.",
      status: structural,
    },
    {
      title: "Transaction costs",
      detail: `$${riskSettings.commission_per_trade.toFixed(2)} commission per side, plus the backend's default slippage.`,
      status: structural,
    },
    {
      title: "Data quality",
      detail:
        qualityScore === null
          ? "Not scored for this window. Use Fetch data to score it."
          : `${(qualityScore * 100).toFixed(0)}% quality score for the fetched window.`,
      status: quality,
    },
    {
      title: "Position limits",
      detail: `At most ${riskSettings.max_position_size_pct}% per position and ${riskSettings.max_open_positions} open at once.`,
      status: structural,
    },
    {
      title: "Walk-forward validation",
      detail: "Not part of a single backtest. Use Optimize with walk-forward, or the offline research scripts.",
      status: "open",
    },
  ];

  const passed = checks.filter((c) => c.status === "pass").length;

  return (
    <Section title="Research checks" aside={hasResult ? `${passed} of ${checks.length} pass` : "Run a backtest"}>
      <ul className="divide-y divide-border/70">
        {checks.map((c) => (
          <li key={c.title} className="flex gap-4 py-2 text-[13px]">
            <span className={cn("w-10 shrink-0 text-2xs leading-5", STATUS[c.status].className)}>{STATUS[c.status].label}</span>
            <div className="min-w-0">
              <p>{c.title}</p>
              <p className="mt-0.5 text-2xs text-muted-foreground">{c.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}
