import {useEffect} from 'react';
import {storage} from '../services/storage';
import {useAuthStore} from '../features/auth/authStore';
import client from '../services/api/client';
import {unwrapEnvelope} from '../services/api/envelope';
import {classifyError} from '../services/api/errors';
import {log} from '../services/logging/logger';
import type {User} from '../types/api';

const MAX_HYDRATE_ATTEMPTS = 3;
const HYDRATE_RETRY_DELAY_MS = 1500;

export const useAuth = () => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    let disposed = false;

    const hydrate = async (attempt: number) => {
      const tokens = await storage.getTokens();
      if (!tokens) {
        useAuthStore.getState().hydrate(null, null);
        return;
      }
      try {
        const response = await client.get('/users/me');
        const me = unwrapEnvelope<User>(response);
        if (!disposed) {
          useAuthStore.getState().setAuth(tokens.accessToken, me);
        }
      } catch (error) {
        const classified = classifyError(error);
        log.warn('auth hydrate failed', classified);
        if (classified.kind === 'unauthorized') {
          await storage.clearTokens();
          if (!disposed) {
            useAuthStore.getState().hydrate(null, null);
          }
          return;
        }
        if (attempt < MAX_HYDRATE_ATTEMPTS) {
          setTimeout(
            () => {
              void hydrate(attempt + 1);
            },
            HYDRATE_RETRY_DELAY_MS * (attempt + 1),
          );
          return;
        }
        if (!disposed) {
          useAuthStore.getState().hydrate(tokens.accessToken, null);
        }
      }
    };
    void hydrate(0);

    return () => {
      disposed = true;
    };
  }, []);

  return {isAuthenticated, hydrated, user};
};
