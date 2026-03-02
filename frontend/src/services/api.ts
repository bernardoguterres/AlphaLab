import axios from "axios";
import type {
  BacktestRequest,
  BacktestResult,
  CachedTicker,
  CompareRequest,
  CompareResponse,
  FetchDataResponse,
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
