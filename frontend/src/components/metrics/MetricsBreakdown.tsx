import type { BacktestMetrics } from "@/types";
import { KeyValue, KeyValueList } from "@/components/ui/key-value";
import { formatCurrency, formatNumber, formatPercent } from "@/utils/formatters";

/** `false` marks a metric the backend did not send for this run. */
type Row = [label: string, value: string] | false;

function groups(m: BacktestMetrics): [title: string, rows: Row[]][] {
  const rf = m.assumptions?.risk_free_rate_pct ?? 4;
  return [
    [
      "Returns",
      [
        ["Total return", formatPercent(m.returns.total_return_pct)],
        ["CAGR", formatPercent(m.returns.cagr_pct)],
        ["Mean daily return", formatPercent(m.returns.mean_daily_return, 4)],
        ["Skewness", formatNumber(m.returns.skewness)],
        ["Kurtosis", formatNumber(m.returns.kurtosis)],
      ],
    ],
    [
      "Risk",
      [
        ["Volatility (annual)", formatPercent(m.risk.volatility_annual_pct, 2, false)],
        [`Sharpe (vs ${rf}% risk-free)`, formatNumber(m.risk.sharpe_ratio)],
        m.risk.sharpe_ratio_zero_rf !== undefined && ["Sharpe (0% hurdle)", formatNumber(m.risk.sharpe_ratio_zero_rf)],
        ["Sortino", formatNumber(m.risk.sortino_ratio)],
        ["Calmar", formatNumber(m.risk.calmar_ratio)],
        ["VaR 95%", formatPercent(m.risk.var_95_pct)],
        ["CVaR 95%", formatPercent(m.risk.cvar_95_pct)],
        m.assumptions?.average_exposure_pct !== undefined && [
          "Average exposure",
          formatPercent(m.assumptions.average_exposure_pct, 2, false),
        ],
      ],
    ],
    [
      "Drawdown",
      [
        ["Max drawdown", formatPercent(m.drawdown.max_drawdown_pct)],
        ["Average drawdown", formatPercent(m.drawdown.avg_drawdown_pct)],
        ["Longest drawdown (days)", formatNumber(m.drawdown.max_drawdown_duration_days, 0)],
        ["Recovery (days)", formatNumber(m.drawdown.recovery_days, 0)],
      ],
    ],
    [
      "Trades",
      [
        // win_rate is a 0-1 fraction from the backend's _trade_metrics().
        ["Win rate", formatPercent(m.trades.win_rate * 100, 2, false)],
        ["Average win", formatCurrency(m.trades.avg_win)],
        ["Average loss", formatCurrency(m.trades.avg_loss)],
        ["Profit factor", formatNumber(m.trades.profit_factor)],
        ["Expectancy", formatCurrency(m.trades.expectancy)],
        ["Best trade", formatCurrency(m.trades.best_trade)],
        ["Worst trade", formatCurrency(m.trades.worst_trade)],
      ],
    ],
    [
      "Consistency",
      [
        ["Profitable months", formatPercent(m.consistency.profitable_months_pct, 2, false)],
        ["Longest win streak", formatNumber(m.consistency.longest_win_streak, 0)],
        ["Longest loss streak", formatNumber(m.consistency.longest_loss_streak, 0)],
        ["Ulcer index", formatNumber(m.consistency.ulcer_index)],
      ],
    ],
    [
      "Against buy & hold",
      [
        ["Beta", formatNumber(m.vs_benchmark.beta)],
        ["Alpha (annual)", formatPercent(m.vs_benchmark.alpha_annual_pct)],
        ["Active-return p-value", formatNumber(m.vs_benchmark.active_return_p_value, 4)],
        ["Tracking error", formatPercent(m.vs_benchmark.tracking_error_pct, 2, false)],
        ["Information ratio", formatNumber(m.vs_benchmark.information_ratio)],
        ["Up capture", formatPercent(m.vs_benchmark.up_capture_pct, 2, false)],
        ["Down capture", formatPercent(m.vs_benchmark.down_capture_pct, 2, false)],
      ],
    ],
  ];
}

/** Every metric the backend returns, grouped, on one screen. */
export function MetricsBreakdown({ metrics }: { metrics: BacktestMetrics }) {
  return (
    <div className="grid gap-x-10 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
      {groups(metrics).map(([title, rows]) => (
        <div key={title}>
          <h3 className="mb-1 text-2xs text-muted-foreground">{title}</h3>
          <KeyValueList>
            {rows.map((row) => row && <KeyValue key={row[0]} label={row[0]} value={row[1]} />)}
          </KeyValueList>
        </div>
      ))}
      {metrics.assumptions && (
        <p className="text-2xs leading-relaxed text-muted-foreground md:col-span-2 xl:col-span-3">
          Uninvested cash earns {metrics.assumptions.cash_return_pct}%. The risk-free Sharpe charges the hurdle on all
          capital, including cash that was never invested; the 0% hurdle figure is a separate modelling choice, not a
          correction.
        </p>
      )}
    </div>
  );
}
