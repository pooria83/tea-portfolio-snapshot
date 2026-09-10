import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";

import { RandomProductsSection } from "../RandomProductsSection";
import type { ProductListItem } from "@/types/api";

const messages: Record<string, Record<string, string>> = {
  "website.products": {
    title: "Featured Products",
  },
};

vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: (namespace: string) => {
    const table = messages[namespace as keyof typeof messages] ?? {};
    return (key: string) => (table as Record<string, string>)[key] ?? key;
  },
}));

function makeProduct(id: string): ProductListItem {
  return {
    id,
    store_id: "store-1",
    store_name: "Test Store",
    product_type_id: "pt-1",
    name_ar: null,
    name_en: `Test Product ${id}`,
    name_fa: null,
    brand_name: "Test Brand",
    status: "active",
    has_variants: false,
    price: 99,
    original_price: 129,
    sale_price: 79,
    currency: "SAR",
    quantity: 5,
    image_url: null,
  };
}

const mockProducts: ProductListItem[] = Array.from({ length: 20 }, (_, index) =>
  makeProduct(`product-${index + 1}`),
);

let queryResult: { data: ProductListItem[] | undefined; isLoading: boolean } = {
  data: mockProducts,
  isLoading: false,
};

vi.mock("@/store/api/anonymousApi", () => ({
  useGetRandomProductsQuery: () => queryResult,
}));

vi.mock("swiper/react", () => ({
  Swiper: ({ children }: { children: ReactNode }) => <div data-testid="swiper">{children}</div>,
  SwiperSlide: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("swiper/modules", () => ({
  A11y: {},
  Pagination: {},
  Autoplay: {},
}));

vi.mock("@/components/product/ProductViewDialog", () => ({
  ProductViewDialog: ({
    open,
    storeId,
    productId,
  }: {
    open: boolean;
    storeId: string;
    productId: string;
  }) =>
    open ? (
      <div data-testid="product-view-dialog">{`store=${storeId} product=${productId}`}</div>
    ) : null,
}));

vi.mock("next/image", () => ({
  __esModule: true,
  default: ({ alt, src }: { alt: string; src: string }) => <img alt={alt} src={src} />,
}));

describe("RandomProductsSection", () => {
  beforeEach(() => {
    queryResult = { data: mockProducts, isLoading: false };
  });

  it("renders the section title and 20 product cards", () => {
    render(<RandomProductsSection />);
    expect(screen.getByRole("heading", { name: "Featured Products" })).toBeInTheDocument();
    expect(document.querySelector(".featured-products-pagination")).not.toBeNull();
    expect(screen.getAllByRole("button", { name: /Test Product/ })).toHaveLength(20);
  });

  it("opens the product view dialog when a card is clicked", () => {
    render(<RandomProductsSection />);
    expect(screen.queryByTestId("product-view-dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Test Product product-3/ }));

    expect(screen.getByTestId("product-view-dialog")).toBeInTheDocument();
    expect(screen.getByText(/store=store-1/)).toBeInTheDocument();
    expect(screen.getByText(/product=product-3/)).toBeInTheDocument();
  });

  it("renders nothing when there are no products", () => {
    queryResult = { data: [], isLoading: false };
    const { container } = render(<RandomProductsSection />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a loading skeleton while fetching", () => {
    queryResult = { data: undefined, isLoading: true };
    render(<RandomProductsSection />);
    expect(screen.getByRole("heading", { name: "Featured Products" })).toBeInTheDocument();
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
  });
});
