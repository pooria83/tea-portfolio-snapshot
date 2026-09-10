import { test, expect } from "@playwright/test";

test.describe("Login flow - English", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/en/login");
  });

  test("should render login page in English", async ({ page }) => {
    await expect(page.getByText("AskTea.ai")).toBeVisible();
    await expect(page.getByText("Phone Number")).toBeVisible();
    await expect(page.getByRole("button", { name: "Send Verification Code" })).toBeVisible();
  });

  test("should show error for invalid phone", async ({ page }) => {
    await page.getByLabel("Phone Number").fill("12");
    await page.getByRole("button", { name: "Send Verification Code" }).click();
    await expect(page.getByText("رقم الهاتف غير صحيح")).toBeVisible();
  });

  test("should transition to OTP step with valid phone", async ({ page }) => {
    await page.getByLabel("Phone Number").fill("0912345678");
    await page.getByRole("button", { name: "Send Verification Code" }).click();
    await expect(page.getByText("Verification Code")).toBeVisible();
    await expect(page.getByText("0912345678")).toBeVisible();
  });

  test("should complete full login flow", async ({ page }) => {
    await page.getByLabel("Phone Number").fill("0912345678");
    await page.getByRole("button", { name: "Send Verification Code" }).click();
    await expect(page.getByText("Verification Code")).toBeVisible();

    const otpInputs = page.locator("[data-slot='input-otp'] input");
    await otpInputs.nth(0).fill("1");
    await otpInputs.nth(1).fill("2");
    await otpInputs.nth(2).fill("3");
    await otpInputs.nth(3).fill("4");

    await page.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByText("تم تسجيل الدخول بنجاح")).toBeVisible();
  });
});
