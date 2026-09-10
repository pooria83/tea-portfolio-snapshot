import { test, expect } from "@playwright/test";

test.describe("Login flow - Arabic", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/ar/login");
  });

  test("should render login page in Arabic", async ({ page }) => {
    await expect(page.getByText("AskTea.ai")).toBeVisible();
    await expect(page.getByText("رقم الهاتف")).toBeVisible();
    await expect(page.getByRole("button", { name: "إرسال رمز التحقق" })).toBeVisible();
  });

  test("should show error for invalid phone", async ({ page }) => {
    await page.getByLabel("رقم الهاتف").fill("12");
    await page.getByRole("button", { name: "إرسال رمز التحقق" }).click();
    await expect(page.getByText("رقم الهاتف غير صحيح")).toBeVisible();
  });

  test("should transition to OTP step with valid phone", async ({ page }) => {
    await page.getByLabel("رقم الهاتف").fill("0912345678");
    await page.getByRole("button", { name: "إرسال رمز التحقق" }).click();
    await expect(page.getByText("رمز التحقق")).toBeVisible();
    await expect(page.getByText("0912345678")).toBeVisible();
  });

  test("should complete full login flow", async ({ page }) => {
    await page.getByLabel("رقم الهاتف").fill("0912345678");
    await page.getByRole("button", { name: "إرسال رمز التحقق" }).click();
    await expect(page.getByText("رمز التحقق")).toBeVisible();

    const otpInputs = page.locator("[data-slot='input-otp'] input");
    await otpInputs.nth(0).fill("1");
    await otpInputs.nth(1).fill("2");
    await otpInputs.nth(2).fill("3");
    await otpInputs.nth(3).fill("4");

    await page.getByRole("button", { name: "تأكيد" }).click();
    await expect(page.getByText("تم تسجيل الدخول بنجاح")).toBeVisible();
  });
});
