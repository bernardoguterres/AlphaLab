import { cn } from "@/lib/utils";

type Align = "left" | "right" | "center";

const ALIGN: Record<Align, string> = { left: "text-left", right: "text-right", center: "text-center" };

export function Table({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-[13px]">{children}</table>
    </div>
  );
}

interface ThProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  align?: Align;
}

export function Th({ align = "left", className, ...props }: ThProps) {
  return (
    <th
      className={cn(
        "whitespace-nowrap border-b border-border py-2 pr-4 text-2xs font-normal text-muted-foreground last:pr-0",
        ALIGN[align],
        className,
      )}
      {...props}
    />
  );
}

interface TdProps extends React.TdHTMLAttributes<HTMLTableCellElement> {
  align?: Align;
  /** Tabular monospace figures. */
  num?: boolean;
}

export function Td({ align = "left", num, className, ...props }: TdProps) {
  return (
    <td
      className={cn("whitespace-nowrap border-b border-border/60 py-2 pr-4 last:pr-0", ALIGN[align], num && "num", className)}
      {...props}
    />
  );
}
