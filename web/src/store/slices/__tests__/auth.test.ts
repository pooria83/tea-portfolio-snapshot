import { describe, it, expect, beforeEach } from "vitest";
import authReducer, {
  bootstrapAuth,
  sendOtp,
  verifyOtp,
  googleCodeAuth,
  logout,
  setPhone,
  clearError,
  setPreferredView,
  type AuthState,
  type User,
} from "../auth";

const initialState: AuthState = {
  step: "phone",
  phone: "",
  user: null,
  preferredView: "seller",
  loading: false,
  error: null,
};

const sellerUser: User = {
  id: "1",
  name: "Test Seller",
  phone: "+965501234567",
  role: "seller",
  email: "test@example.com",
};

const adminUser: User = {
  id: "1",
  name: "Test Admin",
  phone: "+965501234567",
  role: "admin",
  email: "test@example.com",
};

beforeEach(() => {
  localStorage.clear();
});

describe("auth slice", () => {
  it("should return initial state", () => {
    expect(authReducer(undefined, { type: "unknown" })).toEqual(initialState);
  });

  it("should set phone", () => {
    const state = authReducer(initialState, setPhone("0912345678"));
    expect(state.phone).toBe("0912345678");
  });

  it("should clear error", () => {
    const state = authReducer({ ...initialState, error: "some error" }, clearError());
    expect(state.error).toBeNull();
  });

  it("should reset to initial state on logout", () => {
    const loggedInState: AuthState = {
      step: "authenticated",
      phone: "0912345678",
      user: adminUser,
      preferredView: "admin",
      loading: false,
      error: null,
    };
    expect(authReducer(loggedInState, logout())).toEqual(initialState);
  });

  it("should set preferred view and persist it", () => {
    const state = authReducer(initialState, setPreferredView("admin"));
    expect(state.preferredView).toBe("admin");
    expect(localStorage.getItem("tea_preferred_view")).toBe("admin");
  });

  it("should authenticate via bootstrapAuth fulfilled", () => {
    const state = authReducer(initialState, {
      type: bootstrapAuth.fulfilled.type,
      payload: { user: adminUser },
      meta: { arg: undefined, requestId: "1" },
    });
    expect(state.loading).toBe(false);
    expect(state.step).toBe("authenticated");
    expect(state.user).toEqual(adminUser);
    expect(state.preferredView).toBe("admin");
  });

  describe("sendOtp thunk", () => {
    it("should set loading on pending", () => {
      const state = authReducer(initialState, {
        type: sendOtp.pending.type,
        meta: { arg: "0912345678", requestId: "1" },
      });
      expect(state.loading).toBe(true);
      expect(state.error).toBeNull();
    });

    it("should set step to otp on fulfilled", () => {
      const state = authReducer(initialState, {
        type: sendOtp.fulfilled.type,
        payload: { phone: "0912345678" },
        meta: { arg: "0912345678", requestId: "1" },
      });
      expect(state.loading).toBe(false);
      expect(state.step).toBe("otp");
      expect(state.phone).toBe("0912345678");
    });

    it("should set error on rejected", () => {
      const state = authReducer(initialState, {
        type: sendOtp.rejected.type,
        error: { message: "Rejected" },
        meta: { arg: "12", requestId: "1" },
        payload: "رقم الهاتف غير صحيح",
      });
      expect(state.loading).toBe(false);
      expect(state.error).toBe("رقم الهاتف غير صحيح");
    });
  });

  describe("verifyOtp thunk", () => {
    const otpState: AuthState = { ...initialState, phone: "0912345678", step: "otp" };

    it("should set loading on pending", () => {
      const state = authReducer(otpState, {
        type: verifyOtp.pending.type,
        meta: { arg: "1234", requestId: "1" },
      });
      expect(state.loading).toBe(true);
    });

    it("should authenticate on fulfilled", () => {
      const state = authReducer(otpState, {
        type: verifyOtp.fulfilled.type,
        payload: { user: adminUser },
        meta: { arg: "1234", requestId: "1" },
      });
      expect(state.loading).toBe(false);
      expect(state.step).toBe("authenticated");
      expect(state.user?.name).toBe("Test Admin");
      expect(state.user?.role).toBe("admin");
    });

    it("should set error on rejected", () => {
      const state = authReducer(otpState, {
        type: verifyOtp.rejected.type,
        error: { message: "Rejected" },
        meta: { arg: "0000", requestId: "1" },
        payload: "رمز التحقق غير صحيح",
      });
      expect(state.loading).toBe(false);
      expect(state.error).toBe("رمز التحقق غير صحيح");
    });
  });

  describe("googleCodeAuth thunk", () => {
    it("should set loading on pending", () => {
      const state = authReducer(initialState, {
        type: googleCodeAuth.pending.type,
        meta: { arg: { code: "abc", redirect_uri: "http://localhost/callback" }, requestId: "1" },
      });
      expect(state.loading).toBe(true);
      expect(state.error).toBeNull();
    });

    it("should authenticate on fulfilled", () => {
      const state = authReducer(initialState, {
        type: googleCodeAuth.fulfilled.type,
        payload: { user: sellerUser },
        meta: { arg: { code: "abc", redirect_uri: "http://localhost/callback" }, requestId: "1" },
      });
      expect(state.loading).toBe(false);
      expect(state.step).toBe("authenticated");
      expect(state.user?.name).toBe("Test Seller");
      expect(state.preferredView).toBe("seller");
    });

    it("should set error on rejected", () => {
      const state = authReducer(initialState, {
        type: googleCodeAuth.rejected.type,
        error: { message: "Rejected" },
        meta: { arg: { code: "bad", redirect_uri: "http://localhost/callback" }, requestId: "1" },
        payload: "Google login failed",
      });
      expect(state.loading).toBe(false);
      expect(state.error).toBe("Google login failed");
    });
  });
});
