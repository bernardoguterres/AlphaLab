import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  preview?: React.ReactNode;
  className?: string;
  size?: "sm" | "default";
}

export function EmptyState({ icon: Icon, title, description, action, preview, className, size = "default" }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        size === "default" ? "py-12 px-6" : "py-8 px-4",
        className
      )}
    >
      <div className="relative mb-4">
        <span className="absolute inset-0 rounded-2xl bg-primary/25 blur-xl animate-pulse-gain" />
        <span className="absolute inset-0 rounded-2xl bg-lab-secondary/15 blur-2xl" />
        <div className="relative rounded-2xl bg-gradient-to-br from-secondary/80 to-secondary/40 p-3.5 ring-1 ring-border/60">
          <Icon className={cn("text-primary", size === "default" ? "h-6 w-6" : "h-5 w-5")} />
        </div>
      </div>
      <p className={cn("font-semibold text-foreground", size === "default" ? "text-sm" : "text-xs")}>{title}</p>
      {description && (
        <p className={cn("text-muted-foreground/80 mt-1 max-w-sm", size === "default" ? "text-xs" : "text-[11px]")}>
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
      {preview && <div className="mt-6 w-full">{preview}</div>}
    </div>
  );
}
