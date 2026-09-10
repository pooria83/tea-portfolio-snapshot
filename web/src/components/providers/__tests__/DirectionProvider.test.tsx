import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { DirectionSetter } from "../DirectionProvider";

describe("DirectionSetter", () => {
  beforeEach(() => {
    document.documentElement.dir = "";
  });

  afterEach(() => {
    document.documentElement.dir = "";
  });

  it("should set dir to rtl for Arabic locale", () => {
    render(<DirectionSetter locale="ar" />);
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("should set dir to rtl for Farsi locale", () => {
    render(<DirectionSetter locale="fa" />);
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("should set dir to ltr for English locale", () => {
    render(<DirectionSetter locale="en" />);
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("should update dir when locale changes", () => {
    const { rerender } = render(<DirectionSetter locale="ar" />);
    expect(document.documentElement.dir).toBe("rtl");

    rerender(<DirectionSetter locale="en" />);
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("should render nothing", () => {
    const { container } = render(<DirectionSetter locale="en" />);
    expect(container.innerHTML).toBe("");
  });
});
