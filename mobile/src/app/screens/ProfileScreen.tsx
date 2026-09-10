import * as React from 'react';
import {useEffect, useState} from 'react';
import {
  KeyboardAvoidingView,
  NativeModules,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import {
  ActivityIndicator,
  Button,
  Dialog,
  Divider,
  Menu,
  Portal,
  Snackbar,
  Text,
  TextInput,
  useTheme,
} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {useIsFocused} from '@react-navigation/native';
import Geolocation from '@react-native-community/geolocation';
import {
  GoogleSignin,
  isSuccessResponse,
} from '@react-native-google-signin/google-signin';
import i18n, {setAppLanguage} from '../../i18n';
import type {SupportedLanguage} from '../../i18n';
import type {ProfileScreenProps} from '../../types/navigation';
import LocationPicker from '../../components/map/LocationPicker';
import type {LatLng} from '../../components/map/LocationPicker';
import PhotoUploader from '../../components/upload/PhotoUploader';
import {openAppSettings} from '../../services/permissions/permissions';
import {log} from '../../services/logging/logger';
import {useLocationPermission} from '../../hooks/usePermissions';
import {useLogoutMutation} from '../../features/auth/useAuthMutations';
import {useErrorToastStore} from '../../features/errors/errorToastStore';
import {
  useGetProfileQuery,
  useLinkGoogleMutation,
  useUpdateProfileMutation,
} from '../../features/profile/useProfileMutations';

const LANGUAGES = [
  {code: 'ar', label: 'العربية'},
  {code: 'en', label: 'English'},
  {code: 'fa', label: 'فارسی'},
] as const;

function useFocusedFallback(): boolean {
  try {
    return useIsFocused();
  } catch {
    return true;
  }
}

export default function ProfileScreen({navigation}: ProfileScreenProps) {
  const {t} = useTranslation('profile');
  const theme = useTheme();

  const {data: profile, isLoading, refetch} = useGetProfileQuery();
  const updateProfile = useUpdateProfileMutation();
  const linkGoogle = useLinkGoogleMutation();
  const logout = useLogoutMutation();
  const showError = useErrorToastStore((state) => state.showError);
  const locationPermission = useLocationPermission();
  const isFocused = useFocusedFallback();

  // The lib's internal permission gate hangs on the new React Native
  // architecture; we gate the permission ourselves before locating.
  useEffect(() => {
    Geolocation.setRNConfiguration({skipPermissionRequests: true});
  }, []);

  const handleRequestLocation = async () => {
    try {
      const next = await locationPermission.request();
      if (next === 'blocked') {
        openAppSettings();
      }
    } catch (error) {
      showError(error);
    }
  };

  const handleLocateMe = async () => {
    log.debug('locate me requested');
    try {
      if (locationPermission.status !== 'granted') {
        const next = await locationPermission.request();
        if (next === 'blocked') {
          log.warn('locate me permission blocked');
          openAppSettings();
          setSnackbar(t('locationUnavailable'));
          return;
        }
        if (next !== 'granted') {
          log.debug('locate me permission denied');
          return;
        }
      }
      const getPosition = (enableHighAccuracy: boolean) =>
        new Promise<{lat: number; lng: number}>((resolve, reject) => {
          Geolocation.getCurrentPosition(
            (pos) => {
              resolve({lat: pos.coords.latitude, lng: pos.coords.longitude});
            },
            (error: unknown) => {
              reject(error);
            },
            {enableHighAccuracy, timeout: 10000, maximumAge: 10000},
          );
        });
      let position: {lat: number; lng: number};
      try {
        position = await getPosition(true);
        log.debug('locate me gps success', {
          lat: position.lat,
          lng: position.lng,
        });
      } catch (error) {
        // Raw GPS needs a satellite fix and can stall indoors; fall back to
        // the network (Wi-Fi/cell) provider, which Google Maps also uses.
        const code = (error as {code?: number}).code;
        if (code !== 2 && code !== 3) {
          throw error;
        }
        position = await getPosition(false);
        log.debug('locate me network success', {
          lat: position.lat,
          lng: position.lng,
        });
      }
      setLocation(position);
    } catch (error) {
      log.warn('locate me failed', {code: (error as {code?: number}).code});
      setSnackbar(
        (error as {code?: number}).code === 2 ||
          (error as {code?: number}).code === 3
          ? t('locationServicesOff')
          : t('locationUnavailable'),
      );
    }
  };

  const [fullName, setFullName] = useState<string | null>(null);
  const [address, setAddress] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [location, setLocation] = useState<LatLng | null>(null);
  const [language, setLanguage] = useState<SupportedLanguage | null>(null);
  const [languageMenuVisible, setLanguageMenuVisible] = useState(false);
  const [languageRestartVisible, setLanguageRestartVisible] = useState(false);
  const [logoutDialogVisible, setLogoutDialogVisible] = useState(false);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [mapTouched, setMapTouched] = useState(false);

  const resolvedFullName = fullName ?? profile?.full_name ?? '';
  const resolvedAddress = address ?? profile?.address ?? '';
  const resolvedAvatarUrl = avatarUrl ?? profile?.avatar_url ?? null;
  const resolvedLocation =
    location ??
    (profile != null &&
    profile.location_lat != null &&
    profile.location_lng != null
      ? {lat: profile.location_lat, lng: profile.location_lng}
      : null);
  const resolvedLanguage = language ?? profile?.preferred_language ?? 'en';

  const handleSelectLanguage = (code: SupportedLanguage) => {
    setLanguageMenuVisible(false);
    setLanguage(code);
    if (code !== i18n.language) {
      void setAppLanguage(code);
    }
  };

  const handleSave = async () => {
    const update: {
      full_name?: string;
      avatar_url?: string;
      address?: string;
      location_lat?: number;
      location_lng?: number;
      preferred_language?: string;
    } = {};
    if (resolvedFullName) {
      update.full_name = resolvedFullName;
    }
    if (resolvedAvatarUrl) {
      update.avatar_url = resolvedAvatarUrl;
    }
    if (resolvedAddress) {
      update.address = resolvedAddress;
    }
    if (resolvedLocation) {
      update.location_lat = resolvedLocation.lat;
      update.location_lng = resolvedLocation.lng;
    }
    if (resolvedLanguage !== profile?.preferred_language) {
      update.preferred_language = resolvedLanguage;
    }
    try {
      await updateProfile.mutateAsync(update);
      if (
        Platform.OS === 'android' &&
        resolvedLanguage !== profile?.preferred_language
      ) {
        // The RTL layout direction applies on the next launch; ask the user
        // before closing the app so they reopen it to see the new layout.
        setLanguageRestartVisible(true);
        return;
      }
      setSnackbar(t('saved'));
    } catch (error) {
      showError(error);
    }
  };

  const handleCloseForLanguage = () => {
    setLanguageRestartVisible(false);
    const languagePrefs = NativeModules.LanguagePreferences as
      {exitApp: () => void} | undefined;
    if (languagePrefs != null) {
      languagePrefs.exitApp();
    }
  };

  const handleConnectGoogle = async () => {
    try {
      await GoogleSignin.hasPlayServices();
      const response = await GoogleSignin.signIn();
      if (!isSuccessResponse(response)) {
        return;
      }
      const idToken = response.data.idToken;
      if (!idToken) {
        throw new Error('Google Sign-In did not return an ID token');
      }
      await linkGoogle.mutateAsync(idToken);
      setSnackbar(t('googleLinked'));
      void refetch();
    } catch (error) {
      showError(error);
    }
  };

  const saving = updateProfile.isPending || linkGoogle.isPending;
  const showGoogleSection = profile != null && !profile.has_google;

  if (isLoading || !profile) {
    return (
      <View style={[styles.center, {backgroundColor: theme.colors.background}]}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
      </View>
    );
  }

  return (
    <View style={{backgroundColor: theme.colors.background, flex: 1}}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{flex: 1}}>
        <ScrollView
          testID="scroll-view"
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          scrollEnabled={!mapTouched}>
          <Text variant="headlineMedium" style={styles.title}>
            {t('profile', {ns: 'nav'})}
          </Text>

          <PhotoUploader
            currentUrl={resolvedAvatarUrl}
            circular
            onUploadComplete={(url) => setAvatarUrl(url)}
          />

          <TextInput
            label={t('fullName')}
            placeholder={t('fullNamePlaceholder')}
            value={resolvedFullName}
            onChangeText={setFullName}
            mode="outlined"
            left={<TextInput.Icon icon="person-outline" />}
            style={styles.field}
          />

          <TextInput
            label={t('phone')}
            value={profile.phone ?? ''}
            editable={false}
            mode="outlined"
            left={<TextInput.Icon icon="phone" />}
            style={[styles.field, styles.readOnly]}
          />

          <TextInput
            label={t('email')}
            value={profile.email ?? ''}
            editable={false}
            mode="outlined"
            left={<TextInput.Icon icon="email" />}
            style={[styles.field, styles.readOnly]}
          />

          {showGoogleSection && (
            <View style={styles.section}>
              <Divider style={styles.divider} />
              <Text variant="titleMedium" style={styles.sectionTitle}>
                {t('connectGoogleLabel')}
              </Text>
              <Text variant="bodyMedium" style={styles.sectionDesc}>
                {t('connectGoogleDesc')}
              </Text>
              <Button
                mode="outlined"
                icon="google"
                onPress={() => {
                  void handleConnectGoogle();
                }}
                loading={linkGoogle.isPending}
                disabled={saving}>
                {t('connectGoogle')}
              </Button>
            </View>
          )}

          <TextInput
            label={t('address')}
            placeholder={t('addressPlaceholder')}
            value={resolvedAddress}
            onChangeText={(v) => setAddress(v)}
            mode="outlined"
            multiline
            numberOfLines={3}
            left={<TextInput.Icon icon="map-marker-outline" />}
            style={styles.field}
          />

          <View style={styles.section}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              {t('location')}
            </Text>
            <View
              style={[
                styles.permissionRow,
                {
                  backgroundColor: theme.colors.surfaceVariant,
                  borderColor: theme.colors.outlineVariant,
                },
              ]}>
              <View style={styles.permissionText}>
                <Text variant="bodyMedium">
                  {locationPermission.status === 'granted'
                    ? t('locationGranted', {ns: 'permissions'})
                    : locationPermission.status === 'blocked'
                      ? t('locationBlocked', {ns: 'permissions'})
                      : t('locationDesc', {ns: 'permissions'})}
                </Text>
              </View>
              {locationPermission.status !== 'granted' ? (
                <Button
                  testID="location-permission-request"
                  mode="outlined"
                  loading={locationPermission.requesting}
                  onPress={() => {
                    void handleRequestLocation();
                  }}>
                  {locationPermission.status === 'blocked'
                    ? t('openSettings', {ns: 'permissions'})
                    : t('allow', {ns: 'permissions'})}
                </Button>
              ) : null}
            </View>
            <Button
              mode="outlined"
              icon="crosshairs-gps"
              testID="test-locate"
              onPress={() => {
                void handleLocateMe();
              }}>
              Test Location
            </Button>
            <View
              testID="map-touch-area"
              onTouchStart={() => setMapTouched(true)}
              onTouchEnd={() => setMapTouched(false)}
              onTouchCancel={() => setMapTouched(false)}>
              <LocationPicker
                value={resolvedLocation}
                onChange={setLocation}
                focused={isFocused}
                onLocateRequested={() => {
                  void handleLocateMe();
                }}
              />
            </View>
          </View>

          <View style={styles.section}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              {t('language')}
            </Text>
            <Menu
              visible={languageMenuVisible}
              onDismiss={() => setLanguageMenuVisible(false)}
              anchor={
                <Button
                  mode="outlined"
                  icon="translate"
                  onPress={() => setLanguageMenuVisible(true)}>
                  {LANGUAGES.find((l) => l.code === resolvedLanguage)?.label ??
                    'English'}
                </Button>
              }>
              {LANGUAGES.map((lang) => (
                <Menu.Item
                  key={lang.code}
                  title={lang.label}
                  onPress={() => {
                    handleSelectLanguage(lang.code);
                  }}
                />
              ))}
            </Menu>
          </View>

          <View style={styles.saveRow}>
            <Button
              mode="contained"
              onPress={() => {
                void handleSave();
              }}
              loading={updateProfile.isPending}
              disabled={saving}>
              {t('save')}
            </Button>
          </View>

          <Divider style={styles.divider} />

          <View style={styles.section}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              {t('permissions')}
            </Text>
            <Button
              testID="permissions-entry"
              mode="outlined"
              icon="lock-open-outline"
              onPress={() => navigation.navigate('Permissions')}>
              {t('manage', {ns: 'permissions'})}
            </Button>
          </View>

          <Divider style={styles.divider} />
          <Button
            mode="outlined"
            icon="logout"
            textColor={theme.colors.error}
            style={styles.logout}
            onPress={() => setLogoutDialogVisible(true)}>
            {t('logout')}
          </Button>
        </ScrollView>
      </KeyboardAvoidingView>

      <Portal>
        <Dialog
          visible={languageRestartVisible}
          onDismiss={() => {
            setLanguageRestartVisible(false);
            setSnackbar(t('saved'));
          }}>
          <Dialog.Title>{t('languageRestartTitle')}</Dialog.Title>
          <Dialog.Content>
            <Text variant="bodyMedium">{t('languageRestartMessage')}</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button
              testID="language-restart-cancel"
              onPress={() => {
                setLanguageRestartVisible(false);
                setSnackbar(t('saved'));
              }}>
              {t('cancel', {ns: 'common'})}
            </Button>
            <Button
              testID="language-restart-confirm"
              textColor={theme.colors.primary}
              onPress={handleCloseForLanguage}>
              {t('languageRestartConfirm')}
            </Button>
          </Dialog.Actions>
        </Dialog>

        <Dialog
          visible={logoutDialogVisible}
          onDismiss={() => setLogoutDialogVisible(false)}>
          <Dialog.Title>{t('logoutTitle')}</Dialog.Title>
          <Dialog.Content>
            <Text variant="bodyMedium">{t('logoutConfirm')}</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setLogoutDialogVisible(false)}>
              {t('cancel', {ns: 'common'})}
            </Button>
            <Button
              testID="logout-confirm"
              textColor={theme.colors.error}
              onPress={() => {
                setLogoutDialogVisible(false);
                logout.mutate();
              }}>
              {t('logout')}
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      <Snackbar
        visible={snackbar != null}
        onDismiss={() => setSnackbar(null)}
        duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    padding: 24,
    paddingBottom: 48,
  },
  title: {
    marginBottom: 16,
  },
  field: {
    marginTop: 12,
  },
  readOnly: {
    opacity: 0.6,
  },
  section: {
    marginTop: 20,
    gap: 8,
  },
  permissionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  permissionText: {
    flex: 1,
  },
  sectionTitle: {
    marginTop: 4,
  },
  sectionDesc: {
    opacity: 0.8,
  },
  divider: {
    marginTop: 24,
    marginBottom: 8,
  },
  saveRow: {
    marginTop: 24,
  },
  logout: {
    marginTop: 8,
  },
});
