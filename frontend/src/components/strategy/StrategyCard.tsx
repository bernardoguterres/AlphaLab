import { type LucideIcon, ChevronRight, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/status-badge";
import { SparklinePlaceholder } from "@/components/ui/sparkline-placeholder";
import { STRATEGY_ACCENT_GRADIENT } from "@/utils/strategyMeta";

interface StrategyCardProps {
  name: string;
  category: string;
  icon: LucideIcon;
  accentClass: string;
  count: number;
  available?: boolean;
  onClick?: () => void;
  /** Best total-return % achieved by this strategy across saved backtests. Omit if count is 0. */
  bestReturn?: number;
  /** Average Sharpe ratio across saved backtests for this strategy. Omit if count is 0. */
  avgSharpe?: number;
  /** Chronological equity/return series from real backtest history. Omit if there's no run data. */
  sparklineData?: number[];
  featured?: boolean;
  className?: string;
}

export function StrategyCard({
  name,
  category,
  icon: Icon,
  accentClass,
  count,
  available = true,
  onClick,
  bestReturn,
  avgSharpe,
  sparklineData,
  featured,
  className,
}: StrategyCardProps) {
  const gradient = STRATEGY_ACCENT_GRADIENT[accentClass] ?? "from-primary to-lab-deep";
  const hasData = count > 0 && !!sparklineData && sparklineData.length >= 2;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative text-left rounded-xl border overflow-hidden transition-all duration-200",
        featured ? "border-warning/25 bg-gradient-to-b from-warning/[0.05] to-card/50" : "border-border/70 bg-card/50",
        "hover:border-primary/30 hover:-translate-y-[3px] hover:shadow-[0_20px_44px_-16px_hsl(var(--primary)/0.32)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        featured ? "p-5 sm:p-6" : "p-4",
        className
      )}
    >
      <div className={cn("absolute inset-x-0 top-0 h-[3px] bg-current opacity-60 group-hover:opacity-100 transition-opacity", accentClass)} />
      <div className={cn("glow-blob h-28 w-28 -top-12 -right-12 opacity-0 group-hover:opacity-25 transition-opacity duration-300", accentClass)} style={{ backgroundColor: "currentColor" }} />

      {featured && (
        <div className="flex items-center gap-1.5 mb-4 relative">
          <div className="flex items-center gap-1 rounded-full bg-warning/15 border border-warning/25 px-2 py-0.5">
            <Star className="h-3 w-3 fill-warning text-warning" />
            <span className="text-[10px] font-bold text-warning uppercase tracking-widest">Top Performer</span>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-3.5 relative">
        <div
          className={cn(
            "rounded-xl bg-gradient-to-br shadow-lg flex items-center justify-center text-white transition-transform group-hover:scale-105",
            gradient,
            featured ? "h-11 w-11" : "h-9 w-9"
          )}
        >
          <Icon className={featured ? "h-5 w-5" : "h-4 w-4"} />
        </div>
        <StatusBadge label={available ? "Available" : "Unavailable"} tone={available ? "gain" : "neutral"} dot className="normal-case tracking-normal text-[10px] px-2 py-0.5" />
      </div>

      <div className="flex items-center gap-1 relative">
        <p className={cn("font-bold tracking-tight truncate", featured ? "text-lg" : "text-sm")}>{name}</p>
        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/0 group-hover:text-muted-foreground/60 -translate-x-1 group-hover:translate-x-0 transition-all shrink-0" />
      </div>
      <span className="inline-block text-[10px] font-medium text-muted-foreground/80 bg-secondary/50 rounded-full px-2 py-0.5 mt-1.5 relative">
        {category}
      </span>

      <div className={cn("relative mt-4 rounded-lg border border-border/40", hasData && "chart-grid-bg", featured ? "h-20 px-1" : "h-12 px-0.5")}>
        {hasData ? (
          <SparklinePlaceholder data={sparklineData!} className={cn("w-full h-full", accentClass)} strokeClassName={accentClass} height={featured ? 80 : 48} />
        ) : (
          <div className="flex items-center justify-center h-full">
            <span className="text-[10px] text-muted-foreground/50">
              {count > 0 ? "Not enough runs for a trend" : "Not tested yet"}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 mt-4 pt-3.5 border-t border-border/50 relative">
        <div>
          <p className="label-caps">Best Return</p>
          <p className={cn("font-mono-numbers font-bold mt-0.5", featured ? "text-base" : "text-xs", bestReturn != null ? (bestReturn >= 0 ? "text-gain" : "text-loss") : "text-muted-foreground/50")}>
            {bestReturn != null ? `${bestReturn >= 0 ? "+" : ""}${bestReturn.toFixed(1)}%` : "—"}
          </p>
        </div>
        <div className="border-x border-border/40 px-2">
          <p className="label-caps">Avg Sharpe</p>
          <p className={cn("font-mono-numbers font-bold mt-0.5", featured ? "text-base" : "text-xs", avgSharpe == null && "text-muted-foreground/50")}>
            {avgSharpe != null ? avgSharpe.toFixed(2) : "—"}
          </p>
        </div>
        <div className="pl-2">
          <p className="label-caps">Runs</p>
          <p className={cn("font-mono-numbers font-bold mt-0.5", featured ? "text-base" : "text-xs")}>{count}</p>
        </div>
      </div>
    </button>
  );
}
