import axios, {type AxiosResponse} from 'axios';
import MockAdapter from 'axios-mock-adapter';
import client from '../../src/services/api/client';
import {storage} from '../../src/services/storage';
import {useAuthStore} from '../../src/features/auth/authStore';
import '../../src/services/api/interceptors';

const mockTokenStore: {
  accessToken: string | null;
  refreshToken: string | null;
} = {
  accessToken: null,
  refreshToken: null,
};

jest.mock('../../src/services/storage', () => ({
  storage: {
    getTokens: jest.fn(() =>
      Promise.resolve(
        mockTokenStore.accessToken && mockTokenStore.refreshToken
          ? {
              accessToken: mockTokenStore.accessToken,
              refreshToken: mockTokenStore.refreshToken,
            }
          : null,
      ),
    ),
    setTokens: jest.fn((accessToken: string, refreshToken: string) => {
      mockTokenStore.accessToken = accessToken;
      mockTokenStore.refreshToken = refreshToken;
      return Promise.resolve();
    }),
    clearTokens: jest.fn(() => {
      mockTokenStore.accessToken = null;
      mockTokenStore.refreshToken = null;
      return Promise.resolve();
    }),
  },
}));

const newTokens = {
  data: {access_token: 'new-at', refresh_token: 'new-rt'},
} as AxiosResponse;

let mockApi: MockAdapter;
let refreshSpy: jest.SpyInstance;

const resetStore = () =>
  useAuthStore.setState({
    token: null,
    user: null,
    isAuthenticated: false,
    hydrated: true,
    step: 'phone',
    phone: null,
    loading: false,
    error: null,
  });

beforeEach(() => {
  resetStore();
  jest.clearAllMocks();
  mockTokenStore.accessToken = null;
  mockTokenStore.refreshToken = null;
  mockApi = new MockAdapter(client);
  refreshSpy = jest.spyOn(axios, 'post');
});

afterEach(() => {
  mockApi.restore();
  refreshSpy.mockRestore();
});

describe('request interceptor', () => {
  it('attaches the bearer token when tokens exist', async () => {
    mockTokenStore.accessToken = 'at-1';
    mockTokenStore.refreshToken = 'rt-1';
    mockApi.onGet('/me').reply(200, {success: true, data: null});

    await client.get('/me');

    expect(mockApi.history.get[0]?.headers?.Authorization).toBe('Bearer at-1');
  });

  it('omits the authorization header when no tokens are stored', async () => {
    mockApi.onGet('/me').reply(200, {success: true, data: null});

    await client.get('/me');

    expect(mockApi.history.get[0]?.headers?.Authorization).toBeUndefined();
  });
});

describe('response interceptor', () => {
  it('passes non-401 errors through unchanged', async () => {
    mockTokenStore.accessToken = 'at-1';
    mockTokenStore.refreshToken = 'rt-1';
    mockApi.onGet('/boom').reply(500, {detail: 'err'});

    await expect(client.get('/boom')).rejects.toMatchObject({
      response: {status: 500},
    });
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(storage.clearTokens).not.toHaveBeenCalled();
  });

  it('refreshes the token and retries the original request', async () => {
    mockTokenStore.accessToken = 'old-at';
    mockTokenStore.refreshToken = 'rt-1';
    refreshSpy.mockResolvedValue(newTokens);
    mockApi.onGet('/protected').replyOnce(401).onGet('/protected').reply(200, {
      ok: true,
    });

    const response = await client.get('/protected');

    expect(response.data).toEqual({ok: true});
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(refreshSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/auth/refresh',
      {refresh_token: 'rt-1'},
    );
    expect(storage.setTokens).toHaveBeenCalledWith('new-at', 'new-rt');
    expect(mockApi.history.get[1]?.headers?.Authorization).toBe(
      'Bearer new-at',
    );
  });

  it('queues concurrent 401s and performs a single refresh', async () => {
    mockTokenStore.accessToken = 'old-at';
    mockTokenStore.refreshToken = 'rt-1';
    refreshSpy.mockResolvedValue(newTokens);
    mockApi
      .onGet('/protected')
      .replyOnce(401)
      .onGet('/protected')
      .replyOnce(401)
      .onGet('/protected')
      .reply(200, {ok: true});

    const [first, second] = await Promise.all([
      client.get('/protected'),
      client.get('/protected'),
    ]);

    expect(first.data).toEqual({ok: true});
    expect(second.data).toEqual({ok: true});
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    const retried = mockApi.history.get.slice(2);
    for (const request of retried) {
      expect(request.headers?.Authorization).toBe('Bearer new-at');
    }
  });

  it('clears tokens and auth when no refresh token exists', async () => {
    mockTokenStore.accessToken = 'at-1';
    mockTokenStore.refreshToken = null;
    mockApi.onGet('/protected').reply(401, {
      success: false,
      error: {message: 'expired'},
    });

    await expect(client.get('/protected')).rejects.toBeDefined();

    expect(storage.clearTokens).toHaveBeenCalled();
    const store = useAuthStore.getState();
    expect(store.isAuthenticated).toBe(false);
    expect(store.token).toBeNull();
    expect(store.hydrated).toBe(true);
  });

  it('rejects queued requests and clears auth when refresh fails', async () => {
    mockTokenStore.accessToken = 'old-at';
    mockTokenStore.refreshToken = 'rt-1';
    const refreshError = new Error('network down');
    refreshSpy.mockRejectedValue(refreshError);
    mockApi
      .onGet('/protected')
      .replyOnce(401)
      .onGet('/protected')
      .replyOnce(401);

    const [first, second] = await Promise.allSettled([
      client.get('/protected'),
      client.get('/protected'),
    ]);

    expect(first.status).toBe('rejected');
    expect(second.status).toBe('rejected');
    expect(storage.clearTokens).toHaveBeenCalled();
    expect(useAuthStore.getState().token).toBeNull();
  });
});
