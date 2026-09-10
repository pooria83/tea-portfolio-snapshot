import {renderHook, waitFor, act} from '@testing-library/react-native';
import {AppState} from 'react-native';
import {storage} from '../../../src/services/storage';
import {useChatWebSocket} from '../../../src/features/chat/useChatWebSocket';
import {MockWebSocket, expectSendFrame, installMockWebSocket} from './wsMock';
import type {ChatMessage} from '../../../src/features/chat/types';

const savedMessage: ChatMessage = {
  id: 'msg-1',
  conversation_id: 'conv-1',
  role: 'assistant',
  content: 'Saved answer',
  status: 'completed',
  token_count: 5,
  product_snapshots: [],
  search_context: null,
  debug: null,
  feedback: null,
  created_at: '2026-08-01T10:00:00Z',
  error: null,
};

let ws: ReturnType<typeof installMockWebSocket>;
let appStateListener: (state: string) => void;

beforeEach(async () => {
  ws = installMockWebSocket();
  appStateListener = () => {};
  jest
    .spyOn(AppState, 'addEventListener')
    .mockImplementation((_type, listener) => {
      appStateListener = listener as (state: string) => void;
      return {
        remove: jest.fn(),
      } as never;
    });
  await storage.setTokens('access-1', 'refresh-1');
});

afterEach(() => {
  ws.restore();
  jest.restoreAllMocks();
  jest.useRealTimers();
});

