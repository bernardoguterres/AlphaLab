import { useState } from "react";
import type { BacktestHistoryItem } from "@/types";
import { BENCHMARK_COLOR, SERIES_COLORS } from "@/components/charts/chartTheme";
import { EquityChart } from "@/components/charts/EquityChart";
import { Segmented } from "@/components/ui/segmented";
import { Stat, StatGrid } from "@/components/ui/stat";
import { Swatch } from "@/components/ui/swatch";
import { formatCurrency, formatDate, formatNumber, formatPercent, pnlColor } from "@/utils/formatters";
import { CHART_RANGES, sliceByRange, type ChartRange } from "@/utils/series";
import { strategyName } from "@/utils/strategies";

interface RunSummaryProps {
  run: BacktestHistoryItem;
  /** Shown next to the title, e.g. an export or "open" action. */
  actions?: React.ReactNode;
}

/** Title, headline figures and equity curve for one backtest run. */
export function RunSummary({ run, actions }: RunSummaryProps) {
  const [range, setRange] = useState<ChartRange>("All");
  const { result } = run;
  const curve = result.equity_curve;
  const benchmark = result.benchmark;
  const excess = benchmark ? result.total_return_pct - benchmark.total_return_pct : null;
  const period = curve.length > 1 ? `${formatDate(curve[0].date)} – ${formatDate(curve[curve.length - 1].date)}` : null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg">
            {run.ticker} <span className="text-muted-foreground">·</span> {strategyName(run.strategy)}
          </h2>
          <p className="num mt-1 text-2xs text-muted-foreground">
            {[period, `${formatCurrency(result.initial_capital)} start`].filter(Boolean).join(" · ")}
          </p>
        </div>
        {actions}
      </header>

      <StatGrid>
        <Stat label="Net return" value={formatPercent(result.total_return_pct)} tone={pnlColor(result.total_return_pct)} />
        {excess !== null && <Stat label="vs buy & hold" value={`${excess >= 0 ? "+" : ""}${excess.toFixed(1)} pt`} tone={pnlColor(excess)} />}
        <Stat label="Sharpe" value={formatNumber(result.metrics.risk.sharpe_ratio)} />
        <Stat label="Max drawdown" value={formatPercent(result.metrics.drawdown.max_drawdown_pct)} />
        <Stat label="Win rate" value={formatPercent(result.metrics.trades.win_rate * 100, 1, false)} />
        <Stat label="Profit factor" value={formatNumber(result.metrics.trades.profit_factor)} />
        <Stat label="Trades" value={result.total_trades} />
      </StatGrid>

      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3 text-2xs text-muted-foreground">
          <div className="flex gap-4">
            <span>
              <Swatch color={SERIES_COLORS[0]} />
              Strategy {formatCurrency(result.final_value)}
            </span>
            {benchmark && (
              <span>
                <Swatch color={BENCHMARK_COLOR} />
                Buy & hold {formatPercent(benchmark.total_return_pct)}
              </span>
            )}
          </div>
          <Segmented label="Chart range" options={CHART_RANGES} value={range} onChange={setRange} />
        </div>
        <EquityChart data={sliceByRange(curve, range)} benchmarkData={benchmark ? sliceByRange(benchmark.equity_curve, range) : undefined} />
      </div>
    </div>
  );
}
