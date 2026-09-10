import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, Record<string, string | string[]>> = {
      website: {
        homeTitle: "Welcome to AskTea.ai",
        homeSubtitle: "Your comprehensive e-commerce platform.",
        featuresTitle: "What We Offer",
        features: ["AI-powered product search", "Smart descriptions"],
        homeCta: "Get Started",
        aboutTitle: "About AskTea.ai",
        aboutText: "About text",
        aboutMission: "Our Mission",
        aboutMissionText: "Mission text",
        chatTitle: "Chat with Our AI",
      },
      app: { tagline: "Comprehensive e-commerce platform", name: "AskTea.ai" },
    };
    const lookup = (key: string) => messages[namespace]?.[key] ?? key;
    return Object.assign(lookup, { raw: lookup });
  },
  useLocale: () => "en",
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
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
    status: "idle",
    canSend: false,
    streaming: false,
    sendMessage: () => true,
    sendSimilar: () => true,
    retry: () => true,
    mergeHistory: () => {},
    reset: () => {},
  }),
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

import WebsiteHomePage from "@/app/[locale]/(website)/page";
import AboutUsPage from "@/app/[locale]/(website)/about/page";

describe("Website pages", () => {
  it("home page shows the main page logo", () => {
    render(<WebsiteHomePage />);
    expect(screen.getByRole("img", { name: "AskTea.ai" })).toHaveAttribute(
      "src",
      "/main-page-logo.svg",
    );
  });

  it("about page shows the about title", () => {
    render(<AboutUsPage />);
    expect(screen.getByRole("heading", { name: "About AskTea.ai" })).toBeInTheDocument();
  });
});
