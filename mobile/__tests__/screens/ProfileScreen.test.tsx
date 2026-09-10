import {render, waitFor, userEvent} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import {NativeModules, Platform} from 'react-native';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import {__cameraEaseTo as cameraEaseToMock} from '@maplibre/maplibre-react-native';
import Geolocation from '@react-native-community/geolocation';
import client from '../../src/services/api/client';
import i18n from '../../src/i18n';
import ProfileScreen from '../../src/app/screens/ProfileScreen';
import {useAuthStore} from '../../src/features/auth/authStore';
import {mockUser} from '../fixtures/user';
import * as permissionsModule from '../../src/services/permissions/permissions';

jest.mock('@react-native-community/geolocation', () => ({
  __esModule: true,
  default: {
    getCurrentPosition: jest.fn(),
    setRNConfiguration: jest.fn(),
  },
}));

const exitAppMock = NativeModules.LanguagePreferences?.exitApp as
  jest.Mock | undefined;

let mockApi: MockAdapter;

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

beforeEach(() => {
  queryClient.clear();
  mockApi = new MockAdapter(client);
  useAuthStore.setState({
    user: mockUser,
    isAuthenticated: true,
    hydrated: true,
    step: 'authenticated',
    token: 'token-1',
    phone: mockUser.phone,
    loading: false,
    error: null,
  });
});

afterEach(async () => {
  queryClient.clear();
  mockApi.restore();
  jest.restoreAllMocks();
  exitAppMock?.mockClear();
  await i18n.changeLanguage('en');
});

