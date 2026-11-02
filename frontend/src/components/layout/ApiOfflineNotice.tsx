import { Notice } from "@/components/ui/notice";
import { useBacktestStore } from "@/stores/backtestStore";

export function ApiOfflineNotice() {
  const online = useBacktestStore((s) => s.isBackendOnline);
  if (online !== false) return null;
  return (
    <Notice tone="loss" title="The API is not responding">
      Start the Flask server with <span className="num text-foreground">python run.py</span> in backend/. It listens on port 5050.
    </Notice>
  );
}
