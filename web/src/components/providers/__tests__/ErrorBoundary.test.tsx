import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { ErrorBoundary } from "../ErrorBoundary";

const messages = {
  common: {
    errorTitle: "Something went wrong",
    unexpectedError: "An unexpected error occurred",
    retry: "Try again",
  },
};

function renderWithIntl(ui: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  );
}

function GoodChild() {
  return <div>Good child</div>;
}

function BadChild({ message }: { message?: string }): React.ReactNode {
  throw new Error(message ?? "Test error");
}

function ChildWithNoMessage(): React.ReactNode {
  throw new Error();
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("should render children when there is no error", () => {
    renderWithIntl(
      <ErrorBoundary>
        <GoodChild />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Good child")).toBeInTheDocument();
  });

  it("should catch error and show fallback UI", () => {
    renderWithIntl(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Test error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("should show fallback when error has no message", () => {
    renderWithIntl(
      <ErrorBoundary>
        <ChildWithNoMessage />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("should render custom fallback when provided", () => {
    renderWithIntl(
      <ErrorBoundary fallback={<div>Custom error UI</div>}>
        <BadChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Custom error UI")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("should recover after clicking retry", async () => {
    let shouldThrow = true;
    function ConditionalChild(): React.ReactNode {
      if (shouldThrow) {
        throw new Error("Temp error");
      }
      return <div>Good child</div>;
    }

    renderWithIntl(
      <ErrorBoundary key="eb">
        <ConditionalChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    shouldThrow = false;

    const user = userEvent.setup();
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Try again" }));
    });
  });
});
