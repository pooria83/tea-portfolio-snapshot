import { baseApi } from "./baseApi";
import type { UserProfile, UserProfileUpdate } from "@/types/api";

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
}

const profileApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProfile: builder.query<UserProfile, void>({
      query: () => "/users/me/profile",
      providesTags: ["Profile"],
      transformResponse: (res: ApiEnvelope<UserProfile>) => res.data,
    }),

    updateProfile: builder.mutation<UserProfile, UserProfileUpdate>({
      query: (body) => ({
        url: "/users/me/profile",
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["Profile"],
      transformResponse: (res: ApiEnvelope<UserProfile>) => res.data,
    }),

    linkPhone: builder.mutation<void, { phone: string }>({
      query: (body) => ({
        url: "/users/me/link/phone/send-otp",
        method: "POST",
        body,
      }),
    }),

    verifyLinkPhone: builder.mutation<UserProfile, { phone: string; code: string }>({
      query: (body) => ({
        url: "/users/me/link/phone/verify",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Profile"],
      transformResponse: (res: ApiEnvelope<UserProfile>) => res.data,
    }),

    linkGoogle: builder.mutation<
      UserProfile,
      { code: string; redirect_uri: string; state?: string }
    >({
      query: (body) => ({
        url: "/users/me/link/google",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Profile"],
      transformResponse: (res: ApiEnvelope<UserProfile>) => res.data,
    }),
  }),
  overrideExisting: true,
});

export const {
  useGetProfileQuery,
  useUpdateProfileMutation,
  useLinkPhoneMutation,
  useVerifyLinkPhoneMutation,
  useLinkGoogleMutation,
} = profileApi;
