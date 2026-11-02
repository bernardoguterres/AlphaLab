import { create } from "zustand";
import { getAvailableData } from "@/services/api";
import type { BacktestHistoryItem, BacktestResult, CachedTicker } from "@/types";

const HISTORY_KEY = "alphalab_history";
const HISTORY_LIMIT = 50;

function loadHistory(): BacktestHistoryItem[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

interface BacktestStore {
  history: BacktestHistoryItem[];
  cachedTickers: CachedTicker[];
  /** The run shown in Backtest: the latest one, or one reopened from history. */
  currentRun: BacktestHistoryItem | null;
  /** null until the first health check answers. */
  isBackendOnline: boolean | null;
  /** Re-reads the cached-dataset listing; keeps the old list if the API is down. */
  refreshCachedTickers: () => Promise<void>;
  setCurrentRun: (run: BacktestHistoryItem | null) => void;
  setBackendOnline: (online: boolean) => void;
  addToHistory: (items: BacktestHistoryItem[]) => void;
}

export const useBacktestStore = create<BacktestStore>((set) => ({
  history: loadHistory(),
  cachedTickers: [],
  currentRun: null,
  isBackendOnline: null,
  refreshCachedTickers: async () => {
    const tickers = await getAvailableData().catch(() => null);
    if (tickers) set({ cachedTickers: tickers });
  },
  setCurrentRun: (run) => set({ currentRun: run }),
  setBackendOnline: (online) => set({ isBackendOnline: online }),
  addToHistory: (items) =>
    set((state) => {
      const history = [...items, ...state.history].slice(0, HISTORY_LIMIT);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
      return { history };
    }),
}));

/** Wraps a finished run with the ticker and strategy that produced it. */
export function historyItem(result: BacktestResult, ticker: string, strategy: string): BacktestHistoryItem {
  return {
    id: result.backtest_id || `${Date.now()}-${strategy}`,
    date: new Date().toISOString(),
    ticker,
    strategy,
    total_return_pct: result.total_return_pct,
    sharpe_ratio: result.metrics.risk.sharpe_ratio,
    max_drawdown: result.metrics.drawdown.max_drawdown_pct,
    total_trades: result.total_trades,
    result,
  };
}
