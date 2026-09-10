import {renderHook, waitFor, act} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import client from '../../../src/services/api/client';
import {useAuthStore} from '../../../src/features/auth/authStore';
import {
  useSendOtpMutation,
  useVerifyOtpMutation,
  useGoogleAuthMutation,
} from '../../../src/features/auth/useAuthMutations';
import {mockUser} from '../../fixtures/user';

const user = mockUser;

const tokenResponse = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
};

let mockApi: MockAdapter;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {retry: false, gcTime: 0},
    mutations: {retry: false, gcTime: 0},
  },
});

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

const resetStore = () =>
  useAuthStore.setState({
    token: null,
    user: null,
    isAuthenticated: false,
    hydrated: true,
    step: 'phone',
    phone: null,
    loading: false,
    error: null,
  });

beforeEach(() => {
  resetStore();
  queryClient.clear();
  mockApi = new MockAdapter(client);
});

afterEach(() => {
  queryClient.clear();
  mockApi.restore();
  jest.clearAllMocks();
});

describe('useSendOtpMutation', () => {
  it('posts the phone and moves to the otp step', async () => {
    mockApi.onPost('/auth/send-otp').reply(200, {success: true, data: null});
    const {result} = await renderHook(() => useSendOtpMutation(), {wrapper});

    await act(async () => {
      result.current.mutate('+965501234567');
    });

    await waitFor(() => expect(useAuthStore.getState().step).toBe('otp'));
    expect(useAuthStore.getState().phone).toBe('+965501234567');
    expect(mockApi.history.post.length).toBe(1);
    expect(JSON.parse(mockApi.history.post[0]?.data ?? '{}')).toEqual({
      phone: '+965501234567',
    });
  });

  it('stores a localized error when sendOtp fails', async () => {
    mockApi.onPost('/auth/send-otp').reply(400, {
      success: false,
      error: {message: 'Invalid phone'},
    });
    const {result} = await renderHook(() => useSendOtpMutation(), {wrapper});

    await act(async () => {
      result.current.mutate('bad');
    });

    expect(useAuthStore.getState().error).toBe(
      'An unexpected error occurred. Please try again.',
    );
    expect(useAuthStore.getState().step).toBe('phone');
  });

  it('uses the backend translation_key when present', async () => {
    mockApi.onPost('/auth/send-otp').reply(400, {
      success: false,
      error: {translation_key: 'invalid_phone', message: 'Invalid phone'},
    });
    const {result} = await renderHook(() => useSendOtpMutation(), {wrapper});

    await act(async () => {
      result.current.mutate('bad');
    });

    expect(useAuthStore.getState().error).toBe('Invalid phone number format');
  });
});

describe('useVerifyOtpMutation', () => {
  beforeEach(() => {
    useAuthStore.getState().setPhone('+965501234567');
    useAuthStore.getState().setStep('otp');
  });

  it('verifies the otp, fetches the user and authenticates', async () => {
    mockApi
      .onPost('/auth/verify-otp')
      .reply(200, tokenResponse)
      .onGet('/users/me')
      .reply(200, {success: true, data: user});

    const {result} = await renderHook(() => useVerifyOtpMutation(), {wrapper});

    await act(async () => {
      result.current.mutate('123456');
    });

    await waitFor(() =>
      expect(useAuthStore.getState().isAuthenticated).toBe(true),
    );
    const store = useAuthStore.getState();
    expect(store.step).toBe('authenticated');
    expect(store.token).toBe('access-1');
    expect(store.user?.id).toBe('user-1');
    const verifyBody = JSON.parse(mockApi.history.post[0]?.data ?? '{}');
    expect(verifyBody).toEqual({phone: '+965501234567', code: '123456'});
  });

  it('surfaces a localized error but stays on the otp step', async () => {
    mockApi.onPost('/auth/verify-otp').reply(401, {
      success: false,
      error: {message: 'Invalid or expired code'},
    });

    const {result} = await renderHook(() => useVerifyOtpMutation(), {wrapper});

    await act(async () => {
      result.current.mutate('000000');
    });

    expect(useAuthStore.getState().error).toBe('Not authenticated');
    expect(useAuthStore.getState().step).toBe('otp');
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});

describe('useGoogleAuthMutation', () => {
  it('sends the android id_token and authenticates', async () => {
    mockApi
      .onPost('/auth/google')
      .reply(200, tokenResponse)
      .onGet('/users/me')
      .reply(200, {success: true, data: user});

    const {result} = await renderHook(() => useGoogleAuthMutation(), {wrapper});

    await act(async () => {
      result.current.mutate('google-id-token');
    });

    await waitFor(() =>
      expect(useAuthStore.getState().isAuthenticated).toBe(true),
    );
    const store = useAuthStore.getState();
    expect(store.step).toBe('authenticated');
    expect(store.token).toBe('access-1');

    const body = JSON.parse(
      mockApi.history.post.find((h) => h.url === '/auth/google')?.data ?? '{}',
    );
    expect(body).toEqual({
      id_token: 'google-id-token',
      client_type: 'android',
    });
  });
});
