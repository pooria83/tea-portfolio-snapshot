import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import { NextIntlClientProvider } from "next-intl";
import authReducer, { type AuthStep } from "@/store/slices/auth";
import DashboardLayout from "@/app/[locale]/(dashboard)/layout";

const mockRouter = { replace: vi.fn() };

vi.mock("@/i18n/routing", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/dashboard",
}));

const messages = {
  common: {
    themeLight: "Light Mode",
    themeDark: "Dark Mode",
  },
  nav: {
    dashboard: "Dashboard",
    stores: "Stores",
    products: "Products",
    profile: "Profile",
    logout: "Logout",
    switchToAdmin: "Switch to Admin",
    switchToSeller: "Switch to Seller",
  },
  auth: {
    logout: "Logout",
  },
};

function createWrapper(store: ReturnType<typeof configureStore>) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <NextIntlClientProvider locale="en" messages={messages}>
        <Provider store={store}>{children}</Provider>
      </NextIntlClientProvider>
    );
  };
}

function createAuthPreload(overrides: Record<string, unknown>) {
  return {
    auth: {
      step: "phone" as AuthStep,
      phone: "",
      user: null,
      preferredView: "seller" as const,
      loading: false,
      error: null,
      ...overrides,
    },
  };
}

describe("DashboardLayout", () => {
  beforeEach(() => {
    mockRouter.replace.mockClear();
  });

  it("should render null when not hydrated", () => {
    const store = configureStore({
      reducer: { auth: authReducer },
    });

    const { container } = render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>,
      { wrapper: createWrapper(store) },
    );

    expect(container.innerHTML).toBe("");
  });

  it("should not render children when loading", () => {
    const store = configureStore({
      reducer: { auth: authReducer },
      preloadedState: createAuthPreload({ loading: true }),
    });

    render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>,
      { wrapper: createWrapper(store) },
    );

    expect(screen.queryByText("Content")).not.toBeInTheDocument();
  });

  it("should redirect to login when not authenticated", () => {
    const store = configureStore({
      reducer: { auth: authReducer },
      preloadedState: createAuthPreload({}),
    });

    render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>,
      { wrapper: createWrapper(store) },
    );

    expect(mockRouter.replace).toHaveBeenCalledWith("/login");
  });
});
