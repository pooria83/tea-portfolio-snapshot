import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string) => {
    const messages: Record<string, Record<string, string>> = {
      app: { name: "AskTea.ai" },
      website: {
        home: "Home",
        about: "About Us",
        login: "Login",
        openMenu: "Open menu",
      },
    };
    return messages[namespace]?.[key] ?? key;
  },
  useLocale: () => "en",
}));

vi.mock("@/i18n/routing", () => ({
  Link: ({
    href,
    children,
    className,
    onClick,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
  }) => (
    <a href={href} className={className} onClick={onClick}>
      {children}
    </a>
  ),
  usePathname: () => "/",
  useRouter: () => ({ replace: () => {} }),
  routing: { locales: ["ar", "en", "fa"], defaultLocale: "en" },
}));

vi.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PopoverContent: () => null,
  PopoverTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/ui/command", () => ({
  Command: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  CommandList: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  CommandItem: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  CommandGroup: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { WebsiteNavbar } from "@/components/website/WebsiteNavbar";

describe("WebsiteNavbar", () => {
  it("renders brand name", () => {
    render(<WebsiteNavbar />);
    expect(screen.getByText("AskTea.ai")).toBeInTheDocument();
  });

  it("renders home, about and login links", () => {
    render(<WebsiteNavbar />);
    expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "About Us" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Login" })).toBeInTheDocument();
  });

  it("renders a hamburger menu button for responsive mode", () => {
    render(<WebsiteNavbar />);
    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
  });

  it("links home to / and about to /about", () => {
    render(<WebsiteNavbar />);
    expect(screen.getByRole("link", { name: "Home" }).getAttribute("href")).toBe("/");
    expect(screen.getByRole("link", { name: "About Us" }).getAttribute("href")).toBe("/about");
  });

  it("links login to /login", () => {
    render(<WebsiteNavbar />);
    expect(screen.getByRole("link", { name: "Login" }).getAttribute("href")).toBe("/login");
  });
});
