import { baseApi } from "./baseApi";
import type {
  AdminChatMessage,
  AdminConversationItem,
  CronProductDetail,
  CronProductItem,
  CronSummary,
  EmbeddingCronProductDetail,
  EmbeddingCronProductItem,
  EmbedModelItem,
  EmbedTextRequest,
  EmbedTextResponse,
  EvalImportResult,
  EvalJudgmentsRequest,
  EvalMetricsResponse,
  EvalQueriesGenerateRequest,
  EvalQueriesImportRequest,
  EvalQueryItem,
  EvalQueryListResponse,
  EvalQueryUpdate,
  EvalSearchRequest,
  EvalSearchResponse,
  LLMApiKeyItem,
  LLMModelItem,
  LLMSettingsResponse,
  LLMSettingsUpdate,
  PaginationMeta,
  PromptTemplateResponse,
  PromptTemplateUpdate,
  ScraperHeaderItem,
  SystemSettingItem,
  SystemSettingUpdate,
} from "@/types/api";

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
}

interface AddApiKeyRequest {
  model_id: string;
  name?: string;
  api_key: string;
}

interface AddApiKeyResponse {
  id: string;
  model_id: string;
  name?: string | null;
  is_active: boolean;
  masked_key: string;
  created_at: string;
}

export const adminApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getLLMModels: builder.query<LLMModelItem[], void>({
      query: () => "/admin/llm/models",
      providesTags: ["LLMModels"],
      transformResponse: (res: ApiEnvelope<LLMModelItem[]>) => res.data,
    }),

    getEmbedModels: builder.query<EmbedModelItem[], void>({
      query: () => "/admin/embed-models",
      providesTags: ["EmbedModels"],
      transformResponse: (res: ApiEnvelope<EmbedModelItem[]>) => res.data,
    }),

    addLLMApiKey: builder.mutation<AddApiKeyResponse, AddApiKeyRequest>({
      query: (body) => ({
        url: "/admin/llm/api-keys",
        method: "POST",
        body,
      }),
      invalidatesTags: ["LLMModels"],
      transformResponse: (res: ApiEnvelope<AddApiKeyResponse>) => res.data,
    }),

    toggleLLMApiKey: builder.mutation<LLMApiKeyItem, string>({
      query: (keyId) => ({
        url: `/admin/llm/api-keys/${keyId}/toggle`,
        method: "PATCH",
      }),
      invalidatesTags: ["LLMModels"],
      transformResponse: (res: ApiEnvelope<LLMApiKeyItem>) => res.data,
    }),

    deleteLLMApiKey: builder.mutation<void, string>({
      query: (keyId) => ({
        url: `/admin/llm/api-keys/${keyId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["LLMModels"],
    }),

    getLLMSettings: builder.query<LLMSettingsResponse, void>({
      query: () => "/admin/llm/settings",
      providesTags: ["LLMSettings"],
      transformResponse: (res: ApiEnvelope<LLMSettingsResponse>) => res.data,
    }),

    updateLLMSettings: builder.mutation<LLMSettingsResponse, LLMSettingsUpdate>({
      query: (body) => ({
        url: "/admin/llm/settings",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["LLMSettings", "LLMModels"],
      transformResponse: (res: ApiEnvelope<LLMSettingsResponse>) => res.data,
    }),

    getPromptTemplates: builder.query<PromptTemplateResponse, void>({
      query: () => "/admin/llm/prompt-templates",
      providesTags: ["PromptTemplates"],
      transformResponse: (res: ApiEnvelope<PromptTemplateResponse>) => res.data,
    }),

    updatePromptTemplates: builder.mutation<PromptTemplateResponse, PromptTemplateUpdate>({
      query: (body) => ({
        url: "/admin/llm/prompt-templates",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["PromptTemplates"],
      transformResponse: (res: ApiEnvelope<PromptTemplateResponse>) => res.data,
    }),

    getSystemSettings: builder.query<SystemSettingItem[], void>({
      query: () => "/admin/system-settings",
      providesTags: ["SystemSettings"],
      transformResponse: (res: ApiEnvelope<SystemSettingItem[]>) => res.data,
    }),

    updateSystemSetting: builder.mutation<SystemSettingItem, SystemSettingUpdate>({
      query: (body) => ({
        url: "/admin/system-settings",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["SystemSettings"],
      transformResponse: (res: ApiEnvelope<SystemSettingItem>) => res.data,
    }),

    getScraperHeaders: builder.query<ScraperHeaderItem[], void>({
      query: () => "/admin/scraper-headers",
      providesTags: ["ScraperHeaders"],
      transformResponse: (res: ApiEnvelope<ScraperHeaderItem[]>) => res.data,
    }),

    updateScraperHeader: builder.mutation<ScraperHeaderItem, { name: string; header: string }>({
      query: ({ name, header }) => ({
        url: `/admin/scraper-headers/${name}`,
        method: "PUT",
        body: { header },
      }),
      invalidatesTags: ["ScraperHeaders"],
      transformResponse: (res: ApiEnvelope<ScraperHeaderItem>) => res.data,
    }),

    clearScraperHeader: builder.mutation<ScraperHeaderItem, string>({
      query: (name) => ({
        url: `/admin/scraper-headers/${name}`,
        method: "DELETE",
      }),
      invalidatesTags: ["ScraperHeaders"],
      transformResponse: (res: ApiEnvelope<ScraperHeaderItem>) => res.data,
    }),

    embedText: builder.mutation<EmbedTextResponse, EmbedTextRequest>({
      query: (body) => ({
        url: "/admin/ai-engine/embed-text",
        method: "POST",
        body,
      }),
      transformResponse: (res: ApiEnvelope<EmbedTextResponse>) => res.data,
    }),

    getCronProducts: builder.query<
      { items: CronProductItem[]; meta: PaginationMeta },
      { status?: string; skip?: number; limit?: number }
    >({
      query: (params) => ({
        url: "/admin/cron/products",
        params,
      }),
      providesTags: ["CronProducts"],
      transformResponse: (res: ApiEnvelope<CronProductItem[]> & { meta: PaginationMeta }) => ({
        items: res.data,
        meta: res.meta,
      }),
    }),

    getCronProductDetail: builder.query<CronProductDetail, string>({
      query: (productId) => `/admin/cron/products/${productId}`,
      transformResponse: (res: ApiEnvelope<CronProductDetail>) => res.data,
    }),

    getCronSummary: builder.query<CronSummary, void>({
      query: () => "/admin/cron/summary",
      providesTags: ["CronProducts", "EmbeddingCronProducts"],
      transformResponse: (res: ApiEnvelope<CronSummary>) => res.data,
    }),

    getEmbeddingCronProducts: builder.query<
      { items: EmbeddingCronProductItem[]; meta: PaginationMeta },
      { embedding_status?: string; model?: string; skip?: number; limit?: number }
    >({
      query: (params) => ({
        url: "/admin/cron/embedding-products",
        params,
      }),
      providesTags: ["EmbeddingCronProducts"],
      transformResponse: (
        res: ApiEnvelope<EmbeddingCronProductItem[]> & { meta: PaginationMeta },
      ) => ({
        items: res.data,
        meta: res.meta,
      }),
    }),

    getEmbeddingCronProductDetail: builder.query<EmbeddingCronProductDetail, string>({
      query: (productId) => `/admin/cron/embedding-products/${productId}`,
      transformResponse: (res: ApiEnvelope<EmbeddingCronProductDetail>) => res.data,
    }),

    getActiveEmbeddingModel: builder.query<{ active_model: string }, void>({
      query: () => "/admin/cron/embedding-products/active-model",
      transformResponse: (res: ApiEnvelope<{ active_model: string }>) => res.data,
    }),

    reindexEmbeddings: builder.mutation<{ affected: number; active_model: string }, void>({
      query: () => ({
        url: "/admin/cron/embedding-products/reindex",
        method: "POST",
      }),
      invalidatesTags: ["EmbeddingCronProducts"],
      transformResponse: (res: ApiEnvelope<{ affected: number; active_model: string }>) => res.data,
    }),

    getAdminChats: builder.query<
      { items: AdminConversationItem[]; meta: PaginationMeta },
      { skip?: number; limit?: number }
    >({
      query: (params) => ({
        url: "/admin/chats",
        params,
      }),
      providesTags: ["AdminChats"],
      transformResponse: (
        res: ApiEnvelope<AdminConversationItem[]> & { meta: PaginationMeta },
      ) => ({
        items: res.data,
        meta: res.meta,
      }),
    }),

    getAdminChatMessages: builder.query<AdminChatMessage[], string>({
      query: (conversationId) => `/admin/chats/${conversationId}/messages`,
      providesTags: ["AdminChats"],
      transformResponse: (res: ApiEnvelope<AdminChatMessage[]>) => res.data,
    }),

    getEvalQueries: builder.query<
      EvalQueryListResponse,
      {
        locale?: string;
        source?: string;
        status?: string;
        q?: string;
        skip?: number;
        limit?: number;
      }
    >({
      query: (params) => ({
        url: "/admin/search-eval/queries",
        params,
      }),
      providesTags: ["EvalQueries"],
      transformResponse: (res: ApiEnvelope<EvalQueryListResponse>) => res.data,
    }),

    evalGenerateQueries: builder.mutation<EvalQueryItem[], EvalQueriesGenerateRequest>({
      query: (body) => ({
        url: "/admin/search-eval/queries/generate",
        method: "POST",
        body,
      }),
      invalidatesTags: ["EvalQueries", "EvalMetrics"],
      transformResponse: (res: ApiEnvelope<EvalQueryItem[]>) => res.data,
    }),

    evalImportQueries: builder.mutation<EvalImportResult, EvalQueriesImportRequest>({
      query: (body) => ({
        url: "/admin/search-eval/queries/import",
        method: "POST",
        body,
      }),
      invalidatesTags: ["EvalQueries", "EvalMetrics"],
      transformResponse: (res: ApiEnvelope<EvalImportResult>) => res.data,
    }),

    updateEvalQuery: builder.mutation<EvalQueryItem, { queryId: string; body: EvalQueryUpdate }>({
      query: ({ queryId, body }) => ({
        url: `/admin/search-eval/queries/${queryId}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["EvalQueries", "EvalMetrics"],
      transformResponse: (res: ApiEnvelope<EvalQueryItem>) => res.data,
    }),

    saveEvalJudgments: builder.mutation<
      EvalQueryItem,
      { queryId: string; body: EvalJudgmentsRequest }
    >({
      query: ({ queryId, body }) => ({
        url: `/admin/search-eval/queries/${queryId}/judgments`,
        method: "PUT",
        body,
      }),
      invalidatesTags: ["EvalQueries", "EvalMetrics"],
      transformResponse: (res: ApiEnvelope<EvalQueryItem>) => res.data,
    }),

    getEvalMetrics: builder.query<EvalMetricsResponse, void>({
      query: () => "/admin/search-eval/metrics",
      providesTags: ["EvalMetrics"],
      transformResponse: (res: ApiEnvelope<EvalMetricsResponse>) => res.data,
    }),

    evalSearch: builder.mutation<EvalSearchResponse, EvalSearchRequest>({
      query: (body) => ({
        url: "/admin/search-eval/search",
        method: "POST",
        body,
      }),
      transformResponse: (res: ApiEnvelope<EvalSearchResponse>) => res.data,
    }),
  }),
  overrideExisting: true,
});

