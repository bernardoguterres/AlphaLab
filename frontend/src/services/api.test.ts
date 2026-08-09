import { describe, it, expect, vi, beforeEach } from "vitest";

// Regression test: the shared axios instance had no response interceptor,
// so any non-2xx API error (missing credentials, validation failures,
// etc.) surfaced to callers as axios's generic "Request failed with
// status code 400" instead of the backend's real {"message": "..."}
// body - even though every Flask error response includes one. Every
// toast.error(err.message) across the app (Settings' Test Telegram/Alpaca
// Connection buttons, backtest error handling, etc.) inherited this,
// making real failures undebuggable from the UI. Fixed by adding a
// response interceptor that rewrites error.message from
// error.response.data.message when present.

let capturedErrorInterceptor:
  | ((error: unknown) => Promise<never>)
  | undefined;

vi.mock("axios", () => {
  const mockInstance = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      response: {
        use: vi.fn((_onFulfilled: unknown, onRejected: (error: unknown) => Promise<never>) => {
          capturedErrorInterceptor = onRejected;
        }),
      },
    },
  };
  return {
    default: {
      create: vi.fn(() => mockInstance),
    },
  };
});

describe("api response interceptor", () => {
  beforeEach(() => {
    capturedErrorInterceptor = undefined;
    vi.resetModules();
  });

  it("rewrites error.message to the backend's message field when present", async () => {
    await import("./api");
    expect(capturedErrorInterceptor).toBeDefined();

    const axiosError = {
      message: "Request failed with status code 400",
      response: {
        status: 400,
        data: {
          status: "error",
          message: "TELEGRAM_BOT_TOKEN environment variable not set",
        },
      },
    };

    await expect(capturedErrorInterceptor!(axiosError)).rejects.toBe(axiosError);
    expect(axiosError.message).toBe("TELEGRAM_BOT_TOKEN environment variable not set");
  });

  it("leaves error.message alone when the backend sent no message field", async () => {
    await import("./api");
    expect(capturedErrorInterceptor).toBeDefined();

    const networkError = {
      message: "Network Error",
      response: undefined,
    };

    await expect(capturedErrorInterceptor!(networkError)).rejects.toBe(networkError);
    expect(networkError.message).toBe("Network Error");
  });
});
