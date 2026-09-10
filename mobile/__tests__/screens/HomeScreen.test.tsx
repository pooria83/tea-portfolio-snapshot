import {render, waitFor, userEvent, act} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import {AppState} from 'react-native';
import {storage} from '../../src/services/storage';
import client from '../../src/services/api/client';
import HomeScreen from '../../src/app/screens/HomeScreen';
import type {ConversationItem} from '../../src/features/chat/types';
import {
  MockWebSocket,
  expectSendFrame,
  installMockWebSocket,
} from '../features/chat/wsMock';

const activeConversation: ConversationItem = {
  id: 'conv-1',
  title: 'Dresses',
  status: 'active',
  user_message_count: 1,
  last_activity_at: '2026-08-01T10:00:00Z',
  locale: 'en',
  created_at: '2026-08-01T09:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
};

const closedConversation: ConversationItem = {
  ...activeConversation,
  id: 'conv-2',
  title: 'Old chat',
  status: 'closed',
};

let mockApi: MockAdapter;
let ws: ReturnType<typeof installMockWebSocket>;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {retry: false, gcTime: 0},
    mutations: {retry: false, gcTime: 0},
  },
});

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider client={queryClient}>
    <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
  </QueryClientProvider>
);

beforeEach(async () => {
  queryClient.clear();
  mockApi = new MockAdapter(client);
  ws = installMockWebSocket();
  jest.spyOn(AppState, 'addEventListener').mockReturnValue({
    remove: jest.fn(),
  } as never);
  await storage.setTokens('access-1', 'refresh-1');
});

afterEach(() => {
  ws.restore();
  jest.restoreAllMocks();
  jest.useRealTimers();
});

