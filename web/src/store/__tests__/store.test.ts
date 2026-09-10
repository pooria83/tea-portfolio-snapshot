import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { makeStore } from "../store";
import { logout, verifyOtp } from "../slices/auth";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("makeStore", () => {
  it("should create store with auth and api reducers", () => {
    const store = makeStore();
    const state = store.getState();
    expect(state.auth).toBeDefined();
    expect(state.api).toBeDefined();
  });

  it("should start with initial auth state", () => {
    const store = makeStore();
    expect(store.getState().auth.step).toBe("phone");
    expect(store.getState().auth.user).toBeNull();
    expect(store.getState().auth.preferredView).toBe("seller");
  });

  it("should not persist auth data to localStorage", () => {
    const store = makeStore();
    store.dispatch(
      verifyOtp.fulfilled(
        { user: { id: "1", name: "T", phone: "123", role: "seller", email: null } },
        "r1",
        "otp",
      ),
    );
    expect(store.getState().auth.step).toBe("authenticated");
    expect(localStorage.getItem("tea_auth")).toBeNull();
  });

  it("should reset auth state and API cache on logout", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ success: true, data: {} }, { status: 200 }),
    );
    const store = makeStore();
    store.dispatch(
      verifyOtp.fulfilled(
        { user: { id: "1", name: "T", phone: "123", role: "admin", email: null } },
        "r1",
        "otp",
      ),
    );
    expect(store.getState().auth.step).toBe("authenticated");

    store.dispatch(logout());

    await vi.waitFor(() => {
      expect(store.getState().auth.step).toBe("phone");
      expect(store.getState().auth.user).toBeNull();
    });
  });
});
