import {logger, type transportFunctionType} from 'react-native-logs';
import * as Sentry from '@sentry/react-native';
import Config from 'react-native-config';

const SENSITIVE_KEY_PATTERN =
  /token|password|passwd|secret|authorization|id_token|refresh_token|access_token|api[_-]?key/i;

export const redact = (value: unknown, key = ''): unknown => {
  if (SENSITIVE_KEY_PATTERN.test(key)) {
    return '[REDACTED]';
  }
  if (Array.isArray(value)) {
    return value.map((item) => redact(item));
  }
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [childKey, childValue] of Object.entries(value)) {
      out[childKey] = redact(childValue, childKey);
    }
    return out;
  }
  return value;
};

let context: Record<string, unknown> = {};

export const setLogContext = (update: Record<string, unknown>): void => {
  context = {...context, ...update};
};

const stringify = (message: unknown): string => {
  if (typeof message === 'string') {
    return message;
  }
  try {
    return JSON.stringify(redact(message));
  } catch {
    return String(message);
  }
};

const consoleTransport: transportFunctionType<Record<string, never>> = ({
  level,
  rawMsg,
}) => {
  const consoleMethod =
    level.text === 'error'
      ? console.error
      : level.text === 'warn'
        ? console.warn
        : level.text === 'info'
          ? console.info
          : console.debug;
  const messages = rawMsg as unknown[];
  if (messages.length === 0) {
    return;
  }
  const last = messages[messages.length - 1];
  const hasData = typeof last === 'object' && last !== null;
  const message = hasData ? messages.slice(0, -1) : messages;
  const data = hasData ? (last as Record<string, unknown>) : {};
  const enriched: Record<string, unknown> = {...context, ...data};
  if (message.length === 1 && typeof message[0] === 'string') {
    consoleMethod(message[0], enriched);
  } else {
    consoleMethod(message, enriched);
  }
};

const SENTRY_LEVELS: Record<string, Sentry.SeverityLevel> = {
  debug: 'debug',
  info: 'info',
  warn: 'warning',
  error: 'error',
};

const sentryTransport: transportFunctionType<Record<string, never>> = ({
  level,
  msg,
}) => {
  if (level.severity < 2) {
    return;
  }
  const sentryLevel: Sentry.SeverityLevel =
    SENTRY_LEVELS[level.text] ?? 'error';
  Sentry.addBreadcrumb({message: msg, level: sentryLevel});
  if (level.text === 'error') {
    Sentry.captureMessage(msg, 'error');
  }
};

export const log = logger.createLogger({
  levels: {debug: 0, info: 1, warn: 2, error: 3},
  severity: Config.ENV === 'production' ? 'info' : 'debug',
  transport: [consoleTransport, sentryTransport],
  async: false,
  stringifyFunc: stringify,
  printDate: true,
  printLevel: true,
  enabled: true,
});
