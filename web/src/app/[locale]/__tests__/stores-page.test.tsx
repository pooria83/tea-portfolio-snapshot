import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import authReducer from "@/store/slices/auth";

const messages = {
  nav: { stores: "Stores", products: "Products" },
  store: {
    createStore: "New Store",
    noStores: "No stores yet",
    createFirstStore: "Create your first store",
    active: "Active",
    inactive: "Inactive",
  },
};

const mockStores = [
  {
    id: "store-1",
    name: "My Store",
    logo_url: "https://example.com/logo.png",
    is_active: true,
    category_name_ar: "مطاعم",
    category_name_en: "Restaurants",
    category_name_fa: "رستوران‌ها",
    store_type_name_ar: "متجر",
    store_type_name_en: "Store",
    store_type_name_fa: "فروشگاه",
  },
  {
    id: "store-2",
    name: "Inactive Store",
    logo_url: null,
    is_active: false,
    category_name_ar: "ملابس",
    category_name_en: "Clothing",
    category_name_fa: "پوشاک",
    store_type_name_ar: "متجر",
    store_type_name_en: "Store",
    store_type_name_fa: "فروشگاه",
  },
];

let mockQueryResult = { data: [] as typeof mockStores, isLoading: true };

vi.mock("@/store/api/storeApi", () => ({
  useGetMyStoresQuery: () => mockQueryResult,
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

import StoresPage from "@/app/[locale]/(dashboard)/seller/stores/page";

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

describe("StoresPage", () => {
  it("should show loading skeletons initially", () => {
    mockQueryResult = { data: [], isLoading: true };
    render(<StoresPage />, { wrapper });

    expect(screen.getByText("Stores")).toBeInTheDocument();
    expect(screen.getByText("New Store")).toBeInTheDocument();
  });

  it("should show empty state when no stores", () => {
    mockQueryResult = { data: [], isLoading: false };
    render(<StoresPage />, { wrapper });

    expect(screen.getByText("No stores yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first store")).toBeInTheDocument();
  });

  it("should render store cards", () => {
    mockQueryResult = { data: mockStores, isLoading: false };
    render(<StoresPage />, { wrapper });

    expect(screen.getByText("My Store")).toBeInTheDocument();
    expect(screen.getByText("Inactive Store")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("should show locale-aware category name", () => {
    mockQueryResult = { data: mockStores, isLoading: false };
    render(<StoresPage />, { wrapper });

    expect(screen.getByText(/Restaurants/)).toBeInTheDocument();
    expect(screen.getByText(/Clothing/)).toBeInTheDocument();
  });
});
