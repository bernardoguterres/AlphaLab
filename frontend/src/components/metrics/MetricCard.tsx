import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { SparklinePlaceholder } from "@/components/ui/sparkline-placeholder";

type MetricTone = "primary" | "cyan" | "gain" | "warning" | "neutral";

interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon?: React.ReactNode;
  colorClass?: string;
  className?: string;
  accent?: boolean;
  tone?: MetricTone;
  trend?: { direction: "up" | "down" | "flat"; label: string };
  sparkline?: number[];
  featured?: boolean;
}

const TONE_BAR: Record<MetricTone, string> = {
  primary: "from-primary/70 via-primary to-primary/70",
  cyan: "from-lab-secondary/70 via-lab-secondary to-lab-secondary/70",
  gain: "from-gain/70 via-gain to-gain/70",
  warning: "from-warning/70 via-warning to-warning/70",
  neutral: "from-border via-border to-border",
};

const TONE_ICON: Record<MetricTone, string> = {
  primary: "text-primary",
  cyan: "text-lab-secondary",
  gain: "text-gain",
  warning: "text-warning",
  neutral: "text-muted-foreground",
};

const TONE_WASH: Record<MetricTone, string> = {
  primary: "bg-primary",
  cyan: "bg-lab-secondary",
  gain: "bg-gain",
  warning: "bg-warning",
  neutral: "bg-transparent",
};

export function MetricCard({
  label,
  value,
  subValue,
  icon,
  colorClass,
  className,
  accent,
  tone = "neutral",
  trend,
  sparkline,
  featured,
}: MetricCardProps) {
  const TrendIcon = trend?.direction === "up" ? ArrowUpRight : trend?.direction === "down" ? ArrowDownRight : Minus;
  const trendColor = trend?.direction === "up" ? "text-gain" : trend?.direction === "down" ? "text-loss" : "text-muted-foreground";

  return (
    <div
      className={cn(
        "card-elevated relative overflow-hidden group transition-all duration-200",
        "hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-[0_16px_36px_-18px_hsl(var(--primary)/0.35)]",
        featured ? "p-5" : "p-4",
        className
      )}
    >
      {accent && <div className={cn("absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r", TONE_BAR[tone])} />}
      {accent && tone !== "neutral" && (
        <div className={cn("glow-blob h-24 w-24 -top-12 -right-12 opacity-[0.06] group-hover:opacity-[0.1] transition-opacity", TONE_WASH[tone])} />
      )}

      <div className="flex items-center justify-between relative">
        <span className="label-caps">{label}</span>
        {icon && (
          <span
            className={cn(
              "rounded-md bg-secondary/60 p-1.5 transition-all group-hover:bg-secondary group-hover:shadow-[0_0_12px_hsl(var(--primary)/0.2)]",
              TONE_ICON[tone]
            )}
          >
            {icon}
          </span>
        )}
      </div>

      <div className="flex items-end justify-between gap-3 mt-2.5 relative">
        <div className="min-w-0">
          <span className={cn("font-mono-numbers leading-none font-bold tracking-tight block", featured ? "text-[34px]" : "text-[28px]", colorClass)}>
            {value}
          </span>
          {trend && (
            <div className={cn("flex items-center gap-1 mt-1.5 text-xs font-medium", trendColor)}>
              <TrendIcon className="h-3 w-3 shrink-0" />
              <span className="truncate">{trend.label}</span>
            </div>
          )}
          {!trend && subValue && (
            <span className="text-xs text-muted-foreground font-mono-numbers truncate block mt-1.5">{subValue}</span>
          )}
        </div>
        {sparkline && sparkline.length >= 2 && (
          <SparklinePlaceholder
            data={sparkline}
            height={featured ? 52 : 36}
            className={cn("shrink-0", featured ? "w-28 h-[52px]" : "w-20 h-9", TONE_ICON[tone])}
            strokeClassName={TONE_ICON[tone]}
          />
        )}
      </div>
    </div>
  );
}
