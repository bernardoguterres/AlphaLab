import type { BacktestResult } from "@/types";
import { ExportButton } from "@/components/export/ExportButton";
import { Notice } from "@/components/ui/notice";
import { Section } from "@/components/ui/section";
import { formatDate } from "@/utils/formatters";
import { strategySpec } from "@/utils/strategies";

/** Why the server would refuse to export this run, if it would. */
function exportRefusal(result: BacktestResult, strategy: string): { title: string; reason: string } | null {
  const block = strategySpec(strategy)?.exportBlock;
  if (block) return { title: block.label, reason: block.reason };

  // AlphaLive has no drawdown halt, so only a halt-free run behaves the same live.
  const halt = result.drawdown_halt;
  if (halt && halt.threshold_pct !== null) {
    const triggered = halt.halted && halt.halted_at ? `, triggered ${formatDate(halt.halted_at)}` : "";
    return {
      title: "Drawdown halt is not supported by AlphaLive",
      reason: `This run blocked new entries after a ${halt.threshold_pct}% drawdown${triggered}. Re-run with the halt off to export.`,
    };
  }
  return null;
}

interface ExportPanelProps {
  result: BacktestResult | null;
  ticker: string;
  strategy: string;
}

export function ExportPanel({ result, ticker, strategy }: ExportPanelProps) {
  const refusal = result && exportRefusal(result, strategy);

  return (
    <Section title="AlphaLive export">
      {!result ? (
        <p className="text-[13px] text-muted-foreground">Run a backtest to check whether it can be exported.</p>
      ) : refusal ? (
        <Notice tone="loss" title={refusal.title}>
          {refusal.reason}
        </Notice>
      ) : (
        <div className="space-y-3 text-[13px]">
          <p className="text-muted-foreground">
            The simulated strategy, parameters and risk settings fit AlphaLive's schema. Exportable is not the same as
            validated: one in-sample backtest is not evidence of an edge.
          </p>
          <ExportButton backtestId={result.backtest_id} strategy={strategy} ticker={ticker} variant="default" />
        </div>
      )}
    </Section>
  );
}
