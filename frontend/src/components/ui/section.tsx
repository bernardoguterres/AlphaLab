import { cn } from "@/lib/utils";

interface SectionProps {
  title: string;
  /** Right-aligned content in the heading row: a count, a control, an action. */
  aside?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

/** A titled block separated from its neighbours by a rule, not a card. */
export function Section({ title, aside, className, children }: SectionProps) {
  return (
    <section className={cn("border-t border-border pt-3", className)}>
      <header className="mb-3 flex min-h-8 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-[13px] font-medium">{title}</h2>
        {aside && <div className="flex items-center gap-3 text-2xs text-muted-foreground">{aside}</div>}
      </header>
      {children}
    </section>
  );
}
