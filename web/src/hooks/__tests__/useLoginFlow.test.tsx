import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useLoginFlow } from "../useLoginFlow";
import { makeStore } from "@/store/store";
import { Provider } from "react-redux";
import type { ReactNode } from "react";

function wrapper({ children }: { children: ReactNode }) {
  return <Provider store={makeStore()}>{children}</Provider>;
}

function okResponse(body?: unknown) {
  return new Response(body ? JSON.stringify(body) : null, {
    status: body ? 200 : 204,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, detail: string) {
  return Response.json(
    { detail },
    {
      status,
      headers: { "Content-Type": "application/json" },
    },
  );
}

const userResponse = {
  id: "test-id",
  email: "test@test.com",
  phone: "0912345678",
  full_name: "Test User",
  username: null,
  role: "seller",
  is_active: true,
  avatar_url: null,
  address: null,
  location_lat: null,
  location_lng: null,
  preferred_language: "ar",
  created_at: "2026-01-01T00:00:00Z",
};

function requestUrl(url: RequestInfo | URL): string {
  if (typeof url === "string") {
    return url;
  }
  return url instanceof URL ? url.toString() : url.url;
}

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const urlStr = requestUrl(url);

    if (urlStr.includes("/auth/send-otp")) {
      return okResponse();
    }
    if (urlStr.includes("/auth/verify-otp")) {
      return okResponse({
        access_token: "test-token",
        refresh_token: "test-refresh",
        token_type: "bearer",
      });
    }
    if (urlStr.includes("/users/me")) {
      return okResponse({ success: true, data: userResponse });
    }
    return errorResponse(404, "Not found");
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useLoginFlow", () => {
  it("should return initial step as phone", () => {
    const { result } = renderHook(() => useLoginFlow(), { wrapper });
    expect(result.current.step).toBe("phone");
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("should transition to otp after sendOtp", async () => {
    const { result } = renderHook(() => useLoginFlow(), { wrapper });

    await act(async () => {
      result.current.sendOtp("0912345678");
    });

    await waitFor(() => {
      expect(result.current.step).toBe("otp");
    });
  });

  it("should authenticate after verifyOtp with correct code", async () => {
    const { result } = renderHook(() => useLoginFlow(), { wrapper });

    await act(async () => {
      result.current.sendOtp("0912345678");
    });
    await waitFor(() => {
      expect(result.current.step).toBe("otp");
    });

    await act(async () => {
      result.current.verifyOtp("1234");
    });
    await waitFor(() => {
      expect(result.current.step).toBe("authenticated");
    });
  });

  it("should set error for short phone", async () => {
    const mockFetch = globalThis.fetch as ReturnType<typeof vi.fn>;
    mockFetch.mockImplementation(async (url: RequestInfo | URL) => {
      const urlStr = requestUrl(url);
      if (urlStr.includes("/auth/send-otp")) {
        return errorResponse(422, "رقم الهاتف غير صحيح");
      }
      if (urlStr.includes("/auth/verify-otp")) {
        return okResponse({
          access_token: "test-token",
          refresh_token: "test-refresh",
          token_type: "bearer",
        });
      }
      if (urlStr.includes("/users/me")) {
        return okResponse({ success: true, data: userResponse });
      }
      return errorResponse(404, "Not found");
    });

    const { result } = renderHook(() => useLoginFlow(), { wrapper });

    await act(async () => {
      result.current.sendOtp("12");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("رقم الهاتف غير صحيح");
    });
  });

  it("should clear error", async () => {
    const mockFetch = globalThis.fetch as ReturnType<typeof vi.fn>;
    mockFetch.mockImplementation(async (url: RequestInfo | URL) => {
      const urlStr = requestUrl(url);
      if (urlStr.includes("/auth/send-otp")) {
        return errorResponse(422, "رقم الهاتف غير صحيح");
      }
      if (urlStr.includes("/auth/verify-otp")) {
        return okResponse({
          access_token: "test-token",
          refresh_token: "test-refresh",
          token_type: "bearer",
        });
      }
      if (urlStr.includes("/users/me")) {
        return okResponse({ success: true, data: userResponse });
      }
      return errorResponse(404, "Not found");
    });

    const { result } = renderHook(() => useLoginFlow(), { wrapper });

    await act(async () => {
      result.current.sendOtp("12");
    });
    await waitFor(() => {
      expect(result.current.error).toBe("رقم الهاتف غير صحيح");
    });

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });
});
