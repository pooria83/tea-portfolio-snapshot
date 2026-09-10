import {render, waitFor, userEvent} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import {
  GoogleSignin,
  statusCodes,
} from '@react-native-google-signin/google-signin';
import client from '../../src/services/api/client';
import {useAuthStore} from '../../src/features/auth/authStore';
import PhoneScreen from '../../src/app/screens/auth/PhoneScreen';
import type {PhoneScreenProps} from '../../src/types/navigation';
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

const navigate = jest.fn();
const goBack = jest.fn();
const screenProps = {
  navigation: {navigate, goBack},
  route: {key: 'Phone-1', name: 'Phone'},
} as unknown as PhoneScreenProps;

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

let mockApi: MockAdapter;

beforeEach(() => {
  resetStore();
  queryClient.clear();
  navigate.mockClear();
  goBack.mockClear();
  jest.clearAllMocks();
  mockApi = new MockAdapter(client);
});

afterEach(() => {
  queryClient.clear();
  mockApi.restore();
});

describe('PhoneScreen', () => {
  it('renders the login header, phone field and google button', async () => {
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    r.getByText('login');
    r.getByText('enterPhone');
    r.getByText('sendOtp');
    r.getByText('googleLogin');
  });

  it('requires a local number before sending the otp', async () => {
    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getByText('sendOtp'));

    await waitFor(() => expect(useAuthStore.getState().error).toBe('required'));
    expect(navigate).not.toHaveBeenCalled();
  });

  it('stores the full phone (dial code + number) and navigates to Otp', async () => {
    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.type(
      r.getAllByPlaceholderText('phonePlaceholder')[0],
      '501234567',
    );
    await userEventApi.press(r.getByText('sendOtp'));

    await waitFor(() =>
      expect(useAuthStore.getState().phone).toBe('+965501234567'),
    );
    expect(navigate).toHaveBeenCalledWith('Otp');
  });

  it('filters the country picker by search text', async () => {
    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getAllByText('+965')[0]);
    const searchInput = r.getByPlaceholderText('searchCountry');
    await userEventApi.type(searchInput, 'Saudi');

    await waitFor(() => {
      expect(r.getByText('Saudi Arabia')).toBeTruthy();
      expect(r.queryByText('Kuwait')).toBeNull();
    });
  });

  it('opens the google sign-in sheet and authenticates on id_token', async () => {
    mockApi
      .onPost('/auth/google')
      .reply(200, tokenResponse)
      .onGet('/users/me')
      .reply(200, {success: true, data: user});

    const mockGoogleSignin = GoogleSignin as jest.Mocked<typeof GoogleSignin>;
    mockGoogleSignin.signIn.mockResolvedValueOnce({
      type: 'success',
      data: {
        user: {
          id: 'g-1',
          name: 'G User',
          email: 'g@example.com',
          photo: null,
          familyName: null,
          givenName: 'G',
        },
        scopes: ['email', 'profile'],
        idToken: 'google-id-token',
        serverAuthCode: null,
      },
    });

    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getByText('googleLogin'));

    await waitFor(() =>
      expect(useAuthStore.getState().isAuthenticated).toBe(true),
    );
    const store = useAuthStore.getState();
    expect(store.step).toBe('authenticated');
    expect(store.token).toBe('access-1');
    expect(mockGoogleSignin.hasPlayServices).toHaveBeenCalled();

    const body = JSON.parse(
      mockApi.history.post.find((h) => h.url === '/auth/google')?.data ?? '{}',
    );
    expect(body).toEqual({
      id_token: 'google-id-token',
      client_type: 'android',
    });
  });

  it('ignores a cancelled google sign-in', async () => {
    const mockGoogleSignin = GoogleSignin as jest.Mocked<typeof GoogleSignin>;
    mockGoogleSignin.signIn.mockRejectedValueOnce({
      code: statusCodes.SIGN_IN_CANCELLED,
      message: 'cancel',
    });

    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getByText('googleLogin'));

    await waitFor(() => expect(useAuthStore.getState().error).toBeNull());
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('ignores an in-progress google sign-in', async () => {
    const mockGoogleSignin = GoogleSignin as jest.Mocked<typeof GoogleSignin>;
    mockGoogleSignin.signIn.mockRejectedValueOnce({
      code: statusCodes.IN_PROGRESS,
      message: 'in progress',
    });

    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getByText('googleLogin'));

    await waitFor(() => expect(useAuthStore.getState().error).toBeNull());
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('surfaces a fallback message for other google failures', async () => {
    const mockGoogleSignin = GoogleSignin as jest.Mocked<typeof GoogleSignin>;
    mockGoogleSignin.signIn.mockRejectedValueOnce({
      code: 'PLAY_SERVICES_NOT_AVAILABLE',
      message: 'play services missing',
    });

    const userEventApi = userEvent.setup();
    const r = await render(<PhoneScreen {...screenProps} />, {wrapper});
    await userEventApi.press(r.getByText('googleLogin'));

    await waitFor(() =>
      expect(useAuthStore.getState().error).toBe('play services missing'),
    );
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
