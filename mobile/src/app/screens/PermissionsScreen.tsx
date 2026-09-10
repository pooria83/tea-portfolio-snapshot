import * as React from 'react';
import {ScrollView, StyleSheet, View} from 'react-native';
import {Button, List, Text, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {SafeAreaView} from 'react-native-safe-area-context';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import {openAppSettings} from '../../services/permissions/permissions';
import {storage} from '../../services/storage';
import {useErrorToastStore} from '../../features/errors/errorToastStore';
import {
  useLocationPermission,
  useMicrophonePermission,
  useNotificationsPermission,
} from '../../hooks/usePermissions';
import type {PermissionsScreenProps} from '../../types/navigation';
import type {PermissionStatus} from '../../services/permissions/permissions';

interface PermissionRowProps {
  icon: string;
  title: string;
  description: string;
  status: PermissionStatus | null;
  busy: boolean;
  onRequest: () => void;
}

function PermissionRow({
  icon,
  title,
  description,
  status,
  busy,
  onRequest,
}: PermissionRowProps) {
  const {t} = useTranslation('permissions');
  const theme = useTheme();

  const granted = status === 'granted';
  const blocked = status === 'blocked';

  return (
    <View
      style={[
        styles.row,
        {
          backgroundColor: theme.colors.surface,
          borderColor: theme.colors.outlineVariant,
        },
      ]}>
      <List.Icon icon={icon} color={theme.colors.primary} />
      <View style={styles.rowBody}>
        <Text variant="titleMedium">{title}</Text>
        <Text
          variant="bodySmall"
          style={[styles.rowDesc, {color: theme.colors.onSurfaceVariant}]}>
          {description}
        </Text>
        {status ? (
          <View
            style={[
              styles.statusChip,
              {
                backgroundColor: granted
                  ? theme.colors.primaryContainer
                  : theme.colors.surfaceVariant,
              },
            ]}>
            <MaterialIcons
              name={granted ? 'check-circle' : 'remove-circle-outline'}
              size={14}
              color={
                granted ? theme.colors.tertiary : theme.colors.onSurfaceVariant
              }
            />
            <Text
              variant="labelSmall"
              style={{
                color: granted
                  ? theme.colors.onPrimaryContainer
                  : theme.colors.onSurfaceVariant,
              }}>
              {t(status)}
            </Text>
          </View>
        ) : null}
      </View>
      {!granted ? (
        <Button mode="outlined" loading={busy} onPress={onRequest}>
          {blocked ? t('openSettings') : t('allow')}
        </Button>
      ) : null}
    </View>
  );
}

const notificationsStatus = (
  permissions: ReturnType<typeof useNotificationsPermission>['status'] | null,
): PermissionStatus | null => {
  if (permissions == null) {
    return null;
  }
  if (permissions.granted) {
    return 'granted';
  }
  return permissions.blocked ? 'blocked' : 'denied';
};

export default function PermissionsScreen({
  navigation,
}: Pick<PermissionsScreenProps, 'navigation'>) {
  const {t} = useTranslation('permissions');
  const theme = useTheme();
  const showError = useErrorToastStore((state) => state.showError);

  const notifications = useNotificationsPermission();
  const location = useLocationPermission();
  const microphone = useMicrophonePermission();

  const requestNotifications = async (): Promise<void> => {
    try {
      await notifications.request();
    } catch (error) {
      showError(error);
    } finally {
      void storage.setNotificationsOnboarded();
    }
  };

  React.useEffect(() => {
    // Onboarding gate: the first visit with notifications ungranted pops the
    // system dialog proactively; afterwards the screen is a plain settings list.
    void (async () => {
      if (await storage.getNotificationsOnboarded()) {
        return;
      }
      const current = notifications.status;
      if (current == null || current.granted) {
        return;
      }
      await requestNotifications();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestSafe = (request: () => Promise<void>): void => {
    void (async () => {
      try {
        await request();
      } catch (error) {
        showError(error);
      }
    })();
  };

  return (
    <SafeAreaView
      edges={['top', 'bottom']}
      style={[styles.container, {backgroundColor: theme.colors.background}]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text variant="headlineMedium" style={styles.title}>
          {t('title')}
        </Text>
        <Text
          variant="bodyMedium"
          style={[styles.subtitle, {color: theme.colors.onSurfaceVariant}]}>
          {t('subtitle')}
        </Text>

        <PermissionRow
          icon="bell-outline"
          title={t('notificationsTitle')}
          description={t('notificationsDesc')}
          status={notificationsStatus(notifications.status)}
          busy={notifications.requesting}
          onRequest={() =>
            requestSafe(async () => {
              const next = await notifications.request();
              if (next.blocked) {
                openAppSettings();
              }
              await storage.setNotificationsOnboarded();
            })
          }
        />

        <PermissionRow
          icon="map-marker-outline"
          title={t('locationTitle')}
          description={t('locationDesc')}
          status={location.status}
          busy={location.requesting}
          onRequest={() =>
            requestSafe(async () => {
              const next = await location.request();
              if (next === 'blocked') {
                openAppSettings();
              }
            })
          }
        />

        <PermissionRow
          icon="microphone-outline"
          title={t('microphoneTitle')}
          description={t('microphoneDesc')}
          status={microphone.status}
          busy={microphone.requesting}
          onRequest={() =>
            requestSafe(async () => {
              const next = await microphone.request();
              if (next === 'blocked') {
                openAppSettings();
              }
            })
          }
        />
      </ScrollView>
      <View
        style={[
          styles.footer,
          {
            backgroundColor: theme.colors.surface,
            borderColor: theme.colors.outlineVariant,
          },
        ]}>
        <Button
          mode="contained"
          onPress={() => navigation.goBack()}
          style={styles.footerButton}>
          {t('done', {ns: 'common'})}
        </Button>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 24,
    gap: 12,
  },
  title: {
    marginBottom: 4,
  },
  subtitle: {
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  rowBody: {
    flex: 1,
    gap: 2,
  },
  rowDesc: {
    opacity: 0.8,
  },
  statusChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  footer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
  },
  footerButton: {
    width: '100%',
  },
});
