import {DeviceEventEmitter, NativeModules, Platform} from 'react-native';

import {
  extractOtp,
  startSmsOtpListening,
  subscribeSmsOtp,
} from '../../src/services/sms/smsOtp';

describe('smsOtp', () => {
  describe('extractOtp', () => {
    it('extracts a 6-digit code from a full SMS', () => {
      expect(
        extractOtp('Your TEA verification code is 482913. Do not share it.'),
      ).toBe('482913');
    });

    it('picks the first 6-digit group', () => {
      expect(extractOtp('Order #123456 — code 987654')).toBe('987654');
    });

    it('returns null when no 6-digit code is present', () => {
      expect(extractOtp('Welcome to TEA!')).toBeNull();
      expect(extractOtp('Code: 12345')).toBeNull();
    });
  });

  describe('subscribeSmsOtp', () => {
    const originalPlatform = Platform.OS;

    afterEach(() => {
      Platform.OS = originalPlatform;
    });

    it('is a no-op off Android', () => {
      Platform.OS = 'ios';
      const unsubscribe = subscribeSmsOtp(() => {});
      expect(unsubscribe).toBeDefined();
    });

    it('emits events on Android and unsubscribes cleanly', () => {
      Platform.OS = 'android';
      const handler = jest.fn();
      const unsubscribe = subscribeSmsOtp(handler);
      DeviceEventEmitter.emit('SmsOtpEvent', {message: 'Code 123456'});
      expect(handler).toHaveBeenCalledWith({message: 'Code 123456'});
      unsubscribe();
      DeviceEventEmitter.emit('SmsOtpEvent', {message: 'Code 654321'});
      expect(handler).toHaveBeenCalledTimes(1);
    });
  });

  describe('startSmsOtpListening', () => {
    const originalPlatform = Platform.OS;
    const originalSmsOtpModule = NativeModules.SmsOtp;

    afterEach(() => {
      Platform.OS = originalPlatform;
      NativeModules.SmsOtp = originalSmsOtpModule;
    });

    it('calls the native module on Android', () => {
      Platform.OS = 'android';
      const startListening = jest.fn();
      NativeModules.SmsOtp = {startListening};
      startSmsOtpListening();
      expect(startListening).toHaveBeenCalled();
    });

    it('does nothing off Android', () => {
      Platform.OS = 'ios';
      const startListening = jest.fn();
      NativeModules.SmsOtp = {startListening};
      startSmsOtpListening();
      expect(startListening).not.toHaveBeenCalled();
    });
  });
});
