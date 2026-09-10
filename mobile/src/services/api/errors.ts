import axios from 'axios';
import type {TFunction} from 'i18next';
import type {ApiErrorBody} from '../../types/api';

export const DEFAULT_API_ERROR = 'An error occurred. Please try again';

export type ErrorKind =
  'timeout' | 'offline' | 'unauthorized' | 'validation' | 'server' | 'unknown';

export interface ClassifiedError {
  kind: ErrorKind;
  status?: number;
  translationKey: string | null;
}

const ERROR_KIND_KEYS: Record<ErrorKind, string> = {
  timeout: 'timeout',
  offline: 'network',
  unauthorized: 'not_authenticated',
  validation: 'generic',
  server: 'server',
  unknown: 'generic',
};

const getResponseData = (error: unknown): unknown => {
  if (!error || typeof error !== 'object' || !('response' in error)) {
    return undefined;
  }
  const response = error.response;
  if (!response || typeof response !== 'object' || !('data' in response)) {
    return undefined;
  }
  return response.data;
};

export const extractTranslationKey = (error: unknown): string | null => {
  const data = getResponseData(error);
  if (!data || typeof data !== 'object') {
    return null;
  }
  const body = data as ApiErrorBody;
  return body.error?.translation_key ?? null;
};

export const extractApiError = (
  error: unknown,
  fallback: string = DEFAULT_API_ERROR,
): string => {
  const data = getResponseData(error);
  if (data && typeof data === 'object') {
    const body = data as ApiErrorBody;
    if (body.error?.message) {
      return body.error.message;
    }
    const detail = body.detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) =>
          typeof entry === 'object' && entry !== null && 'msg' in entry
            ? String((entry as {msg: unknown}).msg)
            : '',
        )
        .filter((message) => message !== '');
      if (messages.length > 0) {
        return messages.join('; ');
      }
    } else if (typeof detail === 'string') {
      return detail;
    }
  }
  if (error && typeof error === 'object' && 'message' in error) {
    const message = error.message;
    if (typeof message === 'string' && message !== '') {
      return message;
    }
  }
  return fallback;
};

export const extractError = (error: unknown): string => {
  return extractApiError(error);
};

export const classifyError = (error: unknown): ClassifiedError => {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') {
      return {kind: 'timeout', translationKey: null};
    }
    if (!error.response) {
      return {kind: 'offline', translationKey: null};
    }
    const status = error.response.status;
    if (status === 401) {
      return {
        kind: 'unauthorized',
        status,
        translationKey: extractTranslationKey(error),
      };
    }
    if (status >= 400 && status < 500) {
      return {
        kind: 'validation',
        status,
        translationKey: extractTranslationKey(error),
      };
    }
    if (status >= 500) {
      return {
        kind: 'server',
        status,
        translationKey: extractTranslationKey(error),
      };
    }
  }
  return {kind: 'unknown', translationKey: null};
};

export const toUserMessage = (error: unknown, t: TFunction): string => {
  const classified = classifyError(error);
  if (classified.translationKey) {
    return t(classified.translationKey, {
      ns: 'error',
      defaultValue: extractApiError(error),
    });
  }
  const kindKey = ERROR_KIND_KEYS[classified.kind];
  const translated = t(kindKey, {ns: 'error'});
  if (translated !== kindKey) {
    return translated;
  }
  return extractApiError(error);
};
