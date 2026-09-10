import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import authReducer from "@/store/slices/auth";
import { ProductCard } from "../ProductCard";
import type { ProductListItem } from "@/types/api";

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const mockProduct: ProductListItem = {
  id: "product-1",
  store_id: "store-1",
  store_name: "Test Store",
  product_type_id: "pt-1",
  name_ar: null,
  name_en: "Test Product",
  name_fa: null,
  brand_name: "TestBrand",
  status: "active",
  has_variants: false,
  price: 100,
  original_price: 100,
  sale_price: null,
  currency: "SAR",
  quantity: 10,
  image_url: "/test-image.jpg",
};

const cardMessages = {
  product: {
    quantity: "Qty",
    variants: "Variants",
  },
  dashboard: {
    viewDetails: "View Details",
  },
  common: {
    edit: "Edit",
  },
};

function wrapper({ children }: { children: React.ReactNode }) {
  const store = configureStore({
    reducer: { auth: authReducer },
  });
  return (
    <NextIntlClientProvider locale="en" messages={cardMessages}>
      <Provider store={store}>{children}</Provider>
    </NextIntlClientProvider>
  );
}

describe("ProductCard", () => {
  it("renders product name (name_en fallback)", () => {
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText("Test Product")).toBeInTheDocument();
  });

  it("renders sale badge when sale_price exists", () => {
    const saleProduct = { ...mockProduct, sale_price: 70, original_price: 100, price: 70 };
    render(<ProductCard product={saleProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText("-30%")).toBeInTheDocument();
  });

  it("does not render sale badge when sale_price is null", () => {
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("shows sale price when on sale", () => {
    const saleProduct = { ...mockProduct, sale_price: 70, original_price: 100, price: 70 };
    render(<ProductCard product={saleProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText("70.00")).toBeInTheDocument();
  });

  it("shows store badge when storeName is passed", () => {
    render(
      <ProductCard product={mockProduct} storeId="store-1" storeName="My Store" locale="en" />,
      { wrapper },
    );
    expect(screen.getByText("My Store")).toBeInTheDocument();
  });

  it("does not show store badge when storeName is not passed", () => {
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.queryByText("Test Store")).toBeNull();
  });

  it("renders status badge for active status", () => {
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders status badge for draft status", () => {
    const draftProduct = { ...mockProduct, status: "draft" };
    render(<ProductCard product={draftProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText("draft")).toBeInTheDocument();
  });

  it("shows image when product has image_url", () => {
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" />, { wrapper });
    const img = screen.getByAltText("Test Product") as HTMLImageElement;
    expect(img).toBeInTheDocument();
    expect(img.src).toContain("test-image.jpg");
  });

  it("shows placeholder icon when no image", () => {
    const noImgProduct = { ...mockProduct, image_url: null };
    render(<ProductCard product={noImgProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("calls onView when View button clicked", async () => {
    const onView = vi.fn();
    const user = userEvent.setup();
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" onView={onView} />, {
      wrapper,
    });
    await user.click(screen.getByText("View Details"));
    expect(onView).toHaveBeenCalled();
  });

  it("renders brand name", () => {
    render(<ProductCard product={mockProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText("TestBrand")).toBeInTheDocument();
  });

  it("shows quantity and variant indicator", () => {
    const variantProduct = { ...mockProduct, has_variants: true };
    render(<ProductCard product={variantProduct} storeId="store-1" locale="en" />, { wrapper });
    expect(screen.getByText(/^Qty/)).toBeInTheDocument();
    expect(screen.getByText(/Variants/)).toBeInTheDocument();
  });
});
