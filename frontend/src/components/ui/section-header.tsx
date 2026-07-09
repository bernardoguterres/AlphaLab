import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  as?: "h1" | "h2" | "h3";
}

export function SectionHeader({ title, description, action, className, as = "h2" }: SectionHeaderProps) {
  const Comp = as;
  const titleSize = as === "h1" ? "text-2xl" : as === "h2" ? "text-base" : "text-sm";
  return (
    <div className={cn("flex items-center justify-between gap-4", className)}>
      <div className="min-w-0">
        <Comp className={cn("font-display font-bold tracking-tight", titleSize)}>{title}</Comp>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
