import * as Keychain from 'react-native-keychain';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {storage} from '../../src/services/storage';

const getStored = async (service: string): Promise<string | null> => {
  const result = await Keychain.getGenericPassword({service});
  return result ? result.password : null;
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('storage', () => {
  it('returns both tokens when both are stored in the keychain', async () => {
    await storage.setTokens('at-1', 'rt-1');

    await expect(storage.getTokens()).resolves.toEqual({
      accessToken: 'at-1',
      refreshToken: 'rt-1',
    });
  });

  it('returns null when only one token is stored', async () => {
    await storage.setTokens('at-1', 'rt-1');
    jest.mocked(Keychain.getGenericPassword).mockResolvedValueOnce(false);

    await expect(storage.getTokens()).resolves.toBeNull();
  });

  it('returns null when reading fails', async () => {
    jest
      .mocked(Keychain.getGenericPassword)
      .mockRejectedValueOnce(new Error('keychain read failed'));

    await expect(storage.getTokens()).resolves.toBeNull();
  });

  it('stores tokens in the keychain, not in AsyncStorage', async () => {
    await storage.setTokens('at-1', 'rt-1');

    expect(await getStored('auth_access_token')).toBe('at-1');
    expect(await getStored('auth_refresh_token')).toBe('rt-1');
    expect(AsyncStorage.setItem).not.toHaveBeenCalled();
  });

  it('clears both keychain secrets and the stored user on clearTokens', async () => {
    await storage.setTokens('at-1', 'rt-1');
    await AsyncStorage.setItem('auth_user', '{"id":"u1"}');

    await storage.clearTokens();

    expect(await getStored('auth_access_token')).toBeNull();
    expect(await getStored('auth_refresh_token')).toBeNull();
    expect(await AsyncStorage.getItem('auth_user')).toBeNull();
  });

  it('does not throw when clearing an empty keychain', async () => {
    await expect(storage.clearTokens()).resolves.toBeUndefined();
  });
});
