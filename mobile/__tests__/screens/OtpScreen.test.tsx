import {render, waitFor, userEvent} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import client from '../../src/services/api/client';
import {useAuthStore} from '../../src/features/auth/authStore';
import OtpScreen from '../../src/app/screens/auth/OtpScreen';
import type {OtpScreenProps} from '../../src/types/navigation';
import {mockUser} from '../fixtures/user';

const user = mockUser;

const tokenResponse = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {retry: false, gcTime: 0},
    mutations: {retry: false, gcTime: 0},
  },
});

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider client={queryClient}>
    <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
  </QueryClientProvider>
);

const goBack = jest.fn();
const screenProps = {
  navigation: {navigate: jest.fn(), goBack},
  route: {key: 'Otp-1', name: 'Otp'},
} as unknown as OtpScreenProps;

const resetStore = () =>
  useAuthStore.setState({
    token: null,
    user: null,
    isAuthenticated: false,
    hydrated: true,
    step: 'otp',
    phone: '+965501234567',
    loading: false,
    error: null,
  });

let mockApi: MockAdapter;

beforeEach(() => {
  resetStore();
  queryClient.clear();
  goBack.mockClear();
  jest.clearAllMocks();
  mockApi = new MockAdapter(client);
});

afterEach(() => {
  queryClient.clear();
  mockApi.restore();
});

describe('OtpScreen', () => {
  it('renders the title, phone, six digit boxes and actions', async () => {
    const r = await render(<OtpScreen {...screenProps} />, {wrapper});
    r.getByText('otp');
    r.getByText('enterOtp');
    r.getByText('+965501234567');
    r.getByText('back');
    r.getByText('verifyOtp');
    r.getByLabelText('otp');
  });

  it('does not verify until six digits are entered', async () => {
    const userEventApi = userEvent.setup();
    const r = await render(<OtpScreen {...screenProps} />, {wrapper});
    await userEventApi.type(r.getByLabelText('otp'), '123');
    await userEventApi.press(r.getByText('verifyOtp'));
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockApi.history.post.length).toBe(0);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('auto-verifies on the sixth digit and authenticates', async () => {
    mockApi
      .onPost('/auth/verify-otp')
      .reply(200, tokenResponse)
      .onGet('/users/me')
      .reply(200, {success: true, data: user});

    const userEventApi = userEvent.setup();
    const r = await render(<OtpScreen {...screenProps} />, {wrapper});
    await userEventApi.type(r.getByLabelText('otp'), '123456');

    await waitFor(() =>
      expect(useAuthStore.getState().isAuthenticated).toBe(true),
    );
    const store = useAuthStore.getState();
    expect(store.step).toBe('authenticated');
    expect(store.token).toBe('access-1');

    const body = JSON.parse(
      mockApi.history.post.find((h) => h.url === '/auth/verify-otp')?.data ??
        '{}',
    );
    expect(body).toEqual({phone: '+965501234567', code: '123456'});
  });

  it('shows the error and stays on the otp step when verification fails', async () => {
    mockApi.onPost('/auth/verify-otp').reply(401, {
      success: false,
      error: {message: 'Invalid or expired code'},
    });

    const userEventApi = userEvent.setup();
    const r = await render(<OtpScreen {...screenProps} />, {wrapper});
    await userEventApi.type(r.getByLabelText('otp'), '000000');

    await waitFor(() => expect(r.getByText('Not authenticated')).toBeTruthy());
    expect(useAuthStore.getState().step).toBe('otp');
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('goes back and resets the auth state to the phone step', async () => {
    const userEventApi = userEvent.setup();
    const r = await render(<OtpScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getByText('back'));

    const store = useAuthStore.getState();
    expect(store.phone).toBe('');
    expect(store.step).toBe('phone');
    expect(goBack).toHaveBeenCalled();
  });
});
