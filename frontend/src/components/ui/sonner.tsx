import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "rounded border border-border bg-surface font-sans text-[13px] text-foreground",
          description: "text-muted-foreground",
        },
      }}
    />
  );
}
