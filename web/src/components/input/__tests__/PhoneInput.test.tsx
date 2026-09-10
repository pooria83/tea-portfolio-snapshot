import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PhoneInputSection } from "../PhoneInput";
import { NextIntlClientProvider } from "next-intl";

const messages = {
  auth: {
    phone: "Phone Number",
    sendOtp: "Send Verification Code",
    searchCountry: "Search country...",
    noCountryFound: "No country found",
    phonePlaceholder: "501234567",
    or: "or",
    googleLogin: "Continue with Google",
  },
  common: {},
};

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("PhoneInputSection", () => {
  it("should render phone input and submit button", () => {
    render(
      <PhoneInputSection
        onSubmit={vi.fn()}
        onGoogleLogin={vi.fn()}
        loading={false}
        error={null}
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    expect(screen.getByLabelText("Phone Number")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send Verification Code" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
  });

  it("should call onSubmit with phone value including dial code", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <PhoneInputSection
        onSubmit={onSubmit}
        onGoogleLogin={vi.fn()}
        loading={false}
        error={null}
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    await user.type(screen.getByLabelText("Phone Number"), "0912345678");
    await user.click(screen.getByRole("button", { name: "Send Verification Code" }));

    expect(onSubmit).toHaveBeenCalledWith("+9650912345678");
  });

  it("should display error message", () => {
    render(
      <PhoneInputSection
        onSubmit={vi.fn()}
        onGoogleLogin={vi.fn()}
        loading={false}
        error="رقم الهاتف غير صحيح"
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    expect(screen.getByText("رقم الهاتف غير صحيح")).toBeInTheDocument();
  });

  it("should disable button when loading", () => {
    render(
      <PhoneInputSection
        onSubmit={vi.fn()}
        onGoogleLogin={vi.fn()}
        loading={true}
        error={null}
        onClearError={vi.fn()}
      />,
      { wrapper },
    );

    expect(screen.getByRole("button", { name: "Send Verification Code..." })).toBeDisabled();
  });
});
