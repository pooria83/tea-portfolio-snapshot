import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { OtpInputSection } from "../OtpInput";
import { NextIntlClientProvider } from "next-intl";

beforeAll(() => {
  if (typeof document !== "undefined" && !document.elementFromPoint) {
    document.elementFromPoint = () => null;
  }
});

beforeEach(() => {
  vi.useFakeTimers({
    toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"],
  });
});

afterEach(() => {
  vi.useRealTimers();
});

const messages = {
  auth: {
    otp: "Verification Code",
    enterOtp: "Enter the verification code sent to your phone",
    verifyOtp: "Verify",
    back: "Back",
  },
};

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("OtpInputSection", () => {
  it("should render OTP input and buttons", () => {
    render(
      <OtpInputSection
        phone="0912345678"
        onSubmit={vi.fn()}
        onBack={vi.fn()}
        loading={false}
        error={null}
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    expect(screen.getByText("0912345678")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Verify" })).toBeInTheDocument();
  });

  it("should call onBack when back button clicked", () => {
    const onBack = vi.fn();

    render(
      <OtpInputSection
        phone="0912345678"
        onSubmit={vi.fn()}
        onBack={onBack}
        loading={false}
        error={null}
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("should display error message", () => {
    render(
      <OtpInputSection
        phone="0912345678"
        onSubmit={vi.fn()}
        onBack={vi.fn()}
        loading={false}
        error="رمز التحقق غير صحيح"
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    expect(screen.getByText("رمز التحقق غير صحيح")).toBeInTheDocument();
  });

  it("should disable verify button when loading", () => {
    render(
      <OtpInputSection
        phone="0912345678"
        onSubmit={vi.fn()}
        onBack={vi.fn()}
        loading={true}
        error={null}
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    expect(screen.getByRole("button", { name: "Verify..." })).toBeDisabled();
  });
});
