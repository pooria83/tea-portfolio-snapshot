"use client";

import { useEffect } from "react";

function getDir(locale: string): string {
  return locale === "ar" || locale === "fa" ? "rtl" : "ltr";
}

export function DirectionSetter({ locale }: { locale: string }) {
  useEffect(() => {
    document.documentElement.dir = getDir(locale);
  }, [locale]);
  return null;
}
