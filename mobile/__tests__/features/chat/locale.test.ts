import {
  localeValue,
  newIdempotencyKey,
  relativeTime,
} from '../../../src/features/chat/locale';

describe('localeValue', () => {
  it('returns the value for the active locale', () => {
    expect(localeValue('ar', 'عربية', 'فارسی', 'English')).toBe('عربية');
    expect(localeValue('fa', 'عربية', 'فارسی', 'English')).toBe('فارسی');
    expect(localeValue('en', 'عربية', 'فارسی', 'English')).toBe('English');
  });
});

describe('newIdempotencyKey', () => {
  it('returns a uuid-shaped key', () => {
    expect(newIdempotencyKey()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
  });

  it('falls back to a manual key when crypto is unavailable', () => {
    const original = globalThis.crypto;
    Object.defineProperty(globalThis, 'crypto', {
      value: undefined,
      configurable: true,
    });
    try {
      expect(newIdempotencyKey()).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
      );
    } finally {
      Object.defineProperty(globalThis, 'crypto', {
        value: original,
        configurable: true,
      });
    }
  });
});

describe('relativeTime', () => {
  const now = Date.now();

  it('returns an empty string for an invalid date', () => {
    expect(relativeTime('not-a-date', 'en')).toBe('');
  });

  it('formats minutes for recent activity', () => {
    expect(
      relativeTime(new Date(now - 5 * 60_000).toISOString(), 'en'),
    ).toContain('minute');
  });

  it('formats hours for activity within a day', () => {
    expect(
      relativeTime(new Date(now - 3 * 3_600_000).toISOString(), 'en'),
    ).toContain('hour');
  });

  it('formats days for older activity', () => {
    expect(
      relativeTime(new Date(now - 5 * 24 * 3_600_000).toISOString(), 'en'),
    ).toContain('day');
  });
});
