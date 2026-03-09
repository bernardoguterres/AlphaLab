import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Header } from "@/components/layout/Header";
import { useBacktestStore } from "@/stores/backtestStore";
import { checkHealth, getAvailableData } from "@/services/api";
import Dashboard from "./pages/Dashboard";
import Backtest from "./pages/Backtest";
import Compare from "./pages/Compare";
import DataManager from "./pages/DataManager";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

function AppContent() {
  const { setBackendOnline, setCachedTickers } = useBacktestStore();

  useEffect(() => {
    const check = async () => {
      try {
        await checkHealth();
        setBackendOnline(true);
        try {
          const tickers = await getAvailableData();
          setCachedTickers(Array.isArray(tickers) ? tickers : []);
        } catch {}
      } catch {
        setBackendOnline(false);
      }
    };
    check();
    const interval = window.setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/data" element={<DataManager />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
