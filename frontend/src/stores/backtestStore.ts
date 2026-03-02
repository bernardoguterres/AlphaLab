import { create } from "zustand";
import type { BacktestHistoryItem, BacktestResult, CachedTicker } from "@/types";

const HISTORY_KEY = "alphalab_history";

function loadHistory(): BacktestHistoryItem[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(items: BacktestHistoryItem[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
}

interface BacktestStore {
  history: BacktestHistoryItem[];
  cachedTickers: CachedTicker[];
  currentResult: BacktestResult | null;
  isBackendOnline: boolean;
  setCachedTickers: (tickers: CachedTicker[]) => void;
  setCurrentResult: (result: BacktestResult | null) => void;
  setBackendOnline: (online: boolean) => void;
  addToHistory: (item: BacktestHistoryItem) => void;
  clearHistory: () => void;
}

export const useBacktestStore = create<BacktestStore>((set) => ({
  history: loadHistory(),
  cachedTickers: [],
  currentResult: null,
  isBackendOnline: false,
  setCachedTickers: (tickers) => set({ cachedTickers: tickers }),
  setCurrentResult: (result) => set({ currentResult: result }),
  setBackendOnline: (online) => set({ isBackendOnline: online }),
  addToHistory: (item) =>
    set((state) => {
      const history = [item, ...state.history].slice(0, 50);
      saveHistory(history);
      return { history };
    }),
  clearHistory: () => {
    localStorage.removeItem(HISTORY_KEY);
    set({ history: [] });
  },
}));
