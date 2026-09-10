import {renderHook, waitFor, act} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import client from '../../../src/services/api/client';
import {useAuthStore} from '../../../src/features/auth/authStore';
import {
  useGetProfileQuery,
  useLinkGoogleMutation,
  useUpdateProfileMutation,
  useUploadFileMutation,
} from '../../../src/features/profile/useProfileMutations';
import {mockUser} from '../../fixtures/user';

let mockApi: MockAdapter;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {retry: false, gcTime: 0},
    mutations: {retry: false, gcTime: 0},
  },
});

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

beforeEach(() => {
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
  queryClient.clear();
  mockApi = new MockAdapter(client);
});

afterEach(() => {
  queryClient.clear();
  mockApi.restore();
});

describe('useGetProfileQuery', () => {
  it('fetches /users/me/profile from the envelope', async () => {
    mockApi.onGet('/users/me/profile').reply(200, {
      success: true,
      data: mockUser,
    });

    const {result} = await renderHook(() => useGetProfileQuery(), {wrapper});

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(mockUser);
    });
  });
});

describe('useUpdateProfileMutation', () => {
  it('PATCHes /users/me/profile and updates the cache', async () => {
    const updated = {...mockUser, full_name: 'New Name'};
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});
    mockApi
      .onPatch('/users/me/profile')
      .reply(200, {success: true, data: updated});

    await renderHook(() => useGetProfileQuery(), {wrapper});

    const {result} = await renderHook(() => useUpdateProfileMutation(), {
      wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({full_name: 'New Name'});
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() =>
      expect(queryClient.getQueryData(['profile'])).toEqual(updated),
    );
  });
});

describe('useUploadFileMutation', () => {
  it('POSTs multipart to /files/upload?max_size=400 and returns the url', async () => {
    const uploaded = {
      file_name: 'abc.jpg',
      original_name: 'photo.jpg',
      content_type: 'image/jpeg',
      size: 1234,
      url: 'https://portfolio.example.invalid/temp-files/abc.jpg',
    };
    mockApi.onPost('/files/upload?max_size=400').reply(201, uploaded);

    const {result} = await renderHook(() => useUploadFileMutation(), {
      wrapper,
    });

    const response = await result.current.mutateAsync({
      uri: 'file:///tmp/photo.jpg',
      name: 'photo.jpg',
      type: 'image/jpeg',
    });

    expect(response.url).toBe(uploaded.url);
    const request = mockApi.history.post[0];
    expect(request.headers?.['Content-Type']).toContain('multipart/form-data');
  });
});

describe('useLinkGoogleMutation', () => {
  it('POSTs id_token to /users/me/link/google/mobile', async () => {
    const linked = {...mockUser, has_google: true};
    mockApi
      .onGet('/users/me/profile')
      .reply(200, {success: true, data: mockUser});
    mockApi
      .onPost('/users/me/link/google/mobile')
      .reply(200, {success: true, data: linked});

    await renderHook(() => useGetProfileQuery(), {wrapper});

    const {result} = await renderHook(() => useLinkGoogleMutation(), {
      wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync('google-id-token');
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() =>
      expect(queryClient.getQueryData(['profile'])).toEqual(linked),
    );
    expect(mockApi.history.post[0].data).toBe('{"id_token":"google-id-token"}');
  });
});
