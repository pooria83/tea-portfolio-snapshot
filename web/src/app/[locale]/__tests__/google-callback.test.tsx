import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import authReducer, { type AuthStep } from "@/store/slices/auth";

const mockReplace = vi.fn();
const mockGet = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => ({ get: mockGet }),
}));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string) => {
    const messages: Record<string, Record<string, string>> = {
      auth: { googleSigningIn: "Signing in..." },
    };
    return messages[namespace]?.[key] ?? key;
  },
}));

const mockLinkGoogle = vi.fn();

vi.mock("@/store/api/profileApi", () => ({
  useLinkGoogleMutation: () => [mockLinkGoogle],
}));

function createStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        step: "phone" as AuthStep,
        phone: "",
        user: null,
        preferredView: "seller" as const,
        loading: false,
        error: null,
      },
    },
  });
}

import GoogleCallbackPage from "@/app/[locale]/auth/google/callback/page";

describe("GoogleCallbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    sessionStorage.setItem("google_oauth_link", "link");
    mockLinkGoogle.mockReturnValue({
      unwrap: () => Promise.resolve({ role: "seller" }),
    });
  });

  it("should show signing in message", () => {
    mockGet.mockReturnValue(null);
    const store = createStore();
    render(
      <Provider store={store}>
        <GoogleCallbackPage />
      </Provider>,
    );
    expect(screen.getByText("Signing in...")).toBeInTheDocument();
  });

  it("should call linkGoogle when state=link", () => {
    mockGet.mockImplementation((key: string) => {
      if (key === "code") return "test-code";
      if (key === "state") return "link";
      return null;
    });

    const store = createStore();
    render(
      <Provider store={store}>
        <GoogleCallbackPage />
      </Provider>,
    );

    expect(mockLinkGoogle).toHaveBeenCalledWith({
      code: "test-code",
      redirect_uri: "http://localhost:3000/auth/google/callback",
      state: "link",
    });
  });

  it("should redirect to profile on successful link", async () => {
    mockGet.mockImplementation((key: string) => {
      if (key === "code") return "test-code";
      if (key === "state") return "link";
      return null;
    });

    mockLinkGoogle.mockReturnValue({
      unwrap: () => Promise.resolve({ role: "admin" }),
    });

    const store = createStore();
    render(
      <Provider store={store}>
        <GoogleCallbackPage />
      </Provider>,
    );

    await vi.waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(expect.stringContaining("google_link_success=1"));
    });
  });

  it("should redirect with error params on link failure", async () => {
    mockGet.mockImplementation((key: string) => {
      if (key === "code") return "test-code";
      if (key === "state") return "link";
      return null;
    });

    mockLinkGoogle.mockReturnValue({
      unwrap: () =>
        Promise.reject({
          data: {
            error: { code: "CONFLICT", message: "Already linked" },
          },
        }),
    });

    const store = createStore();
    render(
      <Provider store={store}>
        <GoogleCallbackPage />
      </Provider>,
    );

    await vi.waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(expect.stringContaining("google_link_error=1"));
      expect(mockReplace).toHaveBeenCalledWith(expect.stringContaining("ecode=CONFLICT"));
    });
  });
});
