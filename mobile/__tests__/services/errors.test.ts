import {AxiosError, AxiosHeaders} from 'axios';
import {
  classifyError,
  toUserMessage,
  extractApiError,
} from '../../src/services/api/errors';
import {redact} from '../../src/services/logging/logger';

const makeAxiosError = (
  status: number | null,
  code: string | undefined,
  data: unknown,
) => {
  return new AxiosError(
    'Request failed',
    code,
    {headers: new AxiosHeaders(), url: '/x'},
    null,
    status != null ? {status, data, headers: new AxiosHeaders()} : undefined,
  );
};

const t = (key: string, options?: {defaultValue?: string}) =>
  options?.defaultValue ?? key;

describe('classifyError', () => {
  it('classifies timeouts', () => {
    const error = makeAxiosError(null, 'ECONNABORTED', undefined);
    expect(classifyError(error)).toEqual({
      kind: 'timeout',
      translationKey: null,
    });
  });

  it('classifies offline requests', () => {
    const error = makeAxiosError(null, undefined, undefined);
    expect(classifyError(error)).toEqual({
      kind: 'offline',
      translationKey: null,
    });
  });

  it('classifies 401 as unauthorized', () => {
    const error = makeAxiosError(401, undefined, {
      error: {translation_key: 'invalid_otp'},
    });
    expect(classifyError(error)).toEqual({
      kind: 'unauthorized',
      status: 401,
      translationKey: 'invalid_otp',
    });
  });

  it('classifies 4xx as validation', () => {
    const error = makeAxiosError(422, undefined, {detail: 'bad'});
    expect(classifyError(error)).toEqual({
      kind: 'validation',
      status: 422,
      translationKey: null,
    });
  });

  it('classifies 5xx as server', () => {
    const error = makeAxiosError(500, undefined, {detail: 'boom'});
    expect(classifyError(error)).toEqual({
      kind: 'server',
      status: 500,
      translationKey: null,
    });
  });

  it('falls back to unknown', () => {
    expect(classifyError(new Error('boom'))).toEqual({
      kind: 'unknown',
      translationKey: null,
    });
  });
});

describe('toUserMessage', () => {
  it('prefers the backend translation key', () => {
    const error = makeAxiosError(409, undefined, {
      error: {translation_key: 'phone_already_linked', message: 'raw'},
    });
    const tWithKey = (key: string) =>
      key === 'phone_already_linked' ? 'Phone linked elsewhere' : key;
    expect(toUserMessage(error, tWithKey)).toBe('Phone linked elsewhere');
  });

  it('falls back to the kind key', () => {
    const offline = makeAxiosError(null, undefined, undefined);
    const tKind = (key: string) => (key === 'network' ? 'Check network' : key);
    expect(toUserMessage(offline, tKind)).toBe('Check network');
  });

  it('falls back to the extracted API message', () => {
    const error = makeAxiosError(500, undefined, {
      error: {message: 'Server blew up'},
    });
    expect(toUserMessage(error, t)).toBe('Server blew up');
  });
});

describe('extractApiError', () => {
  it('joins detail arrays', () => {
    const error = makeAxiosError(422, undefined, {
      detail: [{msg: 'a'}, {msg: 'b'}],
    });
    expect(extractApiError(error)).toBe('a; b');
  });
});

describe('redact', () => {
  it('redacts sensitive keys at any depth', () => {
    const input = {
      access_token: 'abc',
      user: {id_token: 'xyz', name: 'A'},
      ok: 'fine',
      list: [{password: 'p1'}],
    };
    expect(redact(input)).toEqual({
      access_token: '[REDACTED]',
      user: {id_token: '[REDACTED]', name: 'A'},
      ok: 'fine',
      list: [{password: '[REDACTED]'}],
    });
  });

  it('passes through primitives', () => {
    expect(redact('plain')).toBe('plain');
    expect(redact(42)).toBe(42);
  });
});