describe('HomeScreen chat', () => {
  it('shows the empty-state placeholder with no chat loaded', async () => {
    mockApi.onGet('/chats').reply(200, []);

    const {getByText} = await render(<HomeScreen />, {wrapper});

    expect(getByText('placeholder')).toBeTruthy();
  });

  it('creates a conversation on first send and streams the message', async () => {
    mockApi.onGet('/chats').reply(200, []);
    mockApi.onPost('/chats').reply(201, activeConversation);
    mockApi.onGet('/chats/conv-1/messages').reply(200, []);

    const user = userEvent.setup();
    const {getByPlaceholderText, getByText} = await render(<HomeScreen />, {
      wrapper,
    });

    await user.type(getByPlaceholderText('inputPlaceholder'), 'red dress');
    await user.press(getByText('send'));

    await waitFor(() => {
      expect(mockApi.history.post).toHaveLength(1);
      expect(JSON.parse(mockApi.history.post[0].data as string)).toEqual({
        locale: 'en',
        create_new: true,
      });
    });

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    expect(socket.url).toContain('/ws/chat/conv-1?token=access-1');

    expect(getByText('red dress')).toBeTruthy();

    await act(async () => {
      socket.open();
    });

    await waitFor(() =>
      expect(expectSendFrame(socket, 'send_message')).toEqual({
        type: 'send_message',
        content: 'red dress',
        idempotency_key: expect.any(String),
        include_saved_message: true,
      }),
    );
  });

  it('renders the conversation history with user and assistant bubbles', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, [
      {
        id: 'm1',
        conversation_id: 'conv-1',
        role: 'user',
        content: 'show me dresses',
        status: 'completed',
        token_count: null,
        product_snapshots: [],
        search_context: null,
        debug: null,
        feedback: null,
        created_at: '2026-08-01T09:30:00Z',
        error: null,
      },
      {
        id: 'm2',
        conversation_id: 'conv-1',
        role: 'assistant',
        content: 'Here are some options',
        status: 'completed',
        token_count: 12,
        product_snapshots: [],
        search_context: null,
        debug: null,
        feedback: null,
        created_at: '2026-08-01T09:31:00Z',
        error: null,
      },
    ]);

    const user = userEvent.setup();
    const {getByText, getByLabelText} = await render(<HomeScreen />, {
      wrapper,
    });

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));

    await waitFor(() => expect(getByText('show me dresses')).toBeTruthy());
    expect(getByText('Here are some options')).toBeTruthy();
  });

  it('shows the closed banner and disables sending for closed conversations', async () => {
    mockApi.onGet('/chats').reply(200, [closedConversation]);
    mockApi.onGet('/chats/conv-2/messages').reply(200, []);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByPlaceholderText, getByTestId} =
      await render(<HomeScreen />, {wrapper});

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Old chat'));

    await waitFor(() => expect(getByText('closedNote')).toBeTruthy());

    const sendButton = getByTestId('button');
    const input = getByPlaceholderText('inputPlaceholder');
    await user.type(input, 'still typing');
    expect(sendButton.props.accessibilityState?.disabled).toBe(true);
  });

  it('shows the connection-lost banner and reconnects on retry', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, []);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByTestId} = await render(
      <HomeScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(getByText('send')).toBeTruthy());

    jest.useFakeTimers();
    for (let retry = 0; retry < 5; retry += 1) {
      const current =
        MockWebSocket.instances[MockWebSocket.instances.length - 1];
      await act(async () => {
        current?.close(1006);
      });
      await act(async () => {
        jest.advanceTimersByTime(31_000);
      });
      await waitFor(() =>
        expect(MockWebSocket.instances).toHaveLength(retry + 2),
      );
    }

    const failed = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    await act(async () => {
      failed?.close(1006);
    });

    await waitFor(() => expect(getByText('connectionLost')).toBeTruthy());
    await user.press(getByTestId('connection-retry'));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(7));
    const reconnected =
      MockWebSocket.instances[MockWebSocket.instances.length - 1];
    await act(async () => {
      reconnected?.open();
    });
    await waitFor(() => expect(getByText('send')).toBeTruthy());
  });

  it('shows the load-failed state in the drawer and retries', async () => {
    mockApi
      .onGet('/chats')
      .replyOnce(500)
      .onGet('/chats')
      .reply(200, [activeConversation]);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByTestId} = await render(
      <HomeScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('openConversations'));
    await waitFor(() => expect(getByText('loadFailed')).toBeTruthy());

    await user.press(getByTestId('chats-retry'));
    await waitFor(() => expect(getByText('Dresses')).toBeTruthy());
  });

  it('shows the load-failed state for history and retries', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi
      .onGet('/chats/conv-1/messages')
      .replyOnce(500)
      .onGet('/chats/conv-1/messages')
      .reply(200, []);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByTestId} = await render(
      <HomeScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));
    await waitFor(() => expect(getByText('loadFailed')).toBeTruthy());

    await user.press(getByTestId('history-retry'));
    await waitFor(() => expect(getByText('placeholder')).toBeTruthy());
  });

  it('deletes a conversation from the drawer with confirmation', async () => {
    mockApi
      .onGet('/chats')
      .reply(200, [activeConversation, closedConversation]);
    mockApi.onDelete('/chats/conv-2').reply(204);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getAllByLabelText, getByTestId} =
      await render(<HomeScreen />, {wrapper});

    await user.press(getByLabelText('openConversations'));
    await waitFor(() => expect(getByText('Old chat')).toBeTruthy());

    const deleteButtons = getAllByLabelText('deleteChat');
    await user.press(deleteButtons[1]);

    await waitFor(() => expect(getByText('deleteConfirm')).toBeTruthy());
    await user.press(getByTestId('delete-conversation-confirm'));

    await waitFor(() =>
      expect(mockApi.history.delete[0].url).toBe('/chats/conv-2'),
    );
  });

  it('does not render any debug UI for messages with debug data', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, [
      {
        id: 'm1',
        conversation_id: 'conv-1',
        role: 'assistant',
        content: 'Here are some options',
        status: 'completed',
        token_count: 12,
        product_snapshots: [],
        search_context: null,
        debug: {prompt: {model: 'test'}, response: {content: 'ok'}},
        feedback: null,
        created_at: '2026-08-01T09:31:00Z',
        error: null,
      },
    ]);

    const user = userEvent.setup();
    const {getByText, getByLabelText, queryByText} = await render(
      <HomeScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));

    await waitFor(() =>
      expect(getByText('Here are some options')).toBeTruthy(),
    );
    expect(queryByText('debug')).toBeNull();
    expect(queryByText('debugTitle')).toBeNull();
  });

  it('clears the pending user message when switching conversations', async () => {
    mockApi
      .onGet('/chats')
      .reply(200, [activeConversation, closedConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, []);
    mockApi.onGet('/chats/conv-2/messages').reply(200, []);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByPlaceholderText, queryByText} =
      await render(<HomeScreen />, {wrapper});

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(getByText('send')).toBeTruthy());

    await user.type(
      getByPlaceholderText('inputPlaceholder'),
      'i want red dress',
    );
    await user.press(getByText('send'));
    await waitFor(() => expect(getByText('i want red dress')).toBeTruthy());

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Old chat'));
    await waitFor(() => expect(getByText('placeholder')).toBeTruthy());
    expect(queryByText('i want red dress')).toBeNull();
  });

  it('clears the pending user message when starting a new chat', async () => {
    mockApi.onGet('/chats').reply(200, []);
    mockApi.onGet('/chats/conv-1/messages').reply(200, []);
    mockApi.onPost('/chats').reply(201, activeConversation);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByPlaceholderText, queryByText} =
      await render(<HomeScreen />, {wrapper});

    await user.type(
      getByPlaceholderText('inputPlaceholder'),
      'i want red dress',
    );
    await user.press(getByText('send'));
    await waitFor(() => expect(getByText('i want red dress')).toBeTruthy());

    await user.press(getByLabelText('newChat'));
    await waitFor(() => expect(mockApi.history.post).toHaveLength(2));
    expect(queryByText('i want red dress')).toBeNull();
  });

  it('shows the failure text and retry button for a failed turn and retries with the SAME idempotency key', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, []);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByPlaceholderText, getByTestId} =
      await render(<HomeScreen />, {wrapper});

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(getByText('send')).toBeTruthy());

    await user.type(getByPlaceholderText('inputPlaceholder'), 'red dress');
    await user.press(getByText('send'));

    await waitFor(() =>
      expect(expectSendFrame(socket, 'send_message')).toEqual({
        type: 'send_message',
        content: 'red dress',
        idempotency_key: expect.any(String),
        include_saved_message: true,
      }),
    );
    const firstKey = (
      expectSendFrame(socket, 'send_message') as {
        idempotency_key: string;
      }
    ).idempotency_key;

    await act(async () => {
      socket.receive({type: 'error', code: 'embedding_failed'});
    });

    await waitFor(() => expect(getByText('embedding_failed')).toBeTruthy());
    const retryButton = getByTestId('chat-retry-stream');
    await user.press(retryButton);

    await waitFor(() =>
      expect(expectSendFrame(socket, 'send_message')).toEqual({
        type: 'send_message',
        content: 'red dress',
        idempotency_key: firstKey,
        include_saved_message: true,
      }),
    );
  });

  it('keeps the failure text and retry button after message_saved for a failed turn', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, []);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByPlaceholderText, getByTestId} =
      await render(<HomeScreen />, {wrapper});

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(getByText('send')).toBeTruthy());

    await user.type(getByPlaceholderText('inputPlaceholder'), 'red dress');
    await user.press(getByText('send'));
    await waitFor(() => expect(getByText('red dress')).toBeTruthy());

    await act(async () => {
      socket.receive({type: 'error', code: 'embedding_failed'});
    });
    await waitFor(() => expect(getByText('embedding_failed')).toBeTruthy());

    await act(async () => {
      socket.receive({
        type: 'message_saved',
        conversation_id: 'conv-1',
        message: {
          id: 'msg-failed-1',
          conversation_id: 'conv-1',
          role: 'assistant',
          content: '',
          status: 'failed',
          token_count: null,
          product_snapshots: [],
          search_context: {
            rewritten_query: null,
            filters: null,
            intent: 'error',
          },
          debug: null,
          feedback: null,
          created_at: '2026-08-01T09:31:00Z',
          error: 'embedding_failed',
          locale: null,
        },
      });
    });

    await waitFor(() => expect(getByText('embedding_failed')).toBeTruthy());
    expect(getByTestId('chat-retry-stream')).toBeTruthy();
  });

  it('shows the error text and retry for a failed saved turn loaded from history', async () => {
    mockApi.onGet('/chats').reply(200, [activeConversation]);
    mockApi.onGet('/chats/conv-1/messages').reply(200, [
      {
        id: 'm1',
        conversation_id: 'conv-1',
        role: 'user',
        content: 'show me dresses',
        status: 'completed',
        token_count: null,
        product_snapshots: [],
        search_context: null,
        debug: null,
        feedback: null,
        created_at: '2026-08-01T09:30:00Z',
        error: null,
      },
      {
        id: 'm2',
        conversation_id: 'conv-1',
        role: 'assistant',
        content: '',
        status: 'failed',
        token_count: null,
        product_snapshots: [],
        search_context: {
          rewritten_query: null,
          filters: null,
          intent: 'error',
        },
        debug: null,
        feedback: null,
        created_at: '2026-08-01T09:31:00Z',
        error: 'embedding_failed',
      },
    ]);

    const user = userEvent.setup();
    const {getByText, getByLabelText, getByTestId} = await render(
      <HomeScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('openConversations'));
    await user.press(getByText('Dresses'));

    await waitFor(() => expect(getByText('embedding_failed')).toBeTruthy());
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(getByText('send')).toBeTruthy());

    const retryButton = getByTestId('chat-retry');
    await user.press(retryButton);

    await waitFor(() =>
      expect(expectSendFrame(socket, 'send_message')).toEqual({
        type: 'send_message',
        content: 'show me dresses',
        idempotency_key: expect.any(String),
        include_saved_message: true,
      }),
    );
  });
});
