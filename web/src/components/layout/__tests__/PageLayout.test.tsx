import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageLayout } from "../PageLayout";

describe("PageLayout", () => {
  it("should render children", () => {
    render(<PageLayout>Content</PageLayout>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("should use 'wide' variant by default", () => {
    const { container } = render(<PageLayout>Content</PageLayout>);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("space-y-6");
    expect(div.className).not.toContain("max-w-2xl");
  });

  it("should apply 'narrow' variant classes", () => {
    const { container } = render(<PageLayout variant="narrow">Content</PageLayout>);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("max-w-2xl");
    expect(div.className).toContain("space-y-6");
  });

  it("should merge custom className", () => {
    const { container } = render(<PageLayout className="extra-class">Content</PageLayout>);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("extra-class");
    expect(div.className).toContain("space-y-6");
  });
});
