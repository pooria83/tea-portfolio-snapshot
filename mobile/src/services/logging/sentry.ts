import * as Sentry from '@sentry/react-native';
import Config from 'react-native-config';
import type {User} from '../../types/api';

let initialized = false;

export const initSentry = (): void => {
  const dsn = Config.SENTRY_DSN;
  if (!dsn || dsn === '<sentry_dsn>') {
    return;
  }
  Sentry.init({
    dsn,
    environment: Config.ENV,
    tracesSampleRate: 0.1,
  });
  initialized = true;
};

const isSentryEnabled = (): boolean => initialized;

export const setSentryUser = (user: User | null): void => {
  if (!isSentryEnabled()) {
    return;
  }
  if (user != null) {
    const sentryUser: Sentry.User = {id: user.id};
    if (user.username != null) {
      sentryUser.username = user.username;
    }
    Sentry.setUser(sentryUser);
  } else {
    Sentry.setUser(null);
  }
};

export const setSentryRoute = (route: string | null): void => {
  if (!isSentryEnabled()) {
    return;
  }
  if (route != null) {
    Sentry.setTag('route', route);
  }
};
