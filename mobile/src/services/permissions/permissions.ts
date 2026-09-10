import {Platform} from 'react-native';
import {
  PERMISSIONS,
  RESULTS,
  check,
  checkNotifications,
  openSettings,
  request,
  requestNotifications,
} from 'react-native-permissions';

import {log} from '../logging/logger';

export type PermissionStatus = 'granted' | 'denied' | 'blocked';

export interface NotificationsPermission {
  granted: boolean;
  blocked: boolean;
}

const toStatus = (result: string): PermissionStatus => {
  switch (result) {
    case RESULTS.GRANTED:
    case RESULTS.LIMITED:
      return 'granted';
    case RESULTS.BLOCKED:
      return 'blocked';
    default:
      return 'denied';
  }
};

const locationPermission =
  Platform.OS === 'ios'
    ? PERMISSIONS.IOS.LOCATION_WHEN_IN_USE
    : PERMISSIONS.ANDROID.ACCESS_FINE_LOCATION;

const micPermission =
  Platform.OS === 'ios'
    ? PERMISSIONS.IOS.MICROPHONE
    : PERMISSIONS.ANDROID.RECORD_AUDIO;

export const checkLocationPermission = async (): Promise<PermissionStatus> => {
  try {
    return toStatus(await check(locationPermission));
  } catch (error) {
    log.warn('checkLocationPermission failed', error);
    return 'denied';
  }
};

/**
 * Requests location permission at the point of use (the profile map). The
 * operating system decides whether a dialog can be shown again after a denial;
 * once no longer possible, the result is 'blocked' and the caller should
 * offer to open the system settings instead.
 */
export const requestLocationPermission =
  async (): Promise<PermissionStatus> => {
    try {
      return toStatus(await request(locationPermission));
    } catch (error) {
      log.warn('requestLocationPermission failed', error);
      return 'blocked';
    }
  };

export const requestMicrophonePermission =
  async (): Promise<PermissionStatus> => {
    try {
      return toStatus(await request(micPermission));
    } catch (error) {
      log.warn('requestMicrophonePermission failed', error);
      return 'blocked';
    }
  };

export const checkMicrophonePermission =
  async (): Promise<PermissionStatus> => {
    try {
      return toStatus(await check(micPermission));
    } catch (error) {
      log.warn('checkMicrophonePermission failed', error);
      return 'denied';
    }
  };

/** Requests READ_SMS (Android only). Never granted on iOS — returns 'denied'. */
export const requestSmsReadPermission = async (): Promise<PermissionStatus> => {
  if (Platform.OS !== 'android') {
    return 'denied';
  }
  try {
    return toStatus(await request(PERMISSIONS.ANDROID.READ_SMS));
  } catch (error) {
    log.warn('requestSmsReadPermission failed', error);
    return 'blocked';
  }
};

export const getNotificationsPermission =
  async (): Promise<NotificationsPermission> => {
    try {
      const {status} = await checkNotifications();
      return {
        granted: status === RESULTS.GRANTED,
        blocked: status === RESULTS.BLOCKED,
      };
    } catch (error) {
      log.warn('getNotificationsPermission failed', error);
      return {granted: false, blocked: false};
    }
  };

export const requestNotificationsPermission =
  async (): Promise<NotificationsPermission> => {
    try {
      const {status} = await requestNotifications(['alert', 'sound', 'badge']);
      return {
        granted: status === RESULTS.GRANTED,
        blocked: status === RESULTS.BLOCKED,
      };
    } catch (error) {
      log.warn('requestNotificationsPermission failed', error);
      return {granted: false, blocked: false};
    }
  };

export const openAppSettings = (): void => {
  void openSettings();
};
