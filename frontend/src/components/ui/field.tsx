import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

interface FieldProps {
  label: string;
  htmlFor?: string;
  hint?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

/** A form control with its label above and an optional hint below. */
export function Field({ label, htmlFor, hint, className, children }: FieldProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <Label htmlFor={htmlFor} className="text-2xs font-normal text-muted-foreground">
        {label}
      </Label>
      {children}
      {hint && <p className="text-2xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
