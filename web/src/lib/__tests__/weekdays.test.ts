import { describe, it, expect } from "vitest";
import { getWeekdayNames } from "../weekdays";

describe("getWeekdayNames", () => {
  it("should return Arabic names for 'ar' locale", () => {
    const result = getWeekdayNames("ar");
    expect(result).toHaveLength(7);
    expect(result[0]!.day_of_week).toBe(6);
    expect(result[0]!.name).toBe("السبت");
    expect(result[1]!.day_of_week).toBe(0);
    expect(result[1]!.name).toBe("الأحد");
    expect(result[6]!.day_of_week).toBe(5);
    expect(result[6]!.name).toBe("الجمعة");
  });

  it("should return Farsi names for 'fa' locale", () => {
    const result = getWeekdayNames("fa");
    expect(result).toHaveLength(7);
    expect(result[0]!.day_of_week).toBe(6);
    expect(result[0]!.name).toBe("شنبه");
    expect(result[1]!.day_of_week).toBe(0);
    expect(result[1]!.name).toBe("یکشنبه");
    expect(result[6]!.day_of_week).toBe(5);
    expect(result[6]!.name).toBe("جمعه");
  });

  it("should return English names for 'en' locale", () => {
    const result = getWeekdayNames("en");
    expect(result).toHaveLength(7);
    expect(result[0]!.day_of_week).toBe(0);
    expect(result[0]!.name).toBe("Sunday");
    expect(result[1]!.day_of_week).toBe(1);
    expect(result[1]!.name).toBe("Monday");
    expect(result[6]!.day_of_week).toBe(6);
    expect(result[6]!.name).toBe("Saturday");
  });

  it("should return English names for unknown locale", () => {
    const result = getWeekdayNames("fr");
    expect(result).toHaveLength(7);
    expect(result[0]!.name).toBe("Sunday");
  });

  it("should start with Saturday for Arabic (weekend)", () => {
    const ar = getWeekdayNames("ar");
    expect(ar[0]!.day_of_week).toBe(6);
    expect(ar[6]!.day_of_week).toBe(5);
  });

  it("should start with Sunday for English", () => {
    const en = getWeekdayNames("en");
    expect(en[0]!.day_of_week).toBe(0);
  });
});
