import type { MonteCarloResult } from "@/types";
import { Section } from "@/components/ui/section";
import { Stat, StatGrid } from "@/components/ui/stat";
import { formatCurrency, formatPercent } from "@/utils/formatters";

/** Every figure except prob_profit is a final portfolio value in dollars. */
export function MonteCarloSummary({ mc }: { mc: MonteCarloResult }) {
  const method = [`${mc.runs} resamples`, mc.seed !== undefined && `seed ${mc.seed}`, mc.block_length && `${mc.block_length}-bar blocks`]
    .filter(Boolean)
    .join(", ");

  return (
    <Section title="Monte Carlo" aside={method}>
      <StatGrid className="lg:grid-flow-row lg:grid-cols-4">
        <Stat label="5th percentile" value={formatCurrency(mc.percentile_5)} />
        <Stat label="Median" value={formatCurrency(mc.median_final_value)} />
        <Stat label="95th percentile" value={formatCurrency(mc.percentile_95)} />
        <Stat label="Probability of profit" value={formatPercent(mc.prob_profit * 100, 2, false)} />
        <Stat label="Minimum" value={formatCurrency(mc.min_final_value)} />
        <Stat label="Mean" value={formatCurrency(mc.mean_final_value)} />
        <Stat label="Maximum" value={formatCurrency(mc.max_final_value)} />
        <Stat label="Standard deviation" value={formatCurrency(mc.std_final_value)} />
      </StatGrid>
      <p className="mt-3 text-2xs text-muted-foreground">
        Block-bootstrap resampling of this run's own per-bar returns. It shows sampling variation in this return series,
        not parameter, regime or execution uncertainty.
      </p>
    </Section>
  );
}
