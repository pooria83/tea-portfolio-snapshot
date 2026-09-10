import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const mockRouter = { replace: vi.fn() };
const mockSendOtp = vi.fn();
const mockVerifyOtp = vi.fn();
const mockClearError = vi.fn();
let mockStep = "phone";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string) => {
    const messages: Record<string, Record<string, string>> = {
      auth: {
        login: "Sign in",
        phone: "Phone Number",
        sendOtp: "Send Verification Code",
        googleSigningIn: "Signing in...",
        searchCountry: "Search country",
        noCountryFound: "No country found",
        phonePlaceholder: "501234567",
        or: "or",
        googleLogin: "Continue with Google",
        otp: "Verification Code",
        enterOtp: "Enter the verification code",
        back: "Back",
        verifyOtp: "Verify",
      },
      app: { name: "AskTea.ai" },
      common: {
        switchLanguage: "Switch language",
        themeLight: "Light mode",
        themeDark: "Dark mode",
      },
    };
    return messages[namespace]?.[key] ?? key;
  },
  useLocale: () => "en",
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/login",
  routing: { locales: ["ar", "en", "fa"] },
}));

vi.mock("@/components/providers/ThemeProvider", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn() }),
}));

vi.mock("@/hooks/useLoginFlow", () => ({
  useLoginFlow: () => ({
    step: mockStep,
    loading: false,
    error: null,
    sendOtp: mockSendOtp,
    verifyOtp: mockVerifyOtp,
    clearError: mockClearError,
  }),
}));

vi.mock("@/store/hooks", () => ({
  useAppSelector: (selector: (s: unknown) => unknown) =>
    selector({
      auth: { phone: "", user: null, step: mockStep },
    }),
  useAppDispatch: () => vi.fn(),
}));

vi.mock("@/store/slices/auth", () => ({
  setPhone: (phone: string) => ({ type: "auth/setPhone", payload: phone }),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

import LoginPage from "@/app/[locale]/(auth)/login/page";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStep = "phone";
  });

  it("should render login card with app name", () => {
    render(<LoginPage />);
    expect(screen.getByText("AskTea.ai")).toBeInTheDocument();
    expect(screen.getByText("Sign in")).toBeInTheDocument();
  });

  it("should render phone input step", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Phone Number")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send Verification Code" })).toBeInTheDocument();
  });

  it("should render language and theme toggles", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Switch language")).toBeInTheDocument();
    expect(screen.getByLabelText("Light mode")).toBeInTheDocument();
  });
});
