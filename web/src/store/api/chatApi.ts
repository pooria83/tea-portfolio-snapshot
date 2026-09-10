import { baseApi } from "./baseApi";
import type { ChatMessage, ConversationItem } from "@/types/api";

export const chatApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getMyChats: builder.query<ConversationItem[], void>({
      query: () => "/chats",
      providesTags: ["Chats"],
    }),

    createConversation: builder.mutation<ConversationItem, { locale: string; createNew?: boolean }>(
      {
        query: (body) => ({
          url: "/chats",
          method: "POST",
          body: { locale: body.locale, create_new: body.createNew ?? false },
        }),
        invalidatesTags: ["Chats"],
      },
    ),

    getChatMessages: builder.query<
      ChatMessage[],
      { conversationId: string; cursor?: string; limit?: number }
    >({
      query: ({ conversationId, cursor, limit }) => ({
        url: `/chats/${conversationId}/messages`,
        params: {
          ...(cursor ? { cursor } : {}),
          ...(limit ? { limit } : {}),
        },
      }),
      providesTags: (_result, _error, arg) => [{ type: "Chats", id: arg.conversationId }],
    }),

    deleteConversation: builder.mutation<void, string>({
      query: (conversationId) => ({
        url: `/chats/${conversationId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Chats"],
    }),
  }),
  overrideExisting: true,
});

export const {
  useGetMyChatsQuery,
  useCreateConversationMutation,
  useGetChatMessagesQuery,
  useDeleteConversationMutation,
} = chatApi;
