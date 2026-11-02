import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { errorMessage, exportStrategy } from "@/services/api";
import { downloadBlob, isoDate } from "@/utils/download";

interface ExportButtonProps {
  backtestId: string;
  strategy: string;
  ticker: string;
  variant?: "default" | "outline" | "link";
  size?: "default" | "sm";
  label?: string;
}

export function ExportButton({ backtestId, strategy, ticker, variant = "outline", size = "sm", label = "Export to AlphaLive" }: ExportButtonProps) {
  const [busy, setBusy] = useState(false);

  const handleExport = async () => {
    setBusy(true);
    try {
      const filename = `${strategy}_${ticker}_${isoDate().split("-").join("")}.json`;
      downloadBlob(await exportStrategy(backtestId), filename);
      toast.success(`Saved ${filename}`);
    } catch (error) {
      toast.error("Export failed", { description: errorMessage(error, "Unknown error") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant={variant}
      size={size}
      onClick={handleExport}
      disabled={busy || !backtestId}
      aria-label={`Export ${ticker} ${strategy} to AlphaLive`}
    >
      {busy ? "Exporting…" : label}
    </Button>
  );
}
