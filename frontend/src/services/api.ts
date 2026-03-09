import axios from "axios";
import type {
  BacktestRequest,
  BacktestResult,
  BatchBacktestRequest,
  BatchBacktestResponse,
  CachedTicker,
  CompareRequest,
  CompareResponse,
  FetchDataResponse,
  PortfolioOptimizeRequest,
  PortfolioOptimizeResponse,
  ParameterOptimizeRequest,
  ParameterOptimizeResponse,
  HeatmapRequest,
  HeatmapResponse,
  NotificationSettings,
  NotificationSettingsResponse,
  SaveSettingsResponse,
  TestConnectionResponse,
} from "@/types";

const api = axios.create({
  baseURL: "http://127.0.0.1:5000/api",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const { data } = await api.get("/health");
  return data;
}

export async function fetchData(
  tickers: string[],
  start_date: string,
  end_date: string,
  interval: string = "1d"
): Promise<FetchDataResponse> {
  const { data } = await api.post("/data/fetch", { tickers, start_date, end_date, interval });
  return data;
}

export async function getAvailableData(): Promise<CachedTicker[]> {
  const { data } = await api.get("/data/available");
  return data.data ?? data;
}

export async function runBacktest(request: BacktestRequest): Promise<BacktestResult> {
  const { data } = await api.post("/strategies/backtest", request);
  if (data.status === "error") throw new Error(data.message);
  return data.data ?? data;
}

export async function compareStrategies(request: CompareRequest): Promise<CompareResponse> {
  const { data } = await api.post("/compare", request);
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function exportStrategy(backtest_id: string): Promise<Blob> {
  const response = await api.post(
    "/strategies/export",
    { backtest_id },
    { responseType: "blob" }
  );
  return response.data;
}

export async function runBatchBacktest(request: BatchBacktestRequest): Promise<BatchBacktestResponse> {
  const { data } = await api.post("/strategies/batch-backtest", request, {
    timeout: 300000, // 5 minutes for batch operations
  });
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function optimizePortfolio(request: PortfolioOptimizeRequest): Promise<PortfolioOptimizeResponse> {
  const { data } = await api.post("/portfolio/optimize", request);
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function optimizeParameters(request: ParameterOptimizeRequest): Promise<ParameterOptimizeResponse> {
  const { data } = await api.post("/strategies/optimize", request, {
    timeout: 300000, // 5 minutes for optimization
  });
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function generateHeatmap(request: HeatmapRequest): Promise<HeatmapResponse> {
  const { data } = await api.post("/strategies/optimize/heatmap", request, {
    timeout: 300000, // 5 minutes for heatmap generation
  });
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function getNotificationSettings(): Promise<NotificationSettingsResponse> {
  const { data } = await api.get("/settings/notifications");
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function saveNotificationSettings(settings: NotificationSettings): Promise<SaveSettingsResponse> {
  const { data } = await api.post("/settings/notifications", settings);
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function testTelegramConnection(): Promise<TestConnectionResponse> {
  const { data } = await api.post("/settings/telegram/test");
  if (data.status === "error") throw new Error(data.message);
  return data;
}

export async function testAlpacaConnection(): Promise<TestConnectionResponse> {
  const { data } = await api.post("/settings/alpaca/test");
  if (data.status === "error") throw new Error(data.message);
  return data;
}
