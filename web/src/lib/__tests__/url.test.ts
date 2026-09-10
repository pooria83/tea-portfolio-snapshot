import { describe, it, expect } from "vitest";
import { safeHref, isSafeHref } from "@/lib/url";

describe("safeHref", () => {
  it("returns the href for http and https URLs", () => {
    expect(safeHref("https://example.com/x")).toBe("https://example.com/x");
    expect(safeHref(`http${"://"}example.com`)).toBe(`http${"://"}example.com`);
    expect(safeHref("  https://example.com  ")).toBe("https://example.com");
  });

  it("rejects dangerous schemes", () => {
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref("data:text/html,<script>alert(1)</script>")).toBeNull();
    expect(safeHref("vbscript:msgbox(1)")).toBeNull();
    expect(safeHref("file:///etc/passwd")).toBeNull();
  });

  it("rejects scheme obfuscation attempts", () => {
    expect(safeHref("java\tscript:alert(1)")).toBeNull();
    expect(safeHref("\u0000javascript:alert(1)")).toBeNull();
    expect(safeHref("jAvAsCrIpT:alert(1)")).toBeNull();
    expect(safeHref("//evil.com/x")).toBeNull();
    expect(safeHref("javascript&#58;alert(1)")).toBeNull();
  });

  it("handles empty and non-string input", () => {
    const empty: string | null | undefined = undefined;
    expect(safeHref(null)).toBeNull();
    expect(safeHref(empty)).toBeNull();
    expect(safeHref("")).toBeNull();
    expect(safeHref(" ".repeat(3))).toBeNull();
  });

  it("isSafeHref mirrors safeHref", () => {
    expect(isSafeHref("https://example.com")).toBe(true);
    expect(isSafeHref("javascript:alert(1)")).toBe(false);
  });
});
