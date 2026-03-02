import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon?: React.ReactNode;
  colorClass?: string;
  className?: string;
}

export function MetricCard({ label, value, subValue, icon, colorClass, className }: MetricCardProps) {
  return (
    <div className={cn("card-elevated p-4 flex flex-col gap-1", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</span>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <span className={cn("font-mono-numbers text-2xl font-bold", colorClass)}>{value}</span>
      {subValue && (
        <span className="text-xs text-muted-foreground font-mono-numbers">{subValue}</span>
      )}
    </div>
  );
}
