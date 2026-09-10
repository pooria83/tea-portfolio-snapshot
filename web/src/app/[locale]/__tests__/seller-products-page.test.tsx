import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import authReducer from "@/store/slices/auth";
import type { ProductListItem } from "@/types/api";

const messages = {
  product: {
    title: "My Products",
    allStores: "All Stores",
    errorLoading: "Error loading products",
    noProducts: "No products yet",
    createFirst: "Create your first product",
    searchPlaceholder: "Search by product name...",
    searchProducts: "Search",
    quantity: "Quantity",
    createTitle: "Create Product",
  },
  common: {
    close: "Close",
    edit: "Edit",
    loading: "Loading...",
    error: "An error occurred",
    search: "Search",
    noResults: "No results found",
    clear: "Clear",
  },
  dashboard: {
    title: "Dashboard",
    viewDetails: "View Details",
    totalProducts: "Products",
    activeProducts: "Active",
    totalStores: "Stores",
  },
  store: {
    noStores: "No stores yet",
    chooseStore: "Choose a store",
  },
};

const mockProducts: ProductListItem[] = [
  {
    id: "p-1",
    store_id: "s-1",
    store_name: "Store 1",
    product_type_id: "pt-1",
    name_ar: null,
    name_en: "Product 1",
    name_fa: null,
    brand_name: "Brand A",
    status: "active",
    has_variants: false,
    price: 50,
    original_price: 50,
    sale_price: null,
    currency: "SAR",
    quantity: 5,
    image_url: null,
  },
  {
    id: "p-2",
    store_id: "s-2",
    store_name: "Store 2",
    product_type_id: "pt-1",
    name_ar: null,
    name_en: "Product 2",
    name_fa: null,
    brand_name: "Brand B",
    status: "active",
    has_variants: false,
    price: 30,
    original_price: 30,
    sale_price: null,
    currency: "SAR",
    quantity: 3,
    image_url: null,
  },
];

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
  {
    id: "s-2",
    name: "Store 2",
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

const mockTrigger = {
  fn: vi.fn().mockResolvedValue({
    data: {
      items: [],
      meta: { skip: 0, limit: 20, total: 0, has_next: false, has_previous: false },
    },
  }),
};
let mockStoresResult = { data: [] as typeof mockStores, isLoading: false };

vi.mock("@/store/api/productApi", () => ({
  useLazyGetMyProductsPageQuery: () => [
    mockTrigger.fn,
    { data: undefined, isLoading: false, isError: false },
  ],
}));

vi.mock("@/store/api/storeApi", () => ({
  useGetMyStoresQuery: () => mockStoresResult,
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
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

vi.mock("next-intl", async () => {
  const actual = await vi.importActual("next-intl");
  return {
    ...(actual as object),
    useLocale: () => "en",
  };
});

import SellerProductsPage from "@/app/[locale]/(dashboard)/seller/products/page";

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

describe("SellerProductsPage", () => {
  it("shows title", async () => {
    render(<SellerProductsPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("My Products")).toBeInTheDocument();
    });
  });

  it("shows empty state when no products", async () => {
    mockTrigger.fn.mockResolvedValue({
      data: {
        items: [],
        meta: { skip: 0, limit: 20, total: 0, has_next: false, has_previous: false },
      },
    });
    mockStoresResult = { data: [], isLoading: false };
    render(<SellerProductsPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("No products yet")).toBeInTheDocument();
    });
    expect(screen.getByText("Create your first product")).toBeInTheDocument();
  });

  it("renders product cards when products exist", async () => {
    mockTrigger.fn.mockResolvedValue({
      data: {
        items: mockProducts,
        meta: { skip: 0, limit: 20, total: 2, has_next: false, has_previous: false },
      },
    });
    mockStoresResult = { data: mockStores, isLoading: false };
    render(<SellerProductsPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Product 1")).toBeInTheDocument();
    });
    expect(screen.getByText("Product 2")).toBeInTheDocument();
  });

  it("renders store filter with select trigger", async () => {
    mockTrigger.fn.mockResolvedValue({
      data: {
        items: mockProducts,
        meta: { skip: 0, limit: 20, total: 2, has_next: false, has_previous: false },
      },
    });
    mockStoresResult = { data: mockStores, isLoading: false };
    render(<SellerProductsPage />, { wrapper });
    await waitFor(() => {
      const trigger = document.querySelector('[role="combobox"]');
      expect(trigger).toBeInTheDocument();
    });
  });

  it("product card receives store_name via storeName prop", async () => {
    mockTrigger.fn.mockResolvedValue({
      data: {
        items: mockProducts,
        meta: { skip: 0, limit: 20, total: 2, has_next: false, has_previous: false },
      },
    });
    mockStoresResult = { data: mockStores, isLoading: false };
    const { container } = render(<SellerProductsPage />, { wrapper });
    await waitFor(() => {
      expect(container.textContent).toContain("Store 1");
    });
    expect(container.textContent).toContain("Store 2");
  });
});
