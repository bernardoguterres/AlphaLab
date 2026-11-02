import { cn } from "@/lib/utils";

type Tone = "neutral" | "warning" | "loss" | "gain";

const TONE: Record<Tone, string> = {
  neutral: "border-border",
  warning: "border-warning",
  loss: "border-loss",
  gain: "border-gain",
};

interface NoticeProps {
  title: string;
  tone?: Tone;
  className?: string;
  children?: React.ReactNode;
}

/** An inline message marked by a coloured rule rather than a filled box. */
export function Notice({ title, tone = "neutral", className, children }: NoticeProps) {
  return (
    <div role={tone === "loss" ? "alert" : undefined} className={cn("border-l-2 py-0.5 pl-3 text-[13px]", TONE[tone], className)}>
      <p>{title}</p>
      {children && <div className="mt-0.5 text-muted-foreground">{children}</div>}
    </div>
  );
}
