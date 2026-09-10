import * as React from 'react';
import {useState, useMemo, useCallback} from 'react';
import {
  View,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Modal,
  FlatList,
  Pressable,
  TouchableOpacity,
  useWindowDimensions,
} from 'react-native';
import {
  Text,
  TextInput,
  Button,
  useTheme,
  Searchbar,
  Divider,
} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {
  GoogleSignin,
  statusCodes,
} from '@react-native-google-signin/google-signin';
import Icon from 'react-native-vector-icons/MaterialIcons';
import {
  countries,
  defaultCountry,
  type Country,
} from '../../../constants/countries';
import {useAuthStore} from '../../../features/auth/authStore';
import {useGoogleAuthMutation} from '../../../features/auth/useAuthMutations';
import {toUserMessage} from '../../../services/api/errors';
import {log} from '../../../services/logging/logger';
import type {PhoneScreenProps} from '../../../types/navigation';

export default function PhoneScreen({navigation}: PhoneScreenProps) {
  const {t} = useTranslation('auth');
  const theme = useTheme();
  const {height} = useWindowDimensions();
  const error = useAuthStore((s) => s.error);
  const setError = useAuthStore((s) => s.setError);
  const setPhone = useAuthStore((s) => s.setPhone);
  const [selectedCountry, setSelectedCountry] =
    useState<Country>(defaultCountry);
  const [localNumber, setLocalNumber] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [search, setSearch] = useState('');

  const googleMutation = useGoogleAuthMutation();

  const filteredCountries = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return countries;
    return countries.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.nameAr.includes(q) ||
        c.nameFa.includes(q) ||
        c.dialCode.includes(q) ||
        c.code.toLowerCase().includes(q),
    );
  }, [search]);

  const handleSubmit = useCallback(() => {
    const fullPhone = `${selectedCountry.dialCode}${localNumber.replace(
      /\D/g,
      '',
    )}`;
    if (fullPhone === selectedCountry.dialCode) {
      setError(t('required'));
      return;
    }
    setError(null);
    setPhone(fullPhone);
    navigation.navigate('Otp');
  }, [selectedCountry, localNumber, setError, setPhone, navigation, t]);

  const handleGoogle = useCallback(async () => {
    try {
      setError(null);
      await GoogleSignin.hasPlayServices({
        showPlayServicesUpdateDialog: true,
      });
      const info = await GoogleSignin.signIn();
      if (info.type !== 'success' || !info.data.idToken) {
        return;
      }
      googleMutation.mutate(info.data.idToken);
    } catch (googleError: unknown) {
      if (
        googleError &&
        typeof googleError === 'object' &&
        'code' in googleError &&
        (googleError.code === statusCodes.SIGN_IN_CANCELLED ||
          googleError.code === statusCodes.IN_PROGRESS)
      ) {
        return;
      }
      log.warn('google sign-in failed', {error: googleError});
      setError(toUserMessage(googleError, t));
    }
  }, [googleMutation, setError, t]);

  const pickCountry = (country: Country) => {
    setSelectedCountry(country);
    setPickerOpen(false);
    setError(null);
  };

  return (
    <View style={[styles.safe, {backgroundColor: theme.colors.background}]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text variant="headlineLarge" style={styles.title}>
              {t('login')}
            </Text>
            <Text
              variant="bodyLarge"
              style={[styles.subtitle, {color: theme.colors.onSurfaceVariant}]}>
              {t('enterPhone')}
            </Text>
          </View>

          {error ? (
            <Text
              style={[styles.errorText, {color: theme.colors.error}]}
              role="alert">
              {error}
            </Text>
          ) : null}

          <Text variant="labelLarge" style={styles.fieldLabel}>
            {t('phone')}
          </Text>

          <View style={styles.phoneRow}>
            <TouchableOpacity
              onPress={() => setPickerOpen(true)}
              style={styles.dialCode}>
              <Text variant="titleMedium">{selectedCountry.flag}</Text>
              <Text variant="titleSmall">{selectedCountry.dialCode}</Text>
              <Icon
                name="arrow-drop-down"
                size={20}
                color={theme.colors.onSurfaceVariant}
              />
            </TouchableOpacity>
            <TextInput
              value={localNumber}
              onChangeText={(val) => {
                setLocalNumber(val.replace(/\D/g, ''));
                setError(null);
              }}
              placeholder={t('phonePlaceholder')}
              keyboardType="phone-pad"
              mode="outlined"
              outlineStyle={styles.phoneInputOutline}
              style={styles.phoneInput}
            />
          </View>

          <Button
            mode="contained"
            onPress={handleSubmit}
            style={styles.button}
            contentStyle={styles.buttonContent}>
            {t('sendOtp')}
          </Button>

          <View style={styles.orRow}>
            <Divider style={styles.orLine} />
            <Text
              variant="bodyMedium"
              style={[styles.orText, {color: theme.colors.onSurfaceVariant}]}>
              {t('or')}
            </Text>
            <Divider style={styles.orLine} />
          </View>

          <Button
            mode="outlined"
            onPress={handleGoogle}
            loading={googleMutation.isPending}
            disabled={googleMutation.isPending}
            icon="google"
            style={styles.button}
            contentStyle={styles.buttonContent}>
            {googleMutation.isPending ? t('googleSigningIn') : t('googleLogin')}
          </Button>
        </ScrollView>

        <Modal
          visible={pickerOpen}
          transparent
          animationType="slide"
          onRequestClose={() => setPickerOpen(false)}>
          <Pressable
            style={styles.modalOverlay}
            onPress={() => setPickerOpen(false)}>
            <View
              style={[
                styles.modalSheet,
                {
                  backgroundColor: theme.colors.surface,
                  maxHeight: height * 0.7,
                },
              ]}>
              <Searchbar
                placeholder={t('searchCountry')}
                value={search}
                onChangeText={setSearch}
                style={styles.search}
              />
              <FlatList
                data={filteredCountries}
                keyExtractor={(item) => item.code}
                keyboardShouldPersistTaps="handled"
                renderItem={({item}) => (
                  <TouchableOpacity onPress={() => pickCountry(item)}>
                    <View style={styles.countryRow}>
                      <Text variant="titleMedium">{item.flag}</Text>
                      <Text variant="bodyLarge" style={styles.countryName}>
                        {item.name}
                      </Text>
                      <Text
                        variant="bodyMedium"
                        style={{color: theme.colors.onSurfaceVariant}}>
                        {item.dialCode}
                      </Text>
                    </View>
                    <Divider />
                  </TouchableOpacity>
                )}
                ListEmptyComponent={
                  <Text
                    variant="bodyMedium"
                    style={[
                      styles.empty,
                      {color: theme.colors.onSurfaceVariant},
                    ]}>
                    {t('noCountryFound')}
                  </Text>
                }
              />
            </View>
          </Pressable>
        </Modal>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: {flex: 1},
  safe: {flex: 1},
  scroll: {flexGrow: 1, padding: 24},
  header: {marginBottom: 24},
  title: {textAlign: 'center', marginBottom: 8},
  subtitle: {textAlign: 'center'},
  fieldLabel: {marginBottom: 8},
  phoneRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 8,
    paddingLeft: 8,
    marginBottom: 16,
  },
  dialCode: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 8,
  },
  phoneInput: {
    flex: 1,
    height: 52,
    borderTopLeftRadius: 0,
    borderBottomLeftRadius: 0,
    backgroundColor: 'transparent',
  },
  phoneInputOutline: {borderWidth: 0},
  button: {marginTop: 8},
  buttonContent: {paddingVertical: 8},
  orRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginVertical: 16,
  },
  orLine: {flex: 1, height: 1},
  orText: {},
  errorText: {textAlign: 'center', marginBottom: 12},
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingBottom: 24,
  },
  search: {margin: 12},
  countryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  countryName: {flex: 1},
  empty: {textAlign: 'center', padding: 24},
});