describe('useChatWebSocket', () => {
  it('connects to the chat socket with the token in the URL', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    expect(socket.url).toBe(
      'ws://localhost:8000/api/v1/ws/chat/conv-1?token=access-1',
    );

    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));
  });

  it('queues a message until the socket opens, then flushes it', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];

    await act(async () => {
      result.current.sendMessage('hello world', 'key-1');
    });
    expect(socket.sent).toHaveLength(0);

    await act(async () => {
      socket.open();
    });
    await waitFor(() =>
      expect(expectSendFrame(socket, 'send_message')).toEqual({
        type: 'send_message',
        content: 'hello world',
        idempotency_key: 'key-1',
        include_saved_message: true,
      }),
    );
    expect(result.current.stream?.status).toBe('streaming');
  });

  it('sends immediately when the socket is open', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendMessage('now', 'key-2');
    });
    expect(expectSendFrame(socket, 'send_message')).toEqual({
      type: 'send_message',
      content: 'now',
      idempotency_key: 'key-2',
      include_saved_message: true,
    });
  });

  it('queues a similar request until the socket opens, then flushes it', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];

    await act(async () => {
      result.current.sendSimilarRequest('p-9', 'key-sim-1');
    });
    expect(socket.sent).toHaveLength(0);

    await act(async () => {
      socket.open();
    });
    await waitFor(() =>
      expect(expectSendFrame(socket, 'similar_request')).toEqual({
        type: 'similar_request',
        product_id: 'p-9',
        product_name: '',
        idempotency_key: 'key-sim-1',
        include_saved_message: true,
      }),
    );
    expect(result.current.stream?.status).toBe('streaming');
  });

  it('sends a similar request immediately and renders product cards then completes', async () => {
    const onMessageSaved = jest.fn();
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendSimilarRequest('p-9', 'key-sim-2');
    });
    expect(expectSendFrame(socket, 'similar_request')).toEqual({
      type: 'similar_request',
      product_id: 'p-9',
      product_name: '',
      idempotency_key: 'key-sim-2',
      include_saved_message: true,
    });

    await act(async () => {
      socket.receive({
        type: 'product_cards',
        products: [
          {
            id: 'p-10',
            name: 'Similar Dress',
            image_url: 'https://example.com/dress.jpg',
            buy_url: null,
            store_id: 'store-1',
          },
        ],
        locale: 'ar',
      });
      socket.receive({type: 'assistant_end'});
      socket.receive({
        type: 'message_saved',
        conversation_id: 'conv-1',
        message: {...savedMessage, id: 'msg-sim-1'},
      });
    });

    await waitFor(() =>
      expect(onMessageSaved).toHaveBeenCalledWith(
        {...savedMessage, id: 'msg-sim-1', locale: null},
        'conv-1',
      ),
    );
    await waitFor(() =>
      expect(result.current.stream?.status).toBe('completed'),
    );
    expect(result.current.stream?.products).toHaveLength(1);
    expect(result.current.stream?.locale).toBe('ar');
  });

  it('marks the stream as failed on product_not_found for a similar request', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendSimilarRequest('p-9', 'key-sim-3');
      socket.receive({type: 'error', code: 'product_not_found'});
    });

    await waitFor(() => expect(result.current.stream?.status).toBe('failed'));
    expect(result.current.stream?.error).toBe('product_not_found');
  });

  it('reports message_saved through onMessageSaved and completes the stream', async () => {
    const onMessageSaved = jest.fn();
    const {result} = await renderHook(() =>
      useChatWebSocket({
        conversationId: 'conv-1',
        onMessageSaved,
      }),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendMessage('ask', 'key-3');
    });
    await waitFor(() =>
      expect(result.current.stream?.status).toBe('streaming'),
    );

    await act(async () => {
      socket.receive({
        type: 'text_chunk',
        delta: 'Part ',
      });
      socket.receive({
        type: 'text_chunk',
        delta: 'two',
      });
      socket.receive({
        type: 'message_saved',
        message: savedMessage,
      });
    });

    await waitFor(() =>
      expect(onMessageSaved).toHaveBeenCalledWith(
        {...savedMessage, locale: null},
        'conv-1',
      ),
    );
    await waitFor(() =>
      expect(result.current.stream?.status).toBe('completed'),
    );
    expect(result.current.stream?.content).toBe('Part two');
  });

  it('marks the stream as failed on a chat error frame', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendMessage('ask', 'key-4');
      socket.receive({type: 'error', code: 'embedding_failed'});
    });

    await waitFor(() => expect(result.current.stream?.status).toBe('failed'));
    expect(result.current.stream?.error).toBe('embedding_failed');
  });

  it('marks the stream as failed with chat_failed for an unknown error code', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendMessage('ask', 'key-5');
      socket.receive({type: 'error', code: 'unknown_code'});
    });

    await waitFor(() => expect(result.current.stream?.status).toBe('failed'));
    expect(result.current.stream?.error).toBe('chat_failed');
  });

  it('keeps the failed stream failed after message_saved', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendMessage('ask', 'key-6');
      socket.receive({type: 'error', code: 'embedding_failed'});
    });
    await waitFor(() => expect(result.current.stream?.status).toBe('failed'));

    await act(async () => {
      socket.receive({
        type: 'message_saved',
        message: savedMessage,
      });
    });

    await waitFor(() => expect(result.current.stream?.status).toBe('failed'));
    expect(result.current.stream?.error).toBe('embedding_failed');
  });

  it('stays closed after a 4001 close code', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      socket.close(4001);
    });

    await waitFor(() => expect(result.current.status).toBe('closed'));
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('reconnects with backoff after an unexpected close', async () => {
    jest.useFakeTimers();
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const first = MockWebSocket.instances[0];
    await act(async () => {
      first.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      first.close(1006);
    });
    await waitFor(() => expect(result.current.status).toBe('reconnecting'));

    await act(async () => {
      jest.advanceTimersByTime(1000);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
    await waitFor(() => expect(result.current.status).toBe('connecting'));
  });

  it('sends a ping every 30 seconds while open', async () => {
    jest.useFakeTimers();
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      jest.advanceTimersByTime(30_000);
    });

    expect(socket.sent).toContainEqual('{"type":"ping"}');
  });

  it('stops retrying after max attempts and reports a failed status', async () => {
    jest.useFakeTimers();
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));

    for (let retry = 0; retry < 5; retry += 1) {
      const socket =
        MockWebSocket.instances[MockWebSocket.instances.length - 1];
      await act(async () => {
        socket?.close(1006);
      });
      await waitFor(() => expect(result.current.status).toBe('reconnecting'));
      await act(async () => {
        jest.advanceTimersByTime(31_000);
      });
      await waitFor(() =>
        expect(MockWebSocket.instances).toHaveLength(retry + 2),
      );
    }

    const last = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    await act(async () => {
      last?.close(1006);
    });
    await waitFor(() => expect(result.current.status).toBe('failed'));

    await act(async () => {
      jest.advanceTimersByTime(120_000);
    });
    expect(MockWebSocket.instances).toHaveLength(6);
  });

  it('retryConnect reconnects and flushes a queued message after failure', async () => {
    jest.useFakeTimers();
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    await act(async () => {
      result.current.sendMessage('hello world', 'key-1');
    });

    for (let retry = 0; retry < 5; retry += 1) {
      const socket =
        MockWebSocket.instances[MockWebSocket.instances.length - 1];
      await act(async () => {
        socket?.close(1006);
      });
      await act(async () => {
        jest.advanceTimersByTime(31_000);
      });
      await waitFor(() =>
        expect(MockWebSocket.instances).toHaveLength(retry + 2),
      );
    }

    const failedSocket =
      MockWebSocket.instances[MockWebSocket.instances.length - 1];
    await act(async () => {
      failedSocket?.close(1006);
    });
    await waitFor(() => expect(result.current.status).toBe('failed'));

    await act(async () => {
      result.current.retryConnect();
    });
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(7));
    await waitFor(() => expect(result.current.status).toBe('connecting'));

    const reconnected =
      MockWebSocket.instances[MockWebSocket.instances.length - 1];
    await act(async () => {
      reconnected?.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));
    await waitFor(() =>
      expect(
        expectSendFrame(reconnected as MockWebSocket, 'send_message'),
      ).toEqual({
        type: 'send_message',
        content: 'hello world',
        idempotency_key: 'key-1',
        include_saved_message: true,
      }),
    );
  });

  it('ignores invalid frames without crashing', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      socket.receive('not-json');
      socket.receive({type: 'unknown_frame'});
    });

    await waitFor(() => expect(result.current.status).toBe('open'));
    expect(result.current.stream).toBeNull();
  });

  it('handles assistant_start, debug and text_chunk frames', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.sendMessage('ask', 'key-6');
    });
    await act(async () => {
      socket.receive({
        type: 'debug',
        debug: {prompt: {q: 'ask'}, response: {}},
      });
      socket.receive({
        type: 'assistant_start',
        search_context: {rewritten_query: 'dresses', filters: null},
      });
      socket.receive({type: 'text_chunk', delta: 'Hi'});
      socket.receive({
        type: 'product_cards',
        products: [{id: 'p1', name: 'Dress'}],
        locale: 'ar',
      });
      socket.receive({type: 'message_saved', message: {}});
    });

    await waitFor(() => expect(result.current.stream?.content).toBe('Hi'));
    expect(result.current.stream?.searchContext?.rewritten_query).toBe(
      'dresses',
    );
    expect(result.current.stream?.debug).toEqual({
      prompt: {q: 'ask'},
      response: {},
    });
    expect(result.current.stream?.products).toEqual([
      {id: 'p1', name: 'Dress'},
    ]);
    expect(result.current.stream?.locale).toBe('ar');
  });

  it('keeps a message queued when the socket send throws, and flushes after reconnect', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    const realSend = socket.send.bind(socket);
    socket.send = () => {
      throw new Error('send boom');
    };
    await act(async () => {
      result.current.sendMessage('retry me', 'key-5');
    });
    expect(socket.sent).toHaveLength(0);
    socket.send = realSend;

    await act(async () => {
      socket.close(4001);
    });
    await waitFor(() => expect(result.current.status).toBe('closed'));
    await act(async () => {
      result.current.retryConnect();
    });
    const reconnected =
      MockWebSocket.instances[MockWebSocket.instances.length - 1];
    await act(async () => {
      reconnected?.open();
    });
    await waitFor(() =>
      expect(
        expectSendFrame(reconnected as MockWebSocket, 'send_message'),
      ).toEqual({
        type: 'send_message',
        content: 'retry me',
        idempotency_key: 'key-5',
        include_saved_message: true,
      }),
    );
  });

  it('reports a socket error without crashing', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      socket.onerror?.();
    });

    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      result.current.retryConnect();
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('goes to closed when no token is available', async () => {
    jest.spyOn(storage, 'getTokens').mockResolvedValue(null);

    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(result.current.status).toBe('closed'));
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('does nothing when no conversation is active', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: null, onMessageSaved: undefined}),
    );

    await waitFor(() => expect(result.current.status).toBe('idle'));
    await act(async () => {
      result.current.sendMessage('x', 'key-0');
    });
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('clears a queued message when the hook unmounts', async () => {
    const {result, unmount} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));

    await act(async () => {
      result.current.sendMessage('lost', 'key-7');
    });

    await act(async () => {
      unmount();
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('reconnects when the app becomes active with a closed socket', async () => {
    const {result} = await renderHook(() =>
      useChatWebSocket({conversationId: 'conv-1', onMessageSaved: undefined}),
    );

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    const socket = MockWebSocket.instances[0];
    await act(async () => {
      socket.open();
    });
    await waitFor(() => expect(result.current.status).toBe('open'));

    await act(async () => {
      appStateListener('background');
    });
    expect(MockWebSocket.instances).toHaveLength(1);

    await act(async () => {
      socket.close(4001);
    });
    await waitFor(() => expect(result.current.status).toBe('closed'));

    await act(async () => {
      appStateListener('active');
    });
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(2));
    await waitFor(() => expect(result.current.status).toBe('connecting'));
  });
});
