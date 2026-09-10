import * as React from 'react';
import {ErrorBoundary, type ErrorBoundaryProps} from 'react-error-boundary';
import {StyleSheet, View} from 'react-native';
import {Button, Text, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {log} from '../../services/logging/logger';

function CrashFallback({resetErrorBoundary}: {resetErrorBoundary: () => void}) {
  const {t} = useTranslation('error');
  const theme = useTheme();

  return (
    <View style={[styles.center, {backgroundColor: theme.colors.background}]}>
      <Text variant="headlineSmall" style={styles.title}>
        {t('crashTitle')}
      </Text>
      <Text variant="bodyMedium" style={styles.message}>
        {t('crashMessage')}
      </Text>
      <Button mode="contained" onPress={resetErrorBoundary}>
        {t('crashReload')}
      </Button>
    </View>
  );
}

export default function AppErrorBoundary({
  children,
}: {
  children: React.ReactNode;
}) {
  const onError: ErrorBoundaryProps['onError'] = (error, info) => {
    log.error('unhandled render error', {
      error,
      componentStack: info.componentStack,
    });
  };

  return (
    <ErrorBoundary FallbackComponent={CrashFallback} onError={onError}>
      {children}
    </ErrorBoundary>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  title: {
    textAlign: 'center',
  },
  message: {
    textAlign: 'center',
  },
});
