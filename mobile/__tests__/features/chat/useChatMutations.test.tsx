import {renderHook, waitFor, act} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import client from '../../../src/services/api/client';
import {
  useCreateConversationMutation,
  useDeleteConversationMutation,
  useGetConversationMessagesQuery,
  useGetConversationsQuery,
} from '../../../src/features/chat/useChatMutations';
import type {
  ChatMessage,
  ConversationItem,
} from '../../../src/features/chat/types';

const conversation: ConversationItem = {
  id: 'conv-1',
  title: 'Dresses',
  status: 'active',
  user_message_count: 2,
  last_activity_at: '2026-08-01T10:00:00Z',
  locale: 'en',
  created_at: '2026-08-01T09:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
};

const message: ChatMessage = {
  id: 'msg-1',
  conversation_id: 'conv-1',
  role: 'assistant',
  content: 'Here are some dresses',
  status: 'completed',
  token_count: 10,
  product_snapshots: [],
  search_context: null,
  debug: null,
  feedback: null,
  created_at: '2026-08-01T10:00:00Z',
  error: null,
  locale: null,
};

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
  queryClient.clear();
  mockApi = new MockAdapter(client);
});

afterEach(() => {
  queryClient.clear();
  mockApi.restore();
});

describe('useGetConversationsQuery', () => {
  it('fetches the raw conversation list (no envelope)', async () => {
    mockApi.onGet('/chats').reply(200, [conversation]);

    const {result} = await renderHook(() => useGetConversationsQuery(), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual([conversation]);
    });
  });

  it('falls back to an empty list for a non-array payload', async () => {
    mockApi.onGet('/chats').reply(200, {results: []});

    const {result} = await renderHook(() => useGetConversationsQuery(), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual([]);
    });
  });
});

describe('useGetConversationMessagesQuery', () => {
  it('fetches messages for the active conversation', async () => {
    mockApi.onGet('/chats/conv-1/messages').reply(200, [message]);

    const {result} = await renderHook(
      () => useGetConversationMessagesQuery('conv-1'),
      {wrapper},
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual([message]);
    });
  });

  it('stays disabled without a conversation id', async () => {
    const {result} = await renderHook(
      () => useGetConversationMessagesQuery(null),
      {wrapper},
    );

    expect(result.current.isPending).toBe(true);
    expect(mockApi.history.get).toHaveLength(0);
  });

  it('normalizes malformed message payloads from the API', async () => {
    mockApi
      .onGet('/chats/conv-1/messages')
      .reply(200, [
        {id: 'msg-bad', content: 'no snapshots', product_snapshots: null},
      ]);

    const {result} = await renderHook(
      () => useGetConversationMessagesQuery('conv-1'),
      {wrapper},
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.product_snapshots).toEqual([]);
    expect(result.current.data?.[0]?.role).toBe('assistant');
    expect(result.current.data?.[0]?.created_at).toBe('');
  });

  it('falls back to an empty list for a non-array payload', async () => {
    mockApi.onGet('/chats/conv-1/messages').reply(200, {messages: []});

    const {result} = await renderHook(
      () => useGetConversationMessagesQuery('conv-1'),
      {wrapper},
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual([]);
    });
  });
});

describe('useCreateConversationMutation', () => {
  it('POSTs create_new and invalidates the chats list', async () => {
    mockApi.onPost('/chats').reply(201, {...conversation, id: 'conv-new'});
    mockApi
      .onGet('/chats')
      .replyOnce(200, [{...conversation, id: 'conv-0'}])
      .onGet('/chats')
      .reply(200, [{...conversation, id: 'conv-new'}]);

    await renderHook(() => useGetConversationsQuery(), {wrapper});

    const {result} = await renderHook(() => useCreateConversationMutation(), {
      wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({locale: 'ar', create_new: true});
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(JSON.parse(mockApi.history.post[0].data as string)).toEqual({
      locale: 'ar',
      create_new: true,
    });
    await waitFor(() =>
      expect(queryClient.getQueryData(['chats'])).toEqual([
        {...conversation, id: 'conv-new'},
      ]),
    );
  });

  it('propagates create failures to the caller', async () => {
    mockApi.onPost('/chats').reply(500);

    const {result} = await renderHook(() => useCreateConversationMutation(), {
      wrapper,
    });

    await act(async () => {
      await expect(
        result.current.mutateAsync({locale: 'en', create_new: true}),
      ).rejects.toThrow();
    });
  });
});

describe('useDeleteConversationMutation', () => {
  it('DELETEs the conversation and invalidates the chats list', async () => {
    mockApi.onDelete('/chats/conv-1').reply(204);
    mockApi
      .onGet('/chats')
      .replyOnce(200, [conversation])
      .onGet('/chats')
      .reply(200, []);

    await renderHook(() => useGetConversationsQuery(), {wrapper});

    const {result} = await renderHook(() => useDeleteConversationMutation(), {
      wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync('conv-1');
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.history.delete[0].url).toBe('/chats/conv-1');
    await waitFor(() =>
      expect(queryClient.getQueryData(['chats'])).toEqual([]),
    );
  });

  it('propagates delete failures to the caller', async () => {
    mockApi.onDelete('/chats/conv-1').reply(500);

    const {result} = await renderHook(() => useDeleteConversationMutation(), {
      wrapper,
    });

    await act(async () => {
      await expect(result.current.mutateAsync('conv-1')).rejects.toThrow();
    });
  });
});
