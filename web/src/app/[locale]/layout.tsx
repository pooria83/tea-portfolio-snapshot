import type { ReactNode } from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { ReduxProvider } from "@/components/providers/ReduxProvider";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { ErrorBoundary } from "@/components/providers/ErrorBoundary";
import { DirectionSetter } from "@/components/providers/DirectionProvider";
import { ScrollToTop } from "@/components/shared/ScrollToTop";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export const metadata: Metadata = {
  title: "AskTea.ai",
  description: "Comprehensive e-commerce platform",
};

type Props = {
  children: ReactNode;
  params: Promise<{ locale: string }>;
};

async function loadMessages(locale: string) {
  let mod: { default: Record<string, unknown> };
  if (locale === "ar") {
    mod = await import("../../../messages/ar.json");
  } else if (locale === "fa") {
    mod = await import("../../../messages/fa.json");
  } else {
    mod = await import("../../../messages/en.json");
  }
  return mod.default;
}

export default async function LocaleLayout({ children, params }: Props) {
  const { locale } = await params;

  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  setRequestLocale(locale);

  const messages = await loadMessages(locale);

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <ThemeProvider>
        <ReduxProvider>
          <ErrorBoundary>
            <TooltipProvider>
              <DirectionSetter locale={locale} />
              {children}
              <Toaster />
              <ScrollToTop />
            </TooltipProvider>
          </ErrorBoundary>
        </ReduxProvider>
      </ThemeProvider>
    </NextIntlClientProvider>
  );
}
