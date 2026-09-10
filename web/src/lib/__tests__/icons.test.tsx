import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { getIcon, IconRenderer } from "../icons";
import { FaTshirt } from "react-icons/fa";

describe("getIcon", () => {
  it("returns undefined for unknown code", () => {
    expect(getIcon("NonExistentIcon")).toBeUndefined();
  });

  it("returns IconType for known code", () => {
    const icon = getIcon("FaTshirt");
    expect(icon).toBe(FaTshirt);
  });
});

describe("IconRenderer", () => {
  it("returns null when code is missing", () => {
    const { container } = render(<IconRenderer />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null when code is null", () => {
    const { container } = render(<IconRenderer code={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for unknown code", () => {
    const { container } = render(<IconRenderer code="UnknownIcon" />);
    expect(container.innerHTML).toBe("");
  });

  it("renders icon element for known code", () => {
    const { container } = render(<IconRenderer code="FaTshirt" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("passes className to the icon", () => {
    const { container } = render(<IconRenderer code="FaTshirt" className="h-6 w-6" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("w-6 h-6");
  });

  it("passes size to the icon", () => {
    const { container } = render(<IconRenderer code="FaTshirt" size={32} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("32");
  });
});
