import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

interface DisclosureProps {
  title: string;
  /** One-line summary of the hidden content, shown while collapsed. */
  summary?: string;
  children: React.ReactNode;
}

export function Disclosure({ title, summary, children }: DisclosureProps) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-t border-border">
      <CollapsibleTrigger className="flex w-full items-baseline gap-3 py-2.5 text-left text-[13px]">
        <span className="w-3 shrink-0 text-muted-foreground" aria-hidden>
          {open ? "−" : "+"}
        </span>
        <span className="shrink-0">{title}</span>
        {summary && !open && <span className="num truncate text-2xs text-muted-foreground">{summary}</span>}
      </CollapsibleTrigger>
      <CollapsibleContent className="pb-5 pl-6">{children}</CollapsibleContent>
    </Collapsible>
  );
}
