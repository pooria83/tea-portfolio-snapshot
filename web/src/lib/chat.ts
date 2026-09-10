export const CHAT_ERROR_CODES = [
  "chat_failed",
  "chat_limit_reached",
  "conversation_closed",
  "conversation_not_found",
  "chat_not_available",
  "embedding_failed",
  "product_not_found",
  "chat_engine_failed",
  "empty_content",
  "message_too_large",
  "missing_product_id",
  "invalid_frame",
  "unsupported_frame",
] as const;

export type ChatErrorCode = (typeof CHAT_ERROR_CODES)[number];

export function isChatErrorCode(code: string): code is ChatErrorCode {
  return (CHAT_ERROR_CODES as readonly string[]).includes(code);
}

const relativeTimeFormatters = new Map<string, Intl.RelativeTimeFormat>();

function getRelativeTimeFormatter(locale: string): Intl.RelativeTimeFormat {
  let formatter = relativeTimeFormatters.get(locale);
  if (!formatter) {
    formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    relativeTimeFormatters.set(locale, formatter);
  }
  return formatter;
}

export function relativeTime(iso: string, locale: string): string {
  const diffMinutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  const formatter = getRelativeTimeFormatter(locale);
  if (Math.abs(diffMinutes) < 60) {
    return formatter.format(-diffMinutes, "minute");
  }
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return formatter.format(-diffHours, "hour");
  }
  return formatter.format(-Math.round(diffHours / 24), "day");
}

export async function copyTextToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.warn("clipboard_api_failed", error);
    }
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    document.execCommand("copy");
    textarea.remove();
    return true;
  } catch (error) {
    console.warn("clipboard_fallback_failed", error);
    return false;
  }
}
