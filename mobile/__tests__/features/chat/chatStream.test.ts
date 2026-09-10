import {
  CHAT_ERROR_CODES,
  chatStreamReducer,
  errorCodeFromFrame,
  initialStreamState,
  isChatErrorCode,
  parseChatFrame,
  sendMessageFrame,
  sendSimilarRequestFrame,
} from '../../../src/features/chat/chatStream';
import type {ChatStreamState} from '../../../src/features/chat/chatStream';

describe('sendMessageFrame', () => {
  it('builds a send_message frame with idempotency key', () => {
    const frame = JSON.parse(sendMessageFrame('red dress', 'key-1')) as Record<
      string,
      unknown
    >;
    expect(frame).toEqual({
      type: 'send_message',
      content: 'red dress',
      idempotency_key: 'key-1',
      include_saved_message: true,
    });
  });
});

describe('sendSimilarRequestFrame', () => {
  it('builds a similar_request frame with idempotency key', () => {
    const frame = JSON.parse(
      sendSimilarRequestFrame('p-1', 'key-sim'),
    ) as Record<string, unknown>;
    expect(frame).toEqual({
      type: 'similar_request',
      product_id: 'p-1',
      product_name: '',
      idempotency_key: 'key-sim',
      include_saved_message: true,
    });
  });
});

describe('parseChatFrame', () => {
  it('parses a valid JSON object frame', () => {
    expect(parseChatFrame('{"type":"text_chunk","delta":"hi"}')).toEqual({
      type: 'text_chunk',
      delta: 'hi',
    });
  });

  it('returns null for invalid JSON', () => {
    expect(parseChatFrame('not json')).toBeNull();
  });

  it('returns null for non-object payloads', () => {
    expect(parseChatFrame('"just a string"')).toBeNull();
    expect(parseChatFrame('[1, 2]')).toBeNull();
  });
});

describe('chatStreamReducer', () => {
  it('starts a stream with search context', () => {
    const state = chatStreamReducer(null, {
      type: 'start',
      searchContext: {rewritten_query: 'dress', filters: null},
    });
    expect(state).not.toBeNull();
    expect(state?.status).toBe('streaming');
    expect(state?.content).toBe('');
    expect(state?.searchContext).toEqual({
      rewritten_query: 'dress',
      filters: null,
    });
  });

  it('appends text chunks', () => {
    let state = chatStreamReducer(null, {type: 'start', searchContext: null});
    state = chatStreamReducer(state, {type: 'chunk', delta: 'hello '});
    state = chatStreamReducer(state, {type: 'chunk', delta: 'world'});
    expect(state?.content).toBe('hello world');
  });

  it('sets products and locale', () => {
    let state = chatStreamReducer(null, {type: 'start', searchContext: null});
    state = chatStreamReducer(state, {
      type: 'products',
      products: [
        {
          id: 'p1',
          name: null,
          price: null,
          currency: 'SAR',
          brand: null,
          image_url: null,
          buy_url: null,
          store_id: null,
        },
      ],
      locale: 'ar',
    });
    expect(state?.products).toHaveLength(1);
    expect(state?.locale).toBe('ar');
  });

  it('attaches debug info', () => {
    let state = chatStreamReducer(null, {type: 'start', searchContext: null});
    state = chatStreamReducer(state, {
      type: 'debug',
      debug: {prompt: {a: 1}, response: {b: 2}},
    });
    expect(state?.debug).toEqual({prompt: {a: 1}, response: {b: 2}});
  });

  it('marks a streaming state as completed', () => {
    let state = chatStreamReducer(null, {type: 'start', searchContext: null});
    state = chatStreamReducer(state, {type: 'completed'});
    expect(state?.status).toBe('completed');
  });

  it('keeps an already completed state completed', () => {
    let state = chatStreamReducer(null, {type: 'start', searchContext: null});
    state = chatStreamReducer(state, {type: 'completed'});
    const completed = chatStreamReducer(state, {type: 'completed'});
    expect(completed?.status).toBe('completed');
  });

  it('marks the stream as failed with an error code', () => {
    const state = chatStreamReducer(null, {
      type: 'failed',
      error: 'chat_limit_reached',
    });
    expect(state?.status).toBe('failed');
    expect(state?.error).toBe('chat_limit_reached');
  });

  it('resets to null', () => {
    let state = chatStreamReducer(null, {type: 'start', searchContext: null});
    state = chatStreamReducer(state, {type: 'chunk', delta: 'x'});
    expect(chatStreamReducer(state, {type: 'reset'})).toBeNull();
  });

  it('ignores unknown actions', () => {
    const state = chatStreamReducer(null, {
      type: 'start',
      searchContext: null,
    });
    expect(chatStreamReducer(state, {type: 'unknown'} as never)).toEqual(state);
  });
});

describe('error codes', () => {
  it('exposes the chat error codes', () => {
    expect(CHAT_ERROR_CODES).toContain('chat_limit_reached');
    expect(CHAT_ERROR_CODES).toContain('embedding_failed');
    expect(CHAT_ERROR_CODES).toContain('conversation_closed');
    expect(CHAT_ERROR_CODES).toContain('conversation_not_found');
    expect(CHAT_ERROR_CODES).toContain('chat_not_available');
    expect(CHAT_ERROR_CODES).toContain('chat_failed');
    expect(CHAT_ERROR_CODES).toContain('product_not_found');
    expect(CHAT_ERROR_CODES).toContain('chat_engine_failed');
    expect(CHAT_ERROR_CODES).toContain('empty_content');
    expect(CHAT_ERROR_CODES).toContain('message_too_large');
    expect(CHAT_ERROR_CODES).toContain('missing_product_id');
    expect(CHAT_ERROR_CODES).toContain('invalid_frame');
    expect(CHAT_ERROR_CODES).toContain('unsupported_frame');
    expect(CHAT_ERROR_CODES).toHaveLength(13);
  });

  it('recognizes known codes', () => {
    expect(isChatErrorCode('chat_failed')).toBe(true);
    expect(isChatErrorCode('something_else')).toBe(false);
  });

  it('extracts an error code from a frame', () => {
    expect(errorCodeFromFrame({code: 'embedding_failed'})).toBe(
      'embedding_failed',
    );
    expect(errorCodeFromFrame({code: 'unknown'})).toBeNull();
    expect(errorCodeFromFrame({})).toBeNull();
  });
});

describe('initialStreamState', () => {
  it('returns a fresh empty streaming state', () => {
    const state = initialStreamState();
    expect(state).toEqual<ChatStreamState>({
      content: '',
      products: [],
      searchContext: null,
      debug: null,
      status: 'streaming',
      error: null,
    });
  });
});
