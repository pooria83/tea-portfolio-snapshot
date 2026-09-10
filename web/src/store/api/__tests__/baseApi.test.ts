import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Reducer, UnknownAction } from "@reduxjs/toolkit";
import { configureStore } from "@reduxjs/toolkit";
import { baseApi } from "../baseApi";
import authReducer, { type AuthState } from "../../slices/auth";

import "@/store/api/profileApi";
import "@/store/api/storeApi";
import "@/store/api/fileApi";

const api = baseApi as unknown as {
  endpoints: Record<string, { initiate: (...args: unknown[]) => unknown } | undefined>;
};

function createTestStore(preloadedAuth?: AuthState) {
  return configureStore({
    reducer: {
      auth: authReducer as Reducer<AuthState, UnknownAction>,
      [baseApi.reducerPath]: baseApi.reducer as Reducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
    preloadedState: preloadedAuth ? { auth: preloadedAuth } : undefined,
  });
}

const authenticatedAuth: AuthState = {
  step: "authenticated",
  phone: "+965501234567",
  user: { id: "1", name: "Test", phone: "+965501234567", role: "seller", email: null },
  preferredView: "seller",
  loading: false,
  error: null,
};

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    if (urlStr.includes("/auth/refresh")) {
      return Response.json(
        { access_token: "new-token", refresh_token: "new-refresh" },
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    const body = { success: true, data: { id: "1", name: "Test" } };
    return Response.json(body, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("baseApi", () => {
  it("should have defined endpoints after injectEndpoints", () => {
    expect(api.endpoints.getProfile).toBeDefined();
    expect(api.endpoints.getMyStores).toBeDefined();
    expect(api.endpoints.uploadFile).toBeDefined();
  });

  it("should send the CSRF header on every request", async () => {
    const store = createTestStore(authenticatedAuth);

    const fetchSpy = vi.spyOn(globalThis, "fetch");
    store.dispatch(api.endpoints.getProfile!.initiate() as never);

    await vi.waitFor(() => {
      const profileCalls = fetchSpy.mock.calls.filter(([url]) => {
        let urlStr: string;
        if (typeof url === "string") {
          urlStr = url;
        } else if (url instanceof Request) {
          urlStr = url.url;
        } else {
          urlStr = "";
        }
        return urlStr.includes("/users/me/profile");
      });
      expect(profileCalls.length).toBeGreaterThan(0);
      const call = profileCalls[0]!;
      if (call[0] instanceof Request) {
        expect(call[0].headers.get("X-Requested-With")).toBe("XMLHttpRequest");
      } else if (call[1]) {
        const init = call[1] as Record<string, Record<string, string>>;
        expect(init.headers?.["X-Requested-With"]).toBe("XMLHttpRequest");
      }
    });
  });

  it("should not send a Bearer token from auth state", async () => {
    const store = createTestStore(authenticatedAuth);

    const fetchSpy = vi.spyOn(globalThis, "fetch");
    store.dispatch(api.endpoints.getProfile!.initiate() as never);

    await vi.waitFor(() => {
      const profileCalls = fetchSpy.mock.calls.filter(([url]) => {
        let urlStr: string;
        if (typeof url === "string") {
          urlStr = url;
        } else if (url instanceof Request) {
          urlStr = url.url;
        } else {
          urlStr = "";
        }
        return urlStr.includes("/users/me/profile");
      });
      if (profileCalls.length > 0) {
        const call = profileCalls[0]!;
        if (call[0] instanceof Request) {
          expect(call[0].headers.get("Authorization")).toBeNull();
        } else if (call[1]) {
          const init = call[1] as Record<string, Record<string, string>>;
          expect(init.headers?.["Authorization"]).toBeUndefined();
        }
      }
    });
  });

  it("should have reducerPath set to 'api'", () => {
    expect(baseApi.reducerPath).toBe("api");
  });
});
