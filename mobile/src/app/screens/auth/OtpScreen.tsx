import * as React from 'react';
import {useState, useRef} from 'react';
import {
  View,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  TextInput as RNTextInput,
  ScrollView,
} from 'react-native';
import {Text, Button, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {useAuthStore} from '../../../features/auth/authStore';
import {useVerifyOtpMutation} from '../../../features/auth/useAuthMutations';
import {
  extractOtp,
  startSmsOtpListening,
  subscribeSmsOtp,
} from '../../../services/sms/smsOtp';
import {requestSmsReadPermission} from '../../../services/permissions/permissions';
import type {OtpScreenProps} from '../../../types/navigation';

const OTP_LENGTH = 6;

export default function OtpScreen({navigation}: OtpScreenProps) {
  const {t} = useTranslation('auth');
  const theme = useTheme();
  const phone = useAuthStore((s) => s.phone);
  const error = useAuthStore((s) => s.error);
  const setError = useAuthStore((s) => s.setError);
  const setPhone = useAuthStore((s) => s.setPhone);
  const setStep = useAuthStore((s) => s.setStep);
  const [otp, setOtp] = useState('');
  const inputRef = useRef<RNTextInput>(null);

  const verifyOtpMutation = useVerifyOtpMutation();

  const applyOtp = React.useCallback(
    (digits: string) => {
      setOtp(digits);
      setError(null);
      if (digits.length === OTP_LENGTH && !verifyOtpMutation.isPending) {
        verifyOtpMutation.mutate(digits);
      }
    },
    [setError, verifyOtpMutation],
  );

  const applyOtpRef = useRef(applyOtp);
  React.useEffect(() => {
    applyOtpRef.current = applyOtp;
  }, [applyOtp]);

  const handleVerify = () => {
    if (otp.length < OTP_LENGTH) {
      setError(t('required'));
      return;
    }
    setError(null);
    verifyOtpMutation.mutate(otp);
  };

  const handleBack = () => {
    setError(null);
    setPhone('');
    setStep('phone');
    navigation.goBack();
  };

  React.useEffect(() => {
    if (Platform.OS !== 'android') {
      return;
    }
    const unsubscribe = subscribeSmsOtp((event) => {
      if (!event.cancelled && event.message) {
        const digits = extractOtp(event.message);
        if (digits) {
          applyOtpRef.current(digits);
        }
      }
    });
    void requestSmsReadPermission().then((status) => {
      if (status === 'granted') {
        startSmsOtpListening();
      }
    });
    return () => {
      unsubscribe();
    };
  }, []);

  const renderDigit = (index: number) => {
    const char = otp[index] ?? '';
    const filled = char !== '';
    return (
      <View
        key={index}
        style={[
          styles.digitBox,
          {
            borderColor: filled ? theme.colors.primary : theme.colors.outline,
            backgroundColor: filled
              ? theme.colors.primaryContainer
              : theme.colors.surface,
          },
        ]}>
        <Text variant="headlineMedium" style={styles.digitText}>
          {char}
        </Text>
      </View>
    );
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
              {t('otp')}
            </Text>
            <Text
              variant="bodyLarge"
              style={[styles.subtitle, {color: theme.colors.onSurfaceVariant}]}>
              {t('enterOtp')}
            </Text>
            {phone ? (
              <Text variant="titleSmall" style={styles.phoneDisplay}>
                {phone}
              </Text>
            ) : null}
          </View>

          {error ? (
            <Text
              style={[styles.errorText, {color: theme.colors.error}]}
              role="alert">
              {error}
            </Text>
          ) : null}

          <View
            style={styles.digitsRow}
            onTouchStart={() => inputRef.current?.focus()}>
            {Array.from({length: OTP_LENGTH}, (_, index) => renderDigit(index))}
          </View>

          <RNTextInput
            ref={inputRef}
            value={otp}
            onChangeText={(val) => {
              applyOtp(val.replace(/\D/g, '').slice(0, OTP_LENGTH));
            }}
            keyboardType="number-pad"
            autoFocus
            maxLength={OTP_LENGTH}
            style={styles.hiddenInput}
            accessibilityLabel={t('otp')}
          />

          <View style={styles.actionsRow}>
            <Button
              mode="outlined"
              onPress={handleBack}
              disabled={verifyOtpMutation.isPending}
              style={styles.flexButton}>
              {t('back')}
            </Button>
            <Button
              mode="contained"
              onPress={handleVerify}
              loading={verifyOtpMutation.isPending}
              disabled={verifyOtpMutation.isPending || otp.length < OTP_LENGTH}
              style={styles.flexButton}>
              {t('verifyOtp')}
            </Button>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: {flex: 1},
  safe: {flex: 1},
  scroll: {flexGrow: 1, justifyContent: 'center', padding: 24},
  header: {marginBottom: 32},
  title: {textAlign: 'center', marginBottom: 8},
  subtitle: {textAlign: 'center'},
  phoneDisplay: {textAlign: 'center', marginTop: 8},
  errorText: {textAlign: 'center', marginBottom: 16},
  digitsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 32,
  },
  digitBox: {
    width: 44,
    height: 56,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  digitText: {fontWeight: '600'},
  hiddenInput: {
    position: 'absolute',
    opacity: 0,
    height: 1,
    width: 1,
  },
  actionsRow: {flexDirection: 'row', gap: 12},
  flexButton: {flex: 1},
});
