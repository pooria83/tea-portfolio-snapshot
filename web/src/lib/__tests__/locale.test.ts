import { describe, it, expect } from "vitest";
import { localeDirection, localeValue } from "../locale";

describe("localeValue", () => {
  it("returns Arabic value for ar locale", () => {
    expect(localeValue("ar", "مرحبا", "سلام", "Hello")).toBe("مرحبا");
  });

  it("returns Farsi value for fa locale", () => {
    expect(localeValue("fa", "مرحبا", "سلام", "Hello")).toBe("سلام");
  });

  it("returns English value for en locale", () => {
    expect(localeValue("en", "مرحبا", "سلام", "Hello")).toBe("Hello");
  });

  it("returns English value for unknown locale", () => {
    expect(localeValue("fr", "مرحبا", "سلام", "Hello")).toBe("Hello");
  });
});

describe("localeDirection", () => {
  it("returns rtl for ar locale", () => {
    expect(localeDirection("ar")).toBe("rtl");
  });

  it("returns rtl for fa locale", () => {
    expect(localeDirection("fa")).toBe("rtl");
  });

  it("returns ltr for en locale", () => {
    expect(localeDirection("en")).toBe("ltr");
  });

  it("returns ltr for unknown locale", () => {
    expect(localeDirection("fr")).toBe("ltr");
  });

  it("returns auto when locale is absent", () => {
    expect(localeDirection()).toBe("auto");
  });
});
