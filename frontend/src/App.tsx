import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "@/components/layout/Sidebar";
import { useBacktestStore } from "@/stores/backtestStore";
import { checkHealth } from "@/services/api";
import Dashboard from "./pages/Dashboard";
import Backtest from "./pages/Backtest";
import Compare from "./pages/Compare";
import DataManager from "./pages/DataManager";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

const HEALTH_POLL_MS = 30_000;

function useBackendHealth() {
  const { setBackendOnline, refreshCachedTickers } = useBacktestStore();

  useEffect(() => {
    const check = () =>
      checkHealth().then(
        () => {
          setBackendOnline(true);
          return refreshCachedTickers();
        },
        () => setBackendOnline(false),
      );
    check();
    const id = window.setInterval(check, HEALTH_POLL_MS);
    return () => window.clearInterval(id);
  }, [setBackendOnline, refreshCachedTickers]);
}

export default function App() {
  useBackendHealth();

  return (
    <BrowserRouter>
      <Toaster />
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar />
        <main className="min-w-0 flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/data" element={<DataManager />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
