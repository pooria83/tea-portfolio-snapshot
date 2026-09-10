import { describe, it, expect } from "vitest";

function isNotEmpty(v: string | undefined) {
  if (!v?.trim()) return "This field is required";
  return true;
}

function validatePrice(v: string | undefined) {
  if (!v) return true;
  const n = Number(v);
  if (Number.isNaN(n) || n <= 0) return "Enter a valid price greater than 0";
  return true;
}

function isValidPrice(v: string | undefined) {
  if (!v) return true;
  const n = Number(v);
  if (Number.isNaN(n) || n < 0) return "Enter a valid price greater than 0";
  return true;
}

function isValidInteger(v: string | undefined) {
  if (!v) return true;
  const n = Number(v);
  if (Number.isNaN(n) || n < 0 || !Number.isInteger(n)) return "Enter a valid quantity";
  return true;
}

describe("ProductForm field validation", () => {
  describe("price field (required + > 0)", () => {
    it("should reject empty value", () => {
      expect(isNotEmpty("")).toBe("This field is required");
    });

    it("should reject text", () => {
      expect(isNotEmpty("abc")).toBe(true);
      expect(validatePrice("abc")).toBe("Enter a valid price greater than 0");
    });

    it("should accept valid number", () => {
      expect(validatePrice("29.99")).toBe(true);
    });

    it("should reject zero", () => {
      expect(validatePrice("0")).toBe("Enter a valid price greater than 0");
    });

    it("should reject negative", () => {
      expect(validatePrice("-5")).toBe("Enter a valid price greater than 0");
    });
  });

  describe("original_price field (optional, >= 0)", () => {
    it("should accept empty (optional)", () => {
      expect(isValidPrice("")).toBe(true);
    });

    it("should reject text", () => {
      expect(isValidPrice("abc")).toBe("Enter a valid price greater than 0");
    });

    it("should accept valid number", () => {
      expect(isValidPrice("19.99")).toBe(true);
    });

    it("should accept zero", () => {
      expect(isValidPrice("0")).toBe(true);
    });

    it("should reject negative", () => {
      expect(isValidPrice("-5")).toBe("Enter a valid price greater than 0");
    });
  });

  describe("quantity field (optional, integer >= 0)", () => {
    it("should accept empty (optional)", () => {
      expect(isValidInteger("")).toBe(true);
    });

    it("should reject text", () => {
      expect(isValidInteger("abc")).toBe("Enter a valid quantity");
    });

    it("should reject float", () => {
      expect(isValidInteger("1.5")).toBe("Enter a valid quantity");
    });

    it("should accept valid integer", () => {
      expect(isValidInteger("50")).toBe(true);
    });

    it("should accept zero", () => {
      expect(isValidInteger("0")).toBe(true);
    });

    it("should reject negative", () => {
      expect(isValidInteger("-1")).toBe("Enter a valid quantity");
    });
  });
});
