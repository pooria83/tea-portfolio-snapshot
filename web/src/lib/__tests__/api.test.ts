import { describe, it, expect } from "vitest";
import { extractTranslationKey, extractApiError } from "../api";

describe("extractTranslationKey", () => {
  it("returns null for null or undefined input", () => {
    expect(extractTranslationKey(null)).toBeNull();
    expect(extractTranslationKey(undefined!)).toBeNull();
  });

  it("returns null for non-object input", () => {
    expect(extractTranslationKey("string")).toBeNull();
    expect(extractTranslationKey(42)).toBeNull();
  });

  it("returns null when error object lacks data property", () => {
    expect(extractTranslationKey({ message: "fail" })).toBeNull();
  });

  it("returns null when data is not an object", () => {
    expect(extractTranslationKey({ data: "not-an-object" })).toBeNull();
  });

  it("returns translation_key when present", () => {
    const error = {
      data: {
        error: { translation_key: "user_not_found" },
      },
    };
    expect(extractTranslationKey(error)).toBe("user_not_found");
  });

  it("returns null when translation_key is missing", () => {
    const error = {
      data: {
        error: { message: "User not found" },
      },
    };
    expect(extractTranslationKey(error)).toBeNull();
  });
});

describe("extractApiError", () => {
  const fallback = "Something went wrong";

  it("returns fallback for null input", () => {
    expect(extractApiError(null, fallback)).toBe(fallback);
  });

  it("returns fallback for undefined input", () => {
    expect(extractApiError(undefined, fallback)).toBe(fallback);
  });

  it("returns fallback for non-object input", () => {
    expect(extractApiError("error", fallback)).toBe(fallback);
    expect(extractApiError(500, fallback)).toBe(fallback);
  });

  it("returns error.message when present in envelope", () => {
    const error = {
      data: {
        success: false,
        error: { code: "NOT_FOUND", message: "User not found" },
      },
    };
    expect(extractApiError(error, fallback)).toBe("User not found");
  });

  it("returns fallback when envelope has no error and no detail", () => {
    const error = { data: {} };
    expect(extractApiError(error, fallback)).toBe(fallback);
  });

  it("returns joined messages when detail is an array of {msg}", () => {
    const error = {
      data: {
        detail: [{ msg: "Field required" }, { msg: "Invalid value" }],
      },
    };
    expect(extractApiError(error, fallback)).toBe("Field required; Invalid value");
  });

  it("returns detail string when detail is a string", () => {
    const error = {
      data: { detail: "Internal server error" },
    };
    expect(extractApiError(error, fallback)).toBe("Internal server error");
  });

  it("prefers error.message over detail", () => {
    const error = {
      data: {
        error: { code: "BAD_REQUEST", message: "Validation failed" },
        detail: "Old detail",
      },
    };
    expect(extractApiError(error, fallback)).toBe("Validation failed");
  });

  it("returns fallback when data is not an object", () => {
    const error = { data: "raw string" };
    expect(extractApiError(error, fallback)).toBe(fallback);
  });

  it("filters null/undefined messages from detail array", () => {
    const error = {
      data: {
        detail: [{ msg: "First" }, {}, { msg: "Third" }],
      },
    };
    expect(extractApiError(error, fallback)).toBe("First; Third");
  });
});
