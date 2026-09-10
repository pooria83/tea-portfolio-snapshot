const mockAsyncStorageStore = new Map<string, string>();
jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    setItem: jest.fn(async (key: string, value: string) => {
      mockAsyncStorageStore.set(key, value);
    }),
    getItem: jest.fn(
      async (key: string) => mockAsyncStorageStore.get(key) ?? null,
    ),
    removeItem: jest.fn(async (key: string) => {
      mockAsyncStorageStore.delete(key);
    }),
    clear: jest.fn(async () => {
      mockAsyncStorageStore.clear();
    }),
  },
}));

const mockNativeModules = require('react-native').NativeModules as Record<
  string,
  unknown
>;
mockNativeModules.LanguagePreferences = {
  setLanguage: jest.fn(),
  exitApp: jest.fn(),
};

jest.mock('react-native-permissions', () => {
  const RESULTS = {
    GRANTED: 'granted',
    DENIED: 'denied',
    BLOCKED: 'blocked',
    LIMITED: 'limited',
    UNAVAILABLE: 'unavailable',
  };
  const PERMISSIONS = {
    IOS: {
      LOCATION_WHEN_IN_USE: 'ios.permission.LOCATION_WHEN_IN_USE',
      MICROPHONE: 'ios.permission.MICROPHONE',
    },
    ANDROID: {
      ACCESS_FINE_LOCATION: 'android.permission.ACCESS_FINE_LOCATION',
      RECORD_AUDIO: 'android.permission.RECORD_AUDIO',
      READ_SMS: 'android.permission.READ_SMS',
    },
  };
  return {
    PERMISSIONS,
    RESULTS,
    check: jest.fn(async () => RESULTS.GRANTED),
    request: jest.fn(async () => RESULTS.GRANTED),
    checkNotifications: jest.fn(async () => ({
      status: RESULTS.GRANTED,
      settings: {},
    })),
    requestNotifications: jest.fn(async () => ({
      status: RESULTS.GRANTED,
      settings: {},
    })),
    openSettings: jest.fn(),
  };
});

const mockKeychainStore = new Map<string, string>();
jest.mock('react-native-keychain', () => ({
  __esModule: true,
  setGenericPassword: jest.fn(
    async (
      _username: string,
      password: string,
      options?: {service?: string},
    ) => {
      mockKeychainStore.set(options?.service ?? 'default', password);
    },
  ),
  getGenericPassword: jest.fn(async (options?: {service?: string}) => {
    const password = mockKeychainStore.get(options?.service ?? 'default');
    return password != null ? {username: 'token', password} : false;
  }),
  resetGenericPassword: jest.fn(async (options?: {service?: string}) => {
    mockKeychainStore.delete(options?.service ?? 'default');
  }),
}));

jest.mock('react-native-safe-area-context', () => {
  const React = require('react');
  const {View} = require('react-native');
  const SafeAreaView = (props: Record<string, unknown>) =>
    React.createElement(View, props);
  const SafeAreaProvider = (props: {children?: React.ReactNode}) =>
    React.createElement(View, null, props.children);
  const useSafeAreaInsets = () => ({top: 0, bottom: 0, left: 0, right: 0});
  return {
    SafeAreaView,
    SafeAreaProvider,
    SafeAreaInsetsContext: React.createContext({
      top: 0,
      bottom: 0,
      left: 0,
      right: 0,
    }),
    SafeAreaFrameContext: React.createContext({
      width: 0,
      height: 0,
      x: 0,
      y: 0,
    }),
    useSafeAreaInsets,
    initialWindowMetrics: {
      frame: {width: 320, height: 640, x: 0, y: 0},
      insets: {top: 0, bottom: 0, left: 0, right: 0},
    },
  };
});

jest.mock('react-native-vector-icons/MaterialIcons', () => {
  const React = require('react');
  const {Text} = require('react-native');
  const Mock = (props: {name?: string; color?: string; size?: number}) =>
    React.createElement(Text, null, props.name ?? '');
  return {__esModule: true, default: Mock};
});

jest.mock('@react-native-google-signin/google-signin', () => {
  const GoogleSignin = {
    configure: jest.fn(),
    signIn: jest.fn(),
    signInSilently: jest.fn(),
    signOut: jest.fn(),
    getCurrentUser: jest.fn(() => null),
    getTokens: jest.fn(() => Promise.resolve({idToken: '', accessToken: ''})),
    hasPlayServices: jest.fn(() => Promise.resolve(true)),
  };
  return {
    GoogleSignin,
    isSuccessResponse: (response: {type?: string}) =>
      response.type === 'success',
    statusCodes: {
      SIGN_IN_CANCELLED: 'SIGN_IN_CANCELLED',
      IN_PROGRESS: 'IN_PROGRESS',
      SIGN_IN_REQUIRED: 'SIGN_IN_REQUIRED',
      PLAY_SERVICES_NOT_AVAILABLE: 'PLAY_SERVICES_NOT_AVAILABLE',
    },
  };
});

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {language: 'en'},
  }),
  initReactI18next: {type: '3rdParty', init: jest.fn()},
}));

jest.mock('@maplibre/maplibre-react-native', () => {
  const React = require('react');
  const {View} = require('react-native');
  const easeTo = jest.fn();
  const zoomTo = jest.fn();
  const cameraImpl = jest.fn((props: Record<string, unknown>) => {
    const {ref, ...rest} = props;
    React.useImperativeHandle(ref, () => ({
      easeTo,
      zoomTo,
      jumpTo: jest.fn(),
      fitBounds: jest.fn(),
      setStop: jest.fn(),
    }));
    return React.createElement(View, rest);
  });
  return {
    __esModule: true,
    __cameraEaseTo: easeTo,
    __cameraZoomTo: zoomTo,
    __cameraMock: cameraImpl,
    Map: jest.fn((props: Record<string, unknown>) =>
      React.createElement(View, props, props.children),
    ),
    Camera: React.memo(cameraImpl),
    Marker: jest.fn((props: Record<string, unknown>) =>
      React.createElement(View, props, props.children),
    ),
  };
});

jest.mock('react-native-image-crop-picker', () => ({
  openPicker: jest.fn(),
}));

jest.mock('@sentry/react-native', () => ({
  init: jest.fn(),
  isInitialized: jest.fn(() => false),
  setUser: jest.fn(),
  setTag: jest.fn(),
  addBreadcrumb: jest.fn(),
  captureMessage: jest.fn(),
  captureException: jest.fn(),
}));

jest.mock('react-native-bootsplash', () => ({
  __esModule: true,
  default: {
    hide: jest.fn(),
    show: jest.fn(),
    isVisible: jest.fn(),
  },
}));

jest.mock('@d11/react-native-fast-image', () => {
  const React = require('react');
  const {Image} = require('react-native');
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement(Image, props),
    resizeMode: {
      contain: 'contain',
      cover: 'cover',
      stretch: 'stretch',
      center: 'center',
    },
    priority: {low: 'low', normal: 'normal', high: 'high'},
    cacheControl: {
      immutable: 'immutable',
      web: 'web',
      cacheOnly: 'cacheOnly',
    },
    transition: {fade: 'fade', none: 'none'},
  };
});
