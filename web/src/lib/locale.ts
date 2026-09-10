export function localeValue(
  locale: string,
  valueAr: string,
  valueFa: string,
  valueEn: string,
): string {
  if (locale === "ar") return valueAr;
  if (locale === "fa") return valueFa;
  return valueEn;
}

export function localeDirection(locale?: string): "rtl" | "ltr" | "auto" {
  if (!locale) return "auto";
  return locale === "ar" || locale === "fa" ? "rtl" : "ltr";
}