export const {
  useGetLLMModelsQuery,
  useGetEmbedModelsQuery,
  useAddLLMApiKeyMutation,
  useToggleLLMApiKeyMutation,
  useDeleteLLMApiKeyMutation,
  useGetLLMSettingsQuery,
  useUpdateLLMSettingsMutation,
  useGetPromptTemplatesQuery,
  useUpdatePromptTemplatesMutation,
  useGetSystemSettingsQuery,
  useUpdateSystemSettingMutation,
  useGetScraperHeadersQuery,
  useUpdateScraperHeaderMutation,
  useClearScraperHeaderMutation,
  useEmbedTextMutation,
  useGetCronProductsQuery,
  useGetCronProductDetailQuery,
  useGetCronSummaryQuery,
  useGetEmbeddingCronProductsQuery,
  useGetEmbeddingCronProductDetailQuery,
  useGetActiveEmbeddingModelQuery,
  useReindexEmbeddingsMutation,
  useGetAdminChatsQuery,
  useGetAdminChatMessagesQuery,
  useGetEvalQueriesQuery,
  useEvalGenerateQueriesMutation,
  useEvalImportQueriesMutation,
  useUpdateEvalQueryMutation,
  useSaveEvalJudgmentsMutation,
  useGetEvalMetricsQuery,
  useEvalSearchMutation,
} = adminApi;
