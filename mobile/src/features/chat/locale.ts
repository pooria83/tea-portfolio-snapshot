export function localeValue(
  locale: string,
  valueAr: string,
  valueFa: string,
  valueEn: string,
): string {
  if (locale === 'ar') {
    return valueAr;
  }
  if (locale === 'fa') {
    return valueFa;
  }
  return valueEn;
}

export function newIdempotencyKey(): string {
  const cryptoApi = (
    globalThis as unknown as {
      crypto?: {randomUUID?: () => string};
    }
  ).crypto;
  if (typeof cryptoApi?.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = (Math.random() * 16) | 0;
    const value = char === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export function relativeTime(iso: string, locale: string): string {
  const time = new Date(iso).getTime();
  if (!Number.isFinite(time)) {
    return '';
  }
  try {
    const diffMinutes = Math.round((Date.now() - time) / 60_000);
    const formatter = new Intl.RelativeTimeFormat(locale, {
      numeric: 'auto',
    });
    if (Math.abs(diffMinutes) < 60) {
      return formatter.format(-diffMinutes, 'minute');
    }
    const diffHours = Math.round(diffMinutes / 60);
    if (Math.abs(diffHours) < 24) {
      return formatter.format(-diffHours, 'hour');
    }
    return formatter.format(-Math.round(diffHours / 24), 'day');
  } catch {
    return '';
  }
}
