import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "../Markdown";

describe("Markdown", () => {
  it("renders markdown content", () => {
    render(<Markdown>**bold** text</Markdown>);
    expect(screen.getByText("bold")).toBeInTheDocument();
    expect(screen.getByText("text")).toBeInTheDocument();
  });

  it("applies dir to the wrapper when provided", () => {
    const { container } = render(<Markdown dir="rtl">مرحبا</Markdown>);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.tagName).toBe("DIV");
    expect(wrapper.getAttribute("dir")).toBe("rtl");
  });

  it("omits dir when not provided", () => {
    const { container } = render(<Markdown>hi</Markdown>);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.getAttribute("dir")).toBeNull();
  });
});
