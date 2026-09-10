/**
 * @format
 */
import './src/i18n';
import './src/services/api/interceptors';
import './src/services/logging/globalHandlers';

import * as React from 'react';
import {useColorScheme} from 'react-native';
import {SafeAreaProvider} from 'react-native-safe-area-context';
import {PaperProvider} from 'react-native-paper';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {GoogleSignin} from '@react-native-google-signin/google-signin';
import Config from 'react-native-config';
import {lightTheme, darkTheme} from './src/theme';
import RootNavigator from './src/app/navigation/RootNavigator';
import AppErrorBoundary from './src/components/feedback/AppErrorBoundary';
import ErrorToast from './src/components/feedback/ErrorToast';
import SuccessToast from './src/components/feedback/SuccessToast';
import {useAuthStore} from './src/features/auth/authStore';
import {installGlobalHandlers} from './src/services/logging/globalHandlers';
import {setLogContext} from './src/services/logging/logger';
import {initSentry, setSentryUser} from './src/services/logging/sentry';

installGlobalHandlers();
initSentry();

GoogleSignin.configure({webClientId: Config.GOOGLE_CLIENT_ID});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});

useAuthStore.subscribe((state) => {
  setLogContext({userId: state.user?.id ?? null});
  setSentryUser(state.user);
});

function App() {
  const isDarkMode = useColorScheme() === 'dark';
  const theme = isDarkMode ? darkTheme : lightTheme;

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <PaperProvider theme={theme}>
          <AppErrorBoundary>
            <RootNavigator />
          </AppErrorBoundary>
          <ErrorToast />
          <SuccessToast />
        </PaperProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

export default App;
