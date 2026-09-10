import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import { Mutex } from "async-mutex";
import { logout } from "../slices/auth";

const mutex = new Mutex();

const baseQuery = fetchBaseQuery({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  prepareHeaders: (headers) => {
    headers.set("X-Requested-With", "XMLHttpRequest");
    return headers;
  },
  credentials: "include",
});

const baseQueryWithReauth: BaseQueryFn<FetchArgs | string, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  await mutex.waitForUnlock();
  let result = await baseQuery(args, api, extraOptions);

  if (result.error && result.error.status === 401) {
    if (mutex.isLocked()) {
      await mutex.waitForUnlock();
      result = await baseQuery(args, api, extraOptions);
    } else {
      const release = await mutex.acquire();
      try {
        const refreshResult = await baseQuery(
          { url: "/auth/refresh", method: "POST" },
          api,
          extraOptions,
        );

        if (refreshResult.data) {
          result = await baseQuery(args, api, extraOptions);
        } else {
          api.dispatch(logout());
        }
      } catch {
        api.dispatch(logout());
      } finally {
        release();
      }
    }
  }

  return result;
};

export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithReauth,
  tagTypes: [
    "Product",
    "Order",
    "Customer",
    "Settings",
    "Profile",
    "Store",
    "LLMModels",
    "LLMSettings",
    "EmbedModels",
    "PromptTemplates",
    "SystemSettings",
    "ScraperHeaders",
    "CronProducts",
    "EmbeddingCronProducts",
    "AdminChats",
    "Chats",
    "EvalQueries",
    "EvalMetrics",
  ],
  endpoints: (builder) => ({
    sendOtp: builder.mutation<void, { phone: string }>({
      query: (body) => ({
        url: "/auth/send-otp",
        method: "POST",
        body,
      }),
    }),

    verifyOtp: builder.mutation<
      { access_token: string; refresh_token: string; token_type: string },
      { phone: string; code: string }
    >({
      query: (body) => ({
        url: "/auth/verify-otp",
        method: "POST",
        body,
      }),
      transformResponse: (res: {
        success: boolean;
        data: { access_token: string; refresh_token: string; token_type: string };
      }) => res.data,
    }),

    googleCodeAuth: builder.mutation<
      { access_token: string; refresh_token: string; token_type: string },
      { code: string; redirect_uri: string; state?: string }
    >({
      query: (body) => ({
        url: "/auth/google/code",
        method: "POST",
        body,
      }),
      transformResponse: (res: {
        success: boolean;
        data: { access_token: string; refresh_token: string; token_type: string };
      }) => res.data,
    }),

    googleNonce: builder.mutation<{ state: string }, void>({
      query: () => ({
        url: "/auth/google/nonce",
        method: "POST",
      }),
      transformResponse: (res: { success: boolean; data: { state: string } }) => res.data,
    }),

    logout: builder.mutation<void, void>({
      query: () => ({
        url: "/auth/logout",
        method: "POST",
      }),
    }),

    getMe: builder.query<
      {
        id: string;
        full_name: string | null;
        username: string | null;
        phone: string | null;
        role: string;
        email: string | null;
      },
      void
    >({
      query: () => "/users/me",
      transformResponse: (res: {
        success: boolean;
        data: {
          id: string;
          full_name: string | null;
          username: string | null;
          phone: string | null;
          role: string;
          email: string | null;
        };
      }) => res.data,
    }),
  }),
});
