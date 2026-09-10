import {
  extractApiError,
  extractError,
  extractTranslationKey,
} from '../../../src/services/api/errors';

describe('extractError', () => {
  it('returns the message from an Error instance', () => {
    expect(extractError(new Error('Network down'))).toBe('Network down');
  });

  it('returns the envelope error message for API errors', () => {
    const axiosError = {
      response: {
        data: {
          success: false,
          error: {message: 'Invalid OTP', translation_key: 'invalid_otp'},
        },
      },
    };
    expect(extractError(axiosError)).toBe('Invalid OTP');
  });

  it('falls back to the legacy detail string', () => {
    const legacyError = {
      response: {
        data: {detail: 'Phone number not registered'},
      },
    };
    expect(extractError(legacyError)).toBe('Phone number not registered');
  });

  it('ignores a detail array and uses the fallback', () => {
    const arrayError = {
      response: {data: {detail: ['field is required']}},
    };
    expect(extractError(arrayError)).toBe(
      'An error occurred. Please try again',
    );
  });

  it('returns the fallback for unknown shapes', () => {
    expect(extractError('string error')).toBe(
      'An error occurred. Please try again',
    );
    expect(extractError(undefined)).toBe('An error occurred. Please try again');
  });
});

describe('extractApiError', () => {
  it('joins pydantic-style detail array messages', () => {
    const error = {
      response: {
        data: {
          detail: [
            {msg: 'phone is required'},
            {msg: 'phone must be a valid number'},
          ],
        },
      },
    };
    expect(extractApiError(error)).toBe(
      'phone is required; phone must be a valid number',
    );
  });

  it('uses the custom fallback when nothing matches', () => {
    expect(extractApiError({}, 'custom fallback')).toBe('custom fallback');
  });

  it('prefers the envelope message over the detail', () => {
    const error = {
      response: {
        data: {
          error: {message: 'envelope message'},
          detail: 'legacy detail',
        },
      },
    };
    expect(extractApiError(error)).toBe('envelope message');
  });
});

describe('extractTranslationKey', () => {
  it('returns the translation key from the envelope', () => {
    const error = {
      response: {
        data: {error: {message: 'Invalid OTP', translation_key: 'invalid_otp'}},
      },
    };
    expect(extractTranslationKey(error)).toBe('invalid_otp');
  });

  it('returns null when there is no key', () => {
    expect(extractTranslationKey(new Error('Network down'))).toBeNull();
    expect(extractTranslationKey({response: {data: {}}})).toBeNull();
  });
});
