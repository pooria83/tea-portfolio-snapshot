import { act, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/image", () => ({
  default: (props: React.ImgHTMLAttributes<HTMLImageElement>) => (
    <img {...props} alt={props.alt ?? ""} />
  ),
}));

import { normalizeSrc, RetryingThumbnail } from "../RetryingThumbnail";

describe("RetryingThumbnail", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("rewrites storage-dev URLs to prod storage on the production host", () => {
    const src = normalizeSrc(
      "https://portfolio.example.invalid/product-graph/products/p/img.jpg",
      "portfolio.example.invalid",
    );
    expect(src).toBe("https://portfolio.example.invalid/product-graph/products/p/img.jpg");
  });

  it("keeps storage-dev URLs on dev hosts", () => {
    const src = normalizeSrc(
      "https://portfolio.example.invalid/product-graph/products/p/img.jpg",
      "localhost",
    );
    expect(src).toBe("https://portfolio.example.invalid/product-graph/products/p/img.jpg");
  });

  it("leaves other absolute URLs untouched", () => {
    const src = normalizeSrc(
      "https://portfolio.example.invalid/product-graph/products/p/img.jpg",
      "portfolio.example.invalid",
    );
    expect(src).toBe("https://portfolio.example.invalid/product-graph/products/p/img.jpg");
  });

  it("shows a fallback after the image fails to load", () => {
    render(<RetryingThumbnail src="https://portfolio.example.invalid/p.jpg" alt="bag" />);

    act(() => {
      fireEvent.error(screen.getByRole("img"));
    });

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByTitle("bag")).toBeInTheDocument();
  });
});
