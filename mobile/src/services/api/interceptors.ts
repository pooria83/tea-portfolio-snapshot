import axios, {type AxiosError, type InternalAxiosRequestConfig} from 'axios';
import client from './client';
import {storage} from '../storage';
import {useAuthStore} from '../../features/auth/authStore';
import {classifyError} from './errors';
import {log} from '../logging/logger';

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const startedAt = new WeakMap<InternalAxiosRequestConfig, number>();

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else if (token) {
      promise.resolve(token);
    }
  });
  failedQueue = [];
};

client.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    startedAt.set(config, Date.now());
    const tokens = await storage.getTokens();
    if (tokens?.accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${tokens.accessToken}`;
    }
    log.debug('api request', {
      method: config.method,
      url: config.url,
      authenticated: tokens?.accessToken != null,
    });
    return config;
  },
  (error) => {
    log.error('api request failed', {error: classifyError(error)});
    return Promise.reject(error);
  },
);

client.interceptors.response.use(
  (response) => {
    const start = startedAt.get(response.config);
    log.debug('api response', {
      method: response.config.method,
      url: response.config.url,
      status: response.status,
      durationMs: start != null ? Date.now() - start : undefined,
    });
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({resolve, reject});
      }).then((token) => {
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${token}`;
        }
        return client(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const tokens = await storage.getTokens();
      if (!tokens?.refreshToken) {
        throw new Error('No refresh token');
      }

      const response = await axios.post(
        `${client.defaults.baseURL}/auth/refresh`,
        {refresh_token: tokens.refreshToken},
      );

      const refreshData = response.data as
        {access_token?: string; refresh_token?: string} | undefined;
      if (!refreshData?.access_token || !refreshData.refresh_token) {
        throw new Error('Invalid refresh response');
      }
      const {access_token, refresh_token} = refreshData;
      await storage.setTokens(access_token, refresh_token);
      processQueue(null, access_token);

      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
      }
      return client(originalRequest);
    } catch (refreshError) {
      log.error('token refresh failed', {
        error: classifyError(refreshError),
      });
      processQueue(refreshError, null);
      await storage.clearTokens();
      useAuthStore.getState().clearAuth();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default client;
