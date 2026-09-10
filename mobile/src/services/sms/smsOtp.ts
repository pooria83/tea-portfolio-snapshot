import {DeviceEventEmitter, NativeModules, Platform} from 'react-native';

import {log} from '../logging/logger';

export interface SmsOtpEvent {
  /** The full approved SMS text (present when the user allowed reading it). */
  message?: string;
  /** True when the user dismissed the consent dialog. */
  cancelled?: boolean;
}

const getSmsOtpNative = ():
  | {
      startListening?: () => void;
    }
  | undefined =>
  NativeModules.SmsOtp as {startListening?: () => void} | undefined;

const OTP_REGEX = /\b(\d{6})\b/g;
const CODE_HINT_REGEX = /\b(?:code|otp|كود|رمز|کد)\b[^\d]{0,12}/i;

/**
 * Extracts the 6-digit OTP from an SMS text, or null when there is none.
 * Prefers the group adjacent to a "code"-like hint (verification codes are
 * usually announced that way) and falls back to the first 6-digit group.
 */
export const extractOtp = (message: string): string | null => {
  const matches = [...message.matchAll(OTP_REGEX)];
  if (matches.length === 0) {
    return null;
  }
  const hinted = matches.find((match) =>
    CODE_HINT_REGEX.test(message.slice(0, match.index)),
  );
  return (hinted ?? matches[0])?.[1] ?? null;
};

/**
 * Subscribes to SMS User Consent events (Android only). Returns an
 * unsubscribe function. On other platforms the subscription is a no-op;
 * iOS auto-fills OTP through the keyboard instead (textContentType).
 */
export const subscribeSmsOtp = (
  handler: (event: SmsOtpEvent) => void,
): (() => void) => {
  if (Platform.OS !== 'android') {
    return () => {};
  }
  const subscription = DeviceEventEmitter.addListener('SmsOtpEvent', handler);
  return () => {
    subscription.remove();
  };
};

/**
 * Starts listening for the next OTP message. Call only after READ_SMS has
 * been granted; the system shows a consent dialog per message.
 */
export const startSmsOtpListening = (): void => {
  if (Platform.OS !== 'android') {
    return;
  }
  const native = getSmsOtpNative();
  if (native?.startListening == null) {
    return;
  }
  try {
    native.startListening();
  } catch (error) {
    log.warn('startSmsOtpListening failed', error);
  }
};
