import { cn } from "@/lib/utils";

export function KeyValueList({ className, children }: { className?: string; children: React.ReactNode }) {
  return <dl className={cn("divide-y divide-border/70", className)}>{children}</dl>;
}

interface KeyValueProps {
  label: React.ReactNode;
  value: React.ReactNode;
  /** Secondary line under the label. */
  note?: React.ReactNode;
  tone?: string;
  /** Render the value in the text face instead of tabular figures. */
  plain?: boolean;
}

export function KeyValue({ label, value, note, tone, plain }: KeyValueProps) {
  return (
    <div className="flex items-baseline justify-between gap-6 py-1.5 text-[13px]">
      <dt className="min-w-0 text-muted-foreground">
        {label}
        {note && <span className="mt-0.5 block text-2xs text-muted-foreground/80">{note}</span>}
      </dt>
      <dd className={cn("shrink-0 text-right", !plain && "num", tone)}>{value}</dd>
    </div>
  );
}
