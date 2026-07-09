import { cn } from "@/lib/utils";

type StatusTone = "gain" | "loss" | "warning" | "neutral" | "primary";

interface StatusBadgeProps {
  label: string;
  tone?: StatusTone;
  dot?: boolean;
  pulse?: boolean;
  className?: string;
}

const toneClasses: Record<StatusTone, string> = {
  gain: "bg-gain/10 text-gain border-gain/30",
  loss: "bg-loss/10 text-loss border-loss/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  neutral: "bg-secondary text-muted-foreground border-border",
  primary: "bg-primary/10 text-primary border-primary/30",
};

const dotClasses: Record<StatusTone, string> = {
  gain: "bg-gain",
  loss: "bg-loss",
  warning: "bg-warning",
  neutral: "bg-muted-foreground",
  primary: "bg-primary",
};

export function StatusBadge({ label, tone = "neutral", dot = false, pulse = false, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
        toneClasses[tone],
        className
      )}
    >
      {dot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", dotClasses[tone], pulse && "animate-pulse-gain")} />
      )}
      {label}
    </span>
  );
}
