export interface ApiErrorDetail {
  code: string;
  message: string;
  translation_key?: string | null;
  details?: Record<string, unknown> | null;
  request_id?: string | null;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorDetail;
}

export function extractTranslationKey(error: unknown): string | null {
  if (!error || typeof error !== "object" || !("data" in error)) return null;
  const data = (error as { data: unknown }).data;
  if (!data || typeof data !== "object") return null;
  return (data as ApiErrorResponse).error?.translation_key ?? null;
}

export function extractApiError(error: unknown, fallback: string): string {
  if (!error || typeof error !== "object" || !("data" in error)) return fallback;

  const data = (error as { data: unknown }).data;
  if (!data || typeof data !== "object") return fallback;

  const apiError = data as ApiErrorResponse;
  const err = apiError.error;

  if (!err) {
    const detail = (data as Record<string, unknown>).detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((d: { msg?: string }) => d.msg)
        .filter(Boolean)
        .join("; ");
      if (messages) return messages;
    }
    if (typeof detail === "string") return detail;
    return fallback;
  }

  if (err.message) return err.message;
  return fallback;
}
