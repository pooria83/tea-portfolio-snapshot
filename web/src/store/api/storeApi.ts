import { z } from "zod";
import { baseApi } from "./baseApi";
import type {
  CategoryOption,
  CountryOption,
  CurrencyOption,
  StoreListItem,
  StoreMember,
  StoreMemberAddRequest,
  StoreResponse,
  StoreCreate,
  StoreUpdate,
} from "@/types/api";
import {
  withValidation,
  CategoryOptionSchema,
  StoreListItemSchema,
  StoreResponseSchema,
} from "@/lib/validation";

const StoreMemberSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  role: z.enum(["owner", "manager"]),
  full_name: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
});

const storeApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCategories: builder.query<CategoryOption[], { locale: string }>({
      query: ({ locale }) => `/categories?locale=${locale}`,
      transformResponse: withValidation(CategoryOptionSchema.array()),
    }),
    getStoreTypes: builder.query<{ id: string; name: string }[], { locale: string }>({
      query: ({ locale }) => `/store-types?locale=${locale}`,
      transformResponse: withValidation(z.object({ id: z.string(), name: z.string() }).array()),
    }),

    getCountries: builder.query<CountryOption[], { locale: string }>({
      query: ({ locale }) => `/stores/countries?locale=${locale}`,
      transformResponse: (
        res: { data: { code: string; name_ar: string; name_en: string; name_fa: string }[] },
        _meta,
        arg,
      ) =>
        res.data.map((c) => ({
          code: c.code,
          name: c[`name_${arg.locale as "ar" | "en" | "fa"}` as keyof typeof c] || c.name_en,
        })),
    }),

    getCurrencies: builder.query<CurrencyOption[], { locale: string }>({
      query: ({ locale }) => `/stores/currencies?locale=${locale}`,
      transformResponse: (
        res: {
          data: {
            code: string;
            name_ar: string;
            name_en: string;
            name_fa: string;
            symbol: string;
          }[];
        },
        _meta,
        arg,
      ) =>
        res.data.map((c) => ({
          code: c.code,
          name: c[`name_${arg.locale as "ar" | "en" | "fa"}` as keyof typeof c] || c.name_en,
          symbol: c.symbol,
        })),
    }),

    getMyStores: builder.query<StoreListItem[], void>({
      query: () => "/stores/my",
      providesTags: ["Store"],
      transformResponse: withValidation(StoreListItemSchema.array()),
    }),

    getStore: builder.query<StoreResponse, string>({
      query: (id) => `/stores/${id}`,
      providesTags: (_result, _error, id) => [{ type: "Store", id }],
      transformResponse: withValidation(StoreResponseSchema),
    }),

    createStore: builder.mutation<StoreResponse, StoreCreate>({
      query: (body) => ({
        url: "/stores",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Store"],
      transformResponse: withValidation(StoreResponseSchema),
    }),

    updateStore: builder.mutation<StoreResponse, { id: string; body: StoreUpdate }>({
      query: ({ id, body }) => ({
        url: `/stores/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { id }) => ["Store", { type: "Store", id }],
      transformResponse: withValidation(StoreResponseSchema),
    }),

    deleteStore: builder.mutation<void, string>({
      query: (id) => ({
        url: `/stores/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Store"],
    }),

    getStoreMembers: builder.query<StoreMember[], string>({
      query: (storeId) => `/stores/${storeId}/members`,
      providesTags: (_result, _error, storeId) => [{ type: "Store", id: storeId }],
      transformResponse: withValidation(StoreMemberSchema.array()),
    }),

    addStoreMember: builder.mutation<StoreMember, { storeId: string; data: StoreMemberAddRequest }>(
      {
        query: ({ storeId, data }) => ({
          url: `/stores/${storeId}/members`,
          method: "POST",
          body: data,
        }),
        invalidatesTags: (_result, _error, { storeId }) => [
          "Store",
          { type: "Store", id: storeId },
        ],
        transformResponse: withValidation(StoreMemberSchema),
      },
    ),

    removeStoreMember: builder.mutation<void, { storeId: string; memberId: string }>({
      query: ({ storeId, memberId }) => ({
        url: `/stores/${storeId}/members/${memberId}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, { storeId }) => ["Store", { type: "Store", id: storeId }],
    }),
  }),
  overrideExisting: true,
});

export const {
  useGetCategoriesQuery,
  useGetCountriesQuery,
  useGetCurrenciesQuery,
  useGetStoreTypesQuery,
  useGetMyStoresQuery,
  useGetStoreQuery,
  useCreateStoreMutation,
  useUpdateStoreMutation,
  useDeleteStoreMutation,
  useGetStoreMembersQuery,
  useAddStoreMemberMutation,
  useRemoveStoreMemberMutation,
} = storeApi;
