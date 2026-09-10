import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import authReducer from "@/store/slices/auth";

const messages = {
  dashboard: {
    title: "Dashboard",
    totalProducts: "Total Products",
    activeProducts: "Active",
    totalStores: "Total Stores",
    myProfile: "My Profile",
  },
};

const mockStores = [
  {
    id: "s-1",
    name: "Store 1",
    logo_url: null,
    is_active: true,
    category_name_ar: null,
    category_name_en: null,
    category_name_fa: null,
    store_type_name_ar: null,
    store_type_name_en: null,
    store_type_name_fa: null,
  },
];

const mockProfile = {
  id: "user-1",
  username: "testuser",
  email: "test@example.com",
  phone: "+96550123456",
};

let mockStatsResult: { data: { total: number; active: number } | undefined; isLoading: boolean } = {
  data: undefined,
  isLoading: true,
};
let mockStoresResult = { data: [] as typeof mockStores, isLoading: true };
let mockProfileResult: { data: typeof mockProfile | null; isLoading: boolean } = {
  data: null,
  isLoading: true,
};

vi.mock("@/store/api/productApi", () => ({
  useGetMyProductsStatsQuery: () => mockStatsResult,
}));

vi.mock("@/store/api/storeApi", () => ({
  useGetMyStoresQuery: () => mockStoresResult,
}));

vi.mock("@/store/api/profileApi", () => ({
  useGetProfileQuery: () => mockProfileResult,
}));

vi.mock("@/i18n/routing", () => ({
  Link: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

import SellerDashboardPage from "@/app/[locale]/(dashboard)/seller/page";

function wrapper({ children }: { children: React.ReactNode }) {
  const store = configureStore({
    reducer: { auth: authReducer },
  });
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <Provider store={store}>{children}</Provider>
    </NextIntlClientProvider>
  );
}

describe("SellerDashboardPage", () => {
  it("shows title", () => {
    render(<SellerDashboardPage />, { wrapper });
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows loading skeletons when queries are loading", () => {
    mockStatsResult = { data: undefined, isLoading: true };
    mockStoresResult = { data: [], isLoading: true };
    mockProfileResult = { data: null, isLoading: true };
    render(<SellerDashboardPage />, { wrapper });
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });

  it("renders product count tile", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Total Products")).toBeInTheDocument();
  });

  it("shows active product count in subtext", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    expect(screen.getByText("Active: 1")).toBeInTheDocument();
  });

  it("renders store count tile", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Total Stores")).toBeInTheDocument();
  });

  it("renders profile tile with email", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    expect(screen.getByText("My Profile")).toBeInTheDocument();
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("product tile links to /seller/products", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    const productLink = screen.getByText("Total Products").closest("a");
    expect(productLink?.getAttribute("href")).toBe("/seller/products");
  });

  it("stores tile links to /seller/stores", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    const storesLink = screen.getByText("Total Stores").closest("a");
    expect(storesLink?.getAttribute("href")).toBe("/seller/stores");
  });

  it("profile tile links to /seller/profile", () => {
    mockStatsResult = { data: { total: 2, active: 1 }, isLoading: false };
    mockStoresResult = { data: mockStores, isLoading: false };
    mockProfileResult = { data: mockProfile, isLoading: false };
    render(<SellerDashboardPage />, { wrapper });
    const profileLink = screen.getByText("My Profile").closest("a");
    expect(profileLink?.getAttribute("href")).toBe("/seller/profile");
  });
});
