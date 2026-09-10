import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import client from '../../services/api/client';
import {classifyError} from '../../services/api/errors';
import {unwrapEnvelope} from '../../services/api/envelope';
import {log} from '../../services/logging/logger';
import {useAuthStore} from '../auth/authStore';
import type {
  LinkGoogleMobileRequest,
  UploadFileResponse,
  User,
  UserProfileUpdate,
} from '../../types/api';

export const PROFILE_QUERY_KEY = ['profile'];

const fetchProfile = async (): Promise<User> => {
  const response = await client.get('/users/me/profile');
  return unwrapEnvelope<User>(response);
};

export const useGetProfileQuery = () =>
  useQuery({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: fetchProfile,
    staleTime: 5 * 60 * 1000,
  });

export const useUpdateProfileMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UserProfileUpdate) => {
      const response = await client.patch('/users/me/profile', data);
      return unwrapEnvelope<User>(response);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, updated);
      useAuthStore.getState().setUser(updated);
    },
    onError: (error: unknown) => {
      log.warn('updateProfile failed', classifyError(error));
    },
  });
};

export const useUploadFileMutation = () =>
  useMutation({
    mutationFn: async (file: {uri: string; name: string; type: string}) => {
      const formData = new FormData();
      formData.append('file', file);
      const response = await client.post<UploadFileResponse>(
        '/files/upload?max_size=400',
        formData,
        {headers: {'Content-Type': 'multipart/form-data'}},
      );
      return response.data;
    },
    onError: (error: unknown) => {
      log.warn('uploadFile failed', classifyError(error));
    },
  });

export const useLinkGoogleMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (idToken: string) => {
      const payload: LinkGoogleMobileRequest = {id_token: idToken};
      const response = await client.post(
        '/users/me/link/google/mobile',
        payload,
      );
      return unwrapEnvelope<User>(response);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, updated);
      useAuthStore.getState().setUser(updated);
    },
    onError: (error: unknown) => {
      log.warn('linkGoogle failed', classifyError(error));
    },
  });
};
