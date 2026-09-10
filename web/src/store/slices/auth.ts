import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "../store";
import { baseApi } from "../api/baseApi";
import { extractApiError } from "@/lib/api";

export type AuthStep = "phone" | "otp" | "authenticated";

export type UserRole = "admin" | "seller";

export interface User {
  id: string;
  name: string;
  phone: string;
  role: UserRole;
  email: string | null;
}

export interface AuthState {
  step: AuthStep;
  phone: string;
  user: User | null;
  preferredView: UserRole;
  loading: boolean;
  error: string | null;
}

const PREF_VIEW_KEY = "tea_preferred_view";

function getStoredPreferredView(): UserRole | null {
  try {
    const raw = localStorage.getItem(PREF_VIEW_KEY);
    if (raw === "admin" || raw === "seller") return raw;
  } catch (error) {
    console.warn("Failed to read preferred view from localStorage:", error);
  }
  return null;
}

function storePreferredView(view: UserRole): void {
  try {
    localStorage.setItem(PREF_VIEW_KEY, view);
  } catch (error) {
    console.warn("Failed to persist preferred view to localStorage:", error);
  }
}

const initialState: AuthState = {
  step: "phone",
  phone: "",
  user: null,
  preferredView: "seller",
  loading: false,
  error: null,
};

interface GetMeUser {
  id: string;
  full_name: string | null;
  username: string | null;
  phone: string | null;
  role: string;
  email: string | null;
}

function mapUser(res: GetMeUser): User {
  return {
    id: res.id,
    name: res.full_name || res.username || res.phone || "",
    phone: res.phone || "",
    role: res.role === "admin" ? "admin" : "seller",
    email: res.email,
  };
}

export const bootstrapAuth = createAsyncThunk<{ user: User }, void, { state: RootState }>(
  "auth/bootstrapAuth",
  async (_arg, { dispatch }) => {
    const me = await dispatch(baseApi.endpoints.getMe.initiate()).unwrap();
    return { user: mapUser(me) };
  },
);

export const sendOtp = createAsyncThunk<
  { phone: string },
  string,
  { rejectValue: string; state: RootState }
>("auth/sendOtp", async (phone, { dispatch, rejectWithValue }) => {
  try {
    await dispatch(baseApi.endpoints.sendOtp.initiate({ phone })).unwrap();
    return { phone };
  } catch (error) {
    return rejectWithValue(extractApiError(error, "Failed to send OTP"));
  }
});

export const verifyOtp = createAsyncThunk<
  { user: User },
  string,
  { rejectValue: string; state: RootState }
>("auth/verifyOtp", async (otp, { getState, dispatch, rejectWithValue }) => {
  const { phone } = getState().auth;
  try {
    await dispatch(baseApi.endpoints.verifyOtp.initiate({ phone, code: otp })).unwrap();
    const me = await dispatch(baseApi.endpoints.getMe.initiate()).unwrap();
    return { user: mapUser(me) };
  } catch (error) {
    return rejectWithValue(extractApiError(error, "Verification failed"));
  }
});

export const googleCodeAuth = createAsyncThunk<
  { user: User },
  { code: string; redirect_uri: string; state?: string },
  { rejectValue: string; state: RootState }
>("auth/googleCodeAuth", async ({ code, redirect_uri, state }, { dispatch, rejectWithValue }) => {
  try {
    const arg = state ? { code, redirect_uri, state } : { code, redirect_uri };
    await dispatch(baseApi.endpoints.googleCodeAuth.initiate(arg)).unwrap();
    const me = await dispatch(baseApi.endpoints.getMe.initiate()).unwrap();
    return { user: mapUser(me) };
  } catch (error) {
    return rejectWithValue(extractApiError(error, "Google login failed"));
  }
});

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setPhone(state, action: PayloadAction<string>) {
      state.phone = action.payload;
    },
    logout() {
      return initialState;
    },
    clearError(state) {
      state.error = null;
    },
    setPreferredView(state, action: PayloadAction<UserRole>) {
      state.preferredView = action.payload;
      storePreferredView(action.payload);
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(bootstrapAuth.pending, (state) => {
        state.loading = true;
      })
      .addCase(bootstrapAuth.fulfilled, (state, action) => {
        state.loading = false;
        state.user = action.payload.user;
        state.step = "authenticated";
        state.preferredView = getStoredPreferredView() ?? action.payload.user.role;
      })
      .addCase(bootstrapAuth.rejected, (state) => {
        state.loading = false;
      })
      .addCase(sendOtp.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(sendOtp.fulfilled, (state, action) => {
        state.loading = false;
        state.phone = action.payload.phone;
        state.step = "otp";
      })
      .addCase(sendOtp.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? null;
      })
      .addCase(verifyOtp.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(verifyOtp.fulfilled, (state, action) => {
        state.loading = false;
        state.user = action.payload.user;
        state.step = "authenticated";
        state.preferredView = getStoredPreferredView() ?? action.payload.user.role;
      })
      .addCase(verifyOtp.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? null;
      })
      .addCase(googleCodeAuth.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(googleCodeAuth.fulfilled, (state, action) => {
        state.loading = false;
        state.user = action.payload.user;
        state.step = "authenticated";
        state.preferredView = getStoredPreferredView() ?? action.payload.user.role;
      })
      .addCase(googleCodeAuth.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? null;
      });
  },
});

export const { setPhone, logout, clearError, setPreferredView } = authSlice.actions;
export default authSlice.reducer;
