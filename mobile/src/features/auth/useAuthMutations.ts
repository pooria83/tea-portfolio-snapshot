import {useMutation} from '@tanstack/react-query';
import client from '../../services/api/client';
import {storage} from '../../services/storage';
import {classifyError, toUserMessage} from '../../services/api/errors';
import {unwrapEnvelope} from '../../services/api/envelope';
import {log} from '../../services/logging/logger';
import i18n from '../../i18n';
import {useAuthStore} from './authStore';
import type {
  GoogleAuthRequest,
  TokenResponse,
  User,
  VerifyOtpRequest,
} from '../../types/api';

const fetchUser = async (): Promise<User> => {
  const response = await client.get('/users/me');
  return unwrapEnvelope<User>(response);
};

const finishAuth = (accessToken: string, user: User): void => {
  useAuthStore.getState().setAuth(accessToken, user);
};

export const useSendOtpMutation = () => {
  const {setLoading, setError, setStep, setPhone} = useAuthStore.getState();

  return useMutation({
    mutationFn: async (phone: string) => {
      await client.post('/auth/send-otp', {phone});
      return phone;
    },
    onSuccess: (phone) => {
      setLoading(false);
      setError(null);
      setPhone(phone);
      setStep('otp');
    },
    onError: (error: unknown) => {
      setLoading(false);
      log.warn('sendOtp failed', classifyError(error));
      setError(toUserMessage(error, i18n.t));
    },
    onMutate: () => {
      setLoading(true);
      setError(null);
    },
  });
};

export const useVerifyOtpMutation = () => {
  const {setError, phone} = useAuthStore.getState();

  return useMutation({
    mutationFn: async (code: string) => {
      if (!phone) {
        throw new Error('No phone number in store');
      }
      const payload: VerifyOtpRequest = {phone, code};
      const response = await client.post<TokenResponse>(
        '/auth/verify-otp',
        payload,
      );
      await storage.setTokens(
        response.data.access_token,
        response.data.refresh_token,
      );
      const user = await fetchUser();
      return {token: response.data, user};
    },
    onSuccess: ({token, user}) => {
      finishAuth(token.access_token, user);
    },
    onError: (error: unknown) => {
      log.warn('verifyOtp failed', classifyError(error));
      setError(toUserMessage(error, i18n.t));
    },
  });
};

export const useGoogleAuthMutation = () => {
  const {setError, setLoading} = useAuthStore.getState();

  return useMutation({
    mutationFn: async (idToken: string) => {
      const payload: GoogleAuthRequest = {
        id_token: idToken,
        client_type: 'android',
      };
      const response = await client.post<TokenResponse>(
        '/auth/google',
        payload,
      );
      await storage.setTokens(
        response.data.access_token,
        response.data.refresh_token,
      );
      const user = await fetchUser();
      return {token: response.data, user};
    },
    onSuccess: ({token, user}) => {
      finishAuth(token.access_token, user);
    },
    onError: (error: unknown) => {
      log.warn('googleAuth failed', classifyError(error));
      setError(toUserMessage(error, i18n.t));
    },
    onMutate: () => {
      setLoading(true);
      setError(null);
    },
    onSettled: () => {
      setLoading(false);
    },
  });
};

export const useLogoutMutation = () => {
  return useMutation({
    mutationFn: async () => {
      await storage.clearTokens();
      useAuthStore.getState().clearAuth();
    },
  });
};
