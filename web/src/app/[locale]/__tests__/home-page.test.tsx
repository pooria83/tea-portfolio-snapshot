import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string) => {
    const messages: Record<string, Record<string, string>> = {
      app: { name: "AskTea.ai", tagline: "Comprehensive e-commerce platform" },
      auth: { login: "Login" },
      website: {
        home: "Home",
        about: "About Us",
        login: "Login",
        openMenu: "Open menu",
        chatTitle: "Chat with Our AI",
      },
      "website.chat": {
        title: "Ask Our AI Assistant",
        description: "Get product recommendations instantly.",
        placeholder: "Ask about products, styles, or outfits...",
        inputPlaceholder: "Search for products, styles, or outfits...",
        back: "Back",
        send: "Send",
        connecting: "Connecting...",
        reconnecting: "Reconnecting...",
        thinking: "Thinking...",
        error: "Something went wrong.",
      },
      "website.products": {
        title: "Featured Products",
      },
      "admin.productSearch": {
        findSimilar: "Find similar products",
      },
    };
    return messages[namespace]?.[key] ?? key;
  },
  useLocale: () => "en",
}));

vi.mock("@/store/api/anonymousApi", () => ({
  useGetAnonymousChatSessionMutation: () => [
    vi.fn().mockReturnValue({ unwrap: () => Promise.resolve({}) }),
    { isLoading: false },
  ],
  useGetRandomProductsQuery: () => ({
    data: [],
    isLoading: false,
  }),
}));

vi.mock("@/hooks/useChat", () => ({
  useChat: () => ({
    messages: [],
    status: "open",
    canSend: true,
    streaming: false,
    sendMessage: () => true,
    sendSimilar: () => true,
    retry: () => true,
    mergeHistory: () => {},
    reset: () => {},
  }),
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

vi.mock("next/image", () => ({
  __esModule: true,
  default: ({
    alt,
    src,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement> & { src: string }) => (
    <img alt={alt} src={src} {...props} />
  ),
}));

import HomePage from "@/app/[locale]/(website)/page";

describe("HomePage", () => {
  it("renders the main page logo", () => {
    render(<HomePage />);
    const logo = screen.getByRole("img", { name: "AskTea.ai" });
    expect(logo).toHaveAttribute("src", "/main-page-logo.svg");
  });

  it("renders the anonymous chat box", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("textbox", { name: "Search for products, styles, or outfits..." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });
});
