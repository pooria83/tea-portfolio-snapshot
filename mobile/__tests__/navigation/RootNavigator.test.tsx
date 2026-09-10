import {render, waitFor, act} from '@testing-library/react-native';
import * as React from 'react';
import MockAdapter from 'axios-mock-adapter';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import {useAuthStore} from '../../src/features/auth/authStore';
import {storage} from '../../src/services/storage';
import client from '../../src/services/api/client';
import i18n from '../../src/i18n';
import {mockUser} from '../fixtures/user';
import RootNavigator from '../../src/app/navigation/RootNavigator';

jest.mock('../../src/app/navigation/AuthStack', () => jest.fn(() => null));
jest.mock('../../src/app/navigation/MainTabs', () => jest.fn(() => null));
jest.mock('../../src/services/storage', () => ({
  storage: {
    getTokens: jest.fn(() => Promise.resolve(null)),
    setTokens: jest.fn(() => Promise.resolve()),
    clearTokens: jest.fn(() => Promise.resolve()),
  },
}));

const mockAuthStack = () =>
  jest.requireMock('../../src/app/navigation/AuthStack') as jest.Mock;
const mockMainTabs = () =>
  jest.requireMock('../../src/app/navigation/MainTabs') as jest.Mock;

const wrapper = ({children}: {children: React.ReactNode}) => (
  <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
);

const resetStore = () =>
  useAuthStore.setState({
    token: null,
    user: null,
    isAuthenticated: false,
    hydrated: false,
    step: 'phone',
    phone: null,
    loading: false,
    error: null,
  });

let mockApi: MockAdapter;

beforeEach(async () => {
  resetStore();
  jest.clearAllMocks();
  mockApi = new MockAdapter(client);
  jest
    .mocked(storage.getTokens)
    .mockImplementation(() => Promise.resolve(null));
  await i18n.changeLanguage('en');
});

afterEach(() => {
  mockApi.restore();
});

describe('RootNavigator hydration gate', () => {
  it('shows a loading indicator while hydration is pending', async () => {
    jest.mocked(storage.getTokens).mockReturnValue(new Promise(() => {}));

    const r = await render(<RootNavigator />, {wrapper});

    expect(r.getByTestId('root-loading')).toBeTruthy();
    expect(mockAuthStack()).not.toHaveBeenCalled();
    expect(mockMainTabs()).not.toHaveBeenCalled();
  });

  it('renders the auth stack after hydrating without a session', async () => {
    const r = await render(<RootNavigator />, {wrapper});

    await waitFor(() => expect(mockAuthStack()).toHaveBeenCalledTimes(1));
    expect(r.queryByTestId('root-loading')).toBeNull();
    expect(mockMainTabs()).not.toHaveBeenCalled();
  });

  it('renders the main tabs when authenticated', async () => {
    mockApi.onGet('/users/me').reply(200, {success: true, data: mockUser});
    jest
      .mocked(storage.getTokens)
      .mockResolvedValue({accessToken: 'at-1', refreshToken: 'rt-1'});

    const r = await render(<RootNavigator />, {wrapper});

    await waitFor(() => expect(mockMainTabs()).toHaveBeenCalledTimes(1));
    expect(r.queryByTestId('root-loading')).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('degrades to the auth stack after retries when hydration fails', async () => {
    jest.useFakeTimers();
    mockApi.onGet('/users/me').reply(500, {detail: 'boom'});
    jest
      .mocked(storage.getTokens)
      .mockResolvedValue({accessToken: 'at-1', refreshToken: 'rt-1'});

    const r = await render(<RootNavigator />, {wrapper});

    for (let attempt = 0; attempt < 3; attempt += 1) {
      await act(async () => {
        jest.advanceTimersByTime(5000);
      });
    }

    await waitFor(() => expect(mockAuthStack()).toHaveBeenCalledTimes(1));
    expect(r.queryByTestId('root-loading')).toBeNull();
    const store = useAuthStore.getState();
    expect(store.isAuthenticated).toBe(false);
    expect(store.hydrated).toBe(true);
    expect(store.token).toBe('at-1');
  });

  it('clears stale tokens and hydrates without a session on 401', async () => {
    mockApi.onGet('/users/me').reply(401, {});
    jest
      .mocked(storage.getTokens)
      .mockResolvedValue({accessToken: 'at-1', refreshToken: 'rt-1'});

    const r = await render(<RootNavigator />, {wrapper});

    await waitFor(() => expect(mockAuthStack()).toHaveBeenCalledTimes(1));
    expect(r.queryByTestId('root-loading')).toBeNull();
    expect(storage.clearTokens).toHaveBeenCalledTimes(1);
    const store = useAuthStore.getState();
    expect(store.isAuthenticated).toBe(false);
    expect(store.hydrated).toBe(true);
    expect(store.token).toBeNull();
  });
});

describe('RootNavigator profile language', () => {
  const setAuthenticated = (preferredLanguage: string) => {
    useAuthStore.setState({
      token: 'at-1',
      user: {...mockUser, preferred_language: preferredLanguage},
      isAuthenticated: true,
      hydrated: true,
      step: 'authenticated',
      phone: mockUser.phone,
      loading: false,
      error: null,
    });
  };

  it('applies the profile preferred language on startup', async () => {
    await render(<RootNavigator />, {wrapper});
    await waitFor(() => expect(mockAuthStack()).toHaveBeenCalledTimes(1));

    setAuthenticated('ar');

    await waitFor(() => expect(i18n.language).toBe('ar'));
    expect(mockMainTabs()).toHaveBeenCalledTimes(1);
  });

  it('does not change the language when the profile language is already active', async () => {
    await render(<RootNavigator />, {wrapper});
    await waitFor(() => expect(mockAuthStack()).toHaveBeenCalledTimes(1));

    setAuthenticated('en');

    await waitFor(() => expect(mockMainTabs()).toHaveBeenCalledTimes(1));
    expect(i18n.language).toBe('en');
  });
});
