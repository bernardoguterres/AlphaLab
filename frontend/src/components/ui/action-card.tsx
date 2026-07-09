import { type LucideIcon, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

type ActionTone = "primary" | "cyan" | "violet" | "gain";

interface ActionCardProps {
  icon: LucideIcon;
  label: string;
  description: string;
  onClick?: () => void;
  className?: string;
  compact?: boolean;
  tone?: ActionTone;
  featured?: boolean;
}

const TONE_GRADIENT: Record<ActionTone, string> = {
  primary: "from-primary to-lab-deep",
  cyan: "from-lab-secondary to-primary",
  violet: "from-violet-500 to-primary",
  gain: "from-gain to-lab-secondary",
};

export function ActionCard({ icon: Icon, label, description, onClick, className, compact, tone = "primary", featured }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex items-start gap-3 rounded-xl border border-border/70 bg-card/40 text-left transition-all overflow-hidden",
        "hover:border-primary/40 hover:bg-secondary/40 hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-12px_hsl(var(--primary)/0.25)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        featured ? "p-5 flex-col items-start gap-4" : compact ? "p-3" : "p-3.5",
        className
      )}
    >
      <div
        className={cn(
          "rounded-lg bg-gradient-to-br shrink-0 flex items-center justify-center text-white shadow-lg transition-transform group-hover:scale-105",
          TONE_GRADIENT[tone],
          featured ? "h-10 w-10" : compact ? "h-7 w-7" : "h-9 w-9"
        )}
      >
        <Icon className={featured ? "h-5 w-5" : compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className={cn("font-semibold", featured ? "text-base" : compact ? "text-xs" : "text-sm")}>{label}</span>
          {!featured && (
            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/0 group-hover:text-primary/70 -translate-x-1 group-hover:translate-x-0 transition-all shrink-0" />
          )}
        </div>
        <p className={cn("text-muted-foreground leading-snug mt-0.5", featured ? "text-xs" : compact ? "text-[10px]" : "text-[11px]")}>
          {description}
        </p>
        {featured && (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary mt-3 group-hover:gap-1.5 transition-all">
            Get started <ArrowRight className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
    </button>
  );
}
