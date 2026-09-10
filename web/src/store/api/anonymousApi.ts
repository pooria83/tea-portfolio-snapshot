import { baseApi } from "./baseApi";
import type { ConversationItem, ProductListItem } from "@/types/api";

export interface AnonymousChatSession {
  token: string;
  conversation: ConversationItem;
}

export const anonymousApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getAnonymousChatSession: builder.mutation<
      AnonymousChatSession,
      { locale: string; appVersion?: string }
    >({
      query: (body) => ({
        url: "/chat/anonymous-session",
        method: "POST",
        body: {
          locale: body.locale,
          app_version: body.appVersion ?? "",
        },
      }),
      transformResponse: (res: AnonymousChatSession) => res,
    }),
    getRandomProducts: builder.query<ProductListItem[], { limit?: number }>({
      query: ({ limit = 20 }) => ({
        url: "/public/products/random",
        params: { limit },
      }),
      transformResponse: (res: { data: ProductListItem[] }) => res.data,
    }),
  }),
  overrideExisting: true,
});

export const { useGetAnonymousChatSessionMutation, useGetRandomProductsQuery } = anonymousApi;
