import * as Keychain from 'react-native-keychain';
import AsyncStorage from '@react-native-async-storage/async-storage';

const ACCESS_SERVICE = 'auth_access_token';
const REFRESH_SERVICE = 'auth_refresh_token';
const USER_KEY = 'auth_user';
const NOTIFICATIONS_ONBOARDED_KEY = 'permissions_notifications_onboarded';

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

const getSecret = async (service: string): Promise<string | null> => {
  try {
    const result = await Keychain.getGenericPassword({service});
    return result ? result.password : null;
  } catch {
    return null;
  }
};

const setSecret = async (service: string, value: string): Promise<void> => {
  await Keychain.setGenericPassword('token', value, {service});
};

const deleteSecret = async (service: string): Promise<void> => {
  try {
    await Keychain.resetGenericPassword({service});
  } catch {
    // nothing to clear when the secret was never stored
  }
};

export const storage = {
  async getTokens(): Promise<StoredTokens | null> {
    const [accessToken, refreshToken] = await Promise.all([
      getSecret(ACCESS_SERVICE),
      getSecret(REFRESH_SERVICE),
    ]);
    if (accessToken && refreshToken) {
      return {accessToken, refreshToken};
    }
    return null;
  },

  async setTokens(accessToken: string, refreshToken: string): Promise<void> {
    await Promise.all([
      setSecret(ACCESS_SERVICE, accessToken),
      setSecret(REFRESH_SERVICE, refreshToken),
    ]);
  },

  async clearTokens(): Promise<void> {
    await Promise.all([
      deleteSecret(ACCESS_SERVICE),
      deleteSecret(REFRESH_SERVICE),
      AsyncStorage.removeItem(USER_KEY),
    ]);
  },

  async getNotificationsOnboarded(): Promise<boolean> {
    const value = await AsyncStorage.getItem(NOTIFICATIONS_ONBOARDED_KEY);
    return value === '1';
  },

  async setNotificationsOnboarded(): Promise<void> {
    await AsyncStorage.setItem(NOTIFICATIONS_ONBOARDED_KEY, '1');
  },
};
