const SAFE_SCHEMES = new Set(["http", "https"]);

export function safeHref(value: string | null | undefined): string | null {
  if (!value) return null;
  const cleaned = value.trim().replaceAll(/[\u0000-\u0020]+/g, "");
  if (!cleaned) return null;
  const match = cleaned.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/);
  if (!match) return null;
  const scheme = (match[1] ?? "").toLowerCase();
  if (!SAFE_SCHEMES.has(scheme)) return null;
  return cleaned;
}

export function isSafeHref(value: string): boolean {
  return safeHref(value) !== null;
}
