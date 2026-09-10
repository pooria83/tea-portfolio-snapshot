import { describe, expect, it } from "vitest";
import { parse } from "@formatjs/icu-messageformat-parser";

import en from "../../../messages/en.json";
import ar from "../../../messages/ar.json";
import fa from "../../../messages/fa.json";

function collectStrings(obj: Record<string, unknown>, path: string, out: [string, string][]) {
  for (const [key, value] of Object.entries(obj)) {
    const next = path ? `${path}.${key}` : key;
    if (typeof value === "string") {
      out.push([next, value]);
    } else if (value && typeof value === "object") {
      collectStrings(value as Record<string, unknown>, next, out);
    }
  }
}

const localeFiles: Record<string, Record<string, unknown>> = { en, ar, fa };

describe("locale messages", () => {
  it.each(["en", "ar", "fa"])("every %s message is valid ICU MessageFormat", (locale) => {
    const entries: [string, string][] = [];
    collectStrings(localeFiles[locale] as Record<string, unknown>, "", entries);

    for (const [key, message] of entries) {
      expect(() => parse(message), `${locale}.${key}`).not.toThrow();
    }
  });
});
