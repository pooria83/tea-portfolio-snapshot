import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;

  let mod: { default: Record<string, unknown> };
  if (locale === "ar") {
    mod = await import("../../messages/ar.json");
  } else if (locale === "fa") {
    mod = await import("../../messages/fa.json");
  } else {
    mod = await import("../../messages/en.json");
  }
  const messages = mod.default;

  return {
    locale,
    messages,
  };
});