describe('ProfileScreen', () => {
  it('loads the profile and renders all fields', async () => {
    const profile = {
      ...mockUser,
      full_name: 'Test User',
      address: 'Kuwait City',
    };
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: profile});

    const {getByDisplayValue, getByText} = await render(<ProfileScreen />, {
      wrapper,
    });

    await waitFor(() => expect(getByText('profile')).toBeTruthy());
    expect(getByDisplayValue('Test User')).toBeTruthy();
    expect(getByDisplayValue('Kuwait City')).toBeTruthy();
    expect(getByDisplayValue('+965501234567')).toBeTruthy();
    expect(getByDisplayValue('user@example.com')).toBeTruthy();
  });

  it('shows the Connect Google section when no Google account is linked', async () => {
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});

    const {getByText} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(getByText('connectGoogle')).toBeTruthy());
    expect(getByText('connectGoogleDesc')).toBeTruthy();
  });

  it('hides the Connect Google section when a Google account is linked', async () => {
    const profile = {...mockUser, has_google: true};
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: profile});

    const {queryByText} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(queryByText('connectGoogleLabel')).toBeNull());
  });

  it('saves the profile on Save press', async () => {
    const user = userEvent.setup();
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});
    mockApi
      .onPatch('/users/me/profile')
      .reply(200, {success: true, data: mockUser});

    const {getByText, getByDisplayValue} = await render(<ProfileScreen />, {
      wrapper,
    });

    await waitFor(() => expect(getByDisplayValue('Test User')).toBeTruthy());
    await user.type(getByDisplayValue('Test User'), ' Renamed');
    await user.press(getByText('save'));

    await waitFor(() => {
      const patch = mockApi.history.patch[0];
      expect(patch).toBeDefined();
      expect(patch.data).toContain('"full_name"');
    });
  });

  it('asks for confirmation before closing the app after saving a new language', async () => {
    jest.replaceProperty(Platform, 'OS', 'android');
    const user = userEvent.setup();
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});
    mockApi.onPatch('/users/me/profile').reply(200, {
      success: true,
      data: {...mockUser, preferred_language: 'ar'},
    });

    const {getByText, getByTestId} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(getByText('language')).toBeTruthy());
    await user.press(getByText('English'));
    await user.press(getByText('العربية'));
    await waitFor(() => expect(i18n.language).toBe('ar'));
    expect(mockApi.history.patch.length).toBe(0);

    await user.press(getByText('save'));

    await waitFor(() => {
      const patch = mockApi.history.patch[0];
      expect(patch).toBeDefined();
      expect(patch.data).toContain('"preferred_language":"ar"');
    });
    await waitFor(() =>
      expect(getByText('languageRestartMessage')).toBeTruthy(),
    );

    await user.press(getByTestId('language-restart-confirm'));

    await waitFor(() => expect(exitAppMock).toHaveBeenCalled());
  });

  it('stays open when the language restart is cancelled', async () => {
    jest.replaceProperty(Platform, 'OS', 'android');
    const user = userEvent.setup();
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});
    mockApi.onPatch('/users/me/profile').reply(200, {
      success: true,
      data: {...mockUser, preferred_language: 'ar'},
    });

    const {getByText, getByTestId} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(getByText('language')).toBeTruthy());
    await user.press(getByText('English'));
    await user.press(getByText('العربية'));
    await user.press(getByText('save'));

    await waitFor(() =>
      expect(getByText('languageRestartMessage')).toBeTruthy(),
    );
    await user.press(getByTestId('language-restart-cancel'));

    await waitFor(() => expect(getByText('saved')).toBeTruthy());
    expect(exitAppMock).not.toHaveBeenCalled();
  });

  it('logs out from the logout dialog', async () => {
    const user = userEvent.setup();
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});

    const {getByText, getByTestId} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(getByText('logout')).toBeTruthy());
    await user.press(getByText('logout'));
    await waitFor(() => expect(getByText('logoutConfirm')).toBeTruthy());
    await user.press(getByTestId('logout-confirm'));
    await waitFor(() =>
      expect(useAuthStore.getState().isAuthenticated).toBe(false),
    );
  });

  it('locks the page scroll while the map is being touched', async () => {
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});

    const {getByTestId, findByTestId} = await render(<ProfileScreen />, {
      wrapper,
    });
    const scrollView = await findByTestId('scroll-view');
    const touchArea = getByTestId('map-touch-area');
    expect(scrollView.props.scrollEnabled).toBe(true);

    touchArea.props.onTouchStart();
    await waitFor(() =>
      expect(getByTestId('scroll-view').props.scrollEnabled).toBe(false),
    );

    touchArea.props.onTouchEnd();
    await waitFor(() =>
      expect(getByTestId('scroll-view').props.scrollEnabled).toBe(true),
    );
  });

  it('centers the map on the current location when locate is requested', async () => {
    const user = userEvent.setup();
    const getCurrentPosition = Geolocation.getCurrentPosition as jest.Mock;
    getCurrentPosition.mockImplementation((success: (pos: unknown) => void) => {
      success({coords: {latitude: 29.1, longitude: 47.8}});
      return Promise.resolve();
    });
    cameraEaseToMock.mockClear();
    jest
      .spyOn(permissionsModule, 'checkLocationPermission')
      .mockResolvedValue('granted');
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});

    const {getByTestId} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(getByTestId('locate-me')).toBeTruthy());
    await user.press(getByTestId('locate-me'));

    await waitFor(() =>
      expect(cameraEaseToMock).toHaveBeenCalledWith({center: [47.8, 29.1]}),
    );
  });

  it('falls back to the network provider when GPS times out', async () => {
    const user = userEvent.setup();
    const getCurrentPosition = Geolocation.getCurrentPosition as jest.Mock;
    getCurrentPosition.mockClear();
    getCurrentPosition
      .mockImplementationOnce(
        (_success: (pos: unknown) => void, error: (e: unknown) => void) => {
          error({code: 3, message: 'Location request timed out'});
          return Promise.resolve();
        },
      )
      .mockImplementationOnce((success: (pos: unknown) => void) => {
        success({coords: {latitude: 29.05, longitude: 47.79}});
        return Promise.resolve();
      });
    cameraEaseToMock.mockClear();
    jest
      .spyOn(permissionsModule, 'checkLocationPermission')
      .mockResolvedValue('granted');
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});

    const {getByTestId} = await render(<ProfileScreen />, {wrapper});

    await waitFor(() => expect(getByTestId('locate-me')).toBeTruthy());
    await user.press(getByTestId('locate-me'));

    await waitFor(() =>
      expect(cameraEaseToMock).toHaveBeenCalledWith({center: [47.79, 29.05]}),
    );
    expect(getCurrentPosition).toHaveBeenCalledTimes(2);
  });
});
