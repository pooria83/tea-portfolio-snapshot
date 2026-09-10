import * as React from 'react';
import {
  NavigationContainer,
  useNavigationContainerRef,
} from '@react-navigation/native';
import {ActivityIndicator, View, StyleSheet} from 'react-native';
import {useTheme} from 'react-native-paper';
import {SafeAreaView} from 'react-native-safe-area-context';
import BootSplash from 'react-native-bootsplash';
import {useAuth} from '../../hooks/useAuth';
import i18n, {isSupportedLanguage, setAppLanguage} from '../../i18n';
import {setLogContext} from '../../services/logging/logger';
import {setSentryRoute} from '../../services/logging/sentry';
import AuthStack from './AuthStack';
import AppStack from './AppStack';

export default function RootNavigator() {
  const {isAuthenticated, hydrated, user} = useAuth();
  const theme = useTheme();
  const navigationRef = useNavigationContainerRef();

  React.useEffect(() => {
    if (!hydrated) {
      return;
    }
    const preferred = user?.preferred_language;
    if (isSupportedLanguage(preferred) && preferred !== i18n.language) {
      void setAppLanguage(preferred);
    }
  }, [hydrated, user]);

  React.useEffect(() => {
    return navigationRef.addListener('state', () => {
      const state = navigationRef.getRootState();
      const current = state?.routes[state.routes.length - 1];
      setLogContext({route: current?.name ?? null});
      setSentryRoute(current?.name ?? null);
    });
  }, [navigationRef]);

  if (!hydrated) {
    return (
      <View
        style={[styles.loading, {backgroundColor: theme.colors.background}]}>
        <ActivityIndicator
          testID="root-loading"
          size="large"
          color={theme.colors.primary}
        />
      </View>
    );
  }

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safeArea}>
      {!hydrated ? (
        <View
          style={[styles.loading, {backgroundColor: theme.colors.background}]}>
          <ActivityIndicator
            testID="root-loading"
            size="large"
            color={theme.colors.primary}
          />
        </View>
      ) : (
        <NavigationContainer
          ref={navigationRef}
          onReady={() => {
            void BootSplash.hide({fade: true});
          }}>
          {isAuthenticated ? <AppStack /> : <AuthStack />}
        </NavigationContainer>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
