import { describe, it, expect } from "vitest";
import { countries, defaultCountry, getCountryByCode, getCountryByDialCode } from "../countries";

describe("countries", () => {
  it("should have Kuwait as first entry (default)", () => {
    expect(countries[0]!.code).toBe("KW");
    expect(countries[0]!.name).toBe("Kuwait");
    expect(countries[0]!.dialCode).toBe("+965");
  });

  it("should have defaultCountry equal to first entry", () => {
    expect(defaultCountry).toBe(countries[0]);
  });

  it("should have all required fields for every entry", () => {
    for (const c of countries) {
      expect(c.code).toBeTruthy();
      expect(c.name).toBeTruthy();
      expect(c.nameAr).toBeTruthy();
      expect(c.nameFa).toBeTruthy();
      expect(c.dialCode).toBeTruthy();
      expect(c.flag).toBeTruthy();
    }
  });

  it("should have unique codes", () => {
    const codes = countries.map((c) => c.code);
    expect(new Set(codes).size).toBe(codes.length);
  });
});

describe("getCountryByCode", () => {
  it("should find Kuwait by 'KW'", () => {
    const c = getCountryByCode("KW");
    expect(c?.name).toBe("Kuwait");
  });

  it("should find UAE by 'AE'", () => {
    const c = getCountryByCode("AE");
    expect(c?.name).toBe("United Arab Emirates");
  });

  it("should return undefined for unknown code", () => {
    expect(getCountryByCode("XX")).toBeUndefined();
  });

  it("should be case-sensitive", () => {
    expect(getCountryByCode("kw")).toBeUndefined();
  });
});

describe("getCountryByDialCode", () => {
  it("should find Kuwait by '+965'", () => {
    const c = getCountryByDialCode("+965");
    expect(c?.code).toBe("KW");
  });

  it("should find first country when dial code is shared (US/CA +1)", () => {
    const c = getCountryByDialCode("+1");
    expect(c?.code).toBe("US");
  });

  it("should return undefined for unknown dial code", () => {
    expect(getCountryByDialCode("+000")).toBeUndefined();
  });
});
