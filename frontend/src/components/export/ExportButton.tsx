import { useState } from "react";
import { exportStrategy } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface ExportButtonProps {
  backtestId: string;
  strategyName: string;
  ticker: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
  showLabel?: boolean;
}

export function ExportButton({
  backtestId,
  strategyName,
  ticker,
  variant = "default",
  size = "default",
  showLabel = true,
}: ExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    if (!backtestId) {
      toast.error("No backtest ID available");
      return;
    }

    setIsExporting(true);

    try {
      // Call API to get export JSON
      const blob = await exportStrategy(backtestId);

      // Create filename: {strategy}_{ticker}_{YYYYMMDD}.json
      const date = new Date().toISOString().split("T")[0].replace(/-/g, "");
      const filename = `${strategyName}_${ticker}_${date}.json`;

      // Trigger download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success(`Exported: ${filename}`, {
        description: "Strategy config ready for AlphaLive",
      });
    } catch (error) {
      console.error("Export failed:", error);
      toast.error("Export failed", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Button
      onClick={handleExport}
      disabled={isExporting}
      variant={variant}
      size={size}
      className="gap-2"
    >
      {isExporting ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Download className="h-4 w-4" />
      )}
      {showLabel && (isExporting ? "Exporting..." : "Export to AlphaLive")}
    </Button>
  );
}
