import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';

import client from '../../services/api/client';
import {classifyError} from '../../services/api/errors';
import {log} from '../../services/logging/logger';
import {normalizeChatMessage, normalizeConversationItem} from './normalize';
import type {
  ChatMessage,
  ConversationCreateRequest,
  ConversationItem,
} from './types';

export const CHATS_QUERY_KEY = ['chats'];

const fetchConversations = async (): Promise<ConversationItem[]> => {
  const response = await client.get<unknown>('/chats');
  const data = response.data;
  const conversations = Array.isArray(data) ? data : [];
  return conversations.map((conversation) =>
    normalizeConversationItem(conversation as Partial<ConversationItem>),
  );
};

const fetchConversationMessages = async (
  conversationId: string,
): Promise<ChatMessage[]> => {
  const response = await client.get<unknown>(
    `/chats/${conversationId}/messages`,
  );
  const data = response.data;
  const messages = Array.isArray(data) ? data : [];
  return messages.map((message) =>
    normalizeChatMessage(message as Partial<ChatMessage>),
  );
};

const createConversation = async (
  request: ConversationCreateRequest,
): Promise<ConversationItem> => {
  const response = await client.post<unknown>('/chats', request);
  return normalizeConversationItem(response.data as Partial<ConversationItem>);
};

const deleteConversation = async (conversationId: string): Promise<void> => {
  await client.delete(`/chats/${conversationId}`);
};

export const useGetConversationsQuery = () =>
  useQuery({
    queryKey: CHATS_QUERY_KEY,
    queryFn: fetchConversations,
  });

export const useGetConversationMessagesQuery = (
  conversationId: string | null,
) =>
  useQuery({
    queryKey: ['chats', conversationId ?? '', 'messages'],
    queryFn: () => fetchConversationMessages(conversationId ?? ''),
    enabled: conversationId != null,
  });

export const useCreateConversationMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createConversation,
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: CHATS_QUERY_KEY});
    },
    onError: (error: unknown) => {
      log.warn('createConversation failed', classifyError(error));
    },
  });
};

export const useDeleteConversationMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      void queryClient.invalidateQueries({queryKey: CHATS_QUERY_KEY});
    },
    onError: (error: unknown) => {
      log.warn('deleteConversation failed', classifyError(error));
    },
  });
};
