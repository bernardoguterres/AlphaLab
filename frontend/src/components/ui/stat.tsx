import { cn } from "@/lib/utils";

/** A row of headline figures. Collapses to two columns on narrow screens. */
export function StatGrid({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <dl className={cn("grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:auto-cols-fr lg:grid-flow-col lg:grid-cols-none", className)}>
      {children}
    </dl>
  );
}

interface StatProps {
  label: string;
  value: React.ReactNode;
  /** Text colour class for the value, e.g. from pnlColor(). */
  tone?: string;
  hint?: React.ReactNode;
}

export function Stat({ label, value, tone, hint }: StatProps) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs text-muted-foreground">{label}</dt>
      <dd className={cn("num mt-1 whitespace-nowrap text-lg leading-tight", tone)}>{value}</dd>
      {hint && <dd className="mt-0.5 truncate text-2xs text-muted-foreground">{hint}</dd>}
    </div>
  );
}
