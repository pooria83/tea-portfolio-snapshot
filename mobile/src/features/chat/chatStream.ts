import type {ChatMessage, ChatProduct} from './types';

export interface ChatStreamState {
  content: string;
  products: ChatProduct[];
  locale?: string;
  searchContext: ChatMessage['search_context'];
  debug: ChatMessage['debug'];
  status: 'streaming' | 'completed' | 'failed';
  error: string | null;
}

export function initialStreamState(): ChatStreamState {
  return {
    content: '',
    products: [],
    searchContext: null,
    debug: null,
    status: 'streaming',
    error: null,
  };
}

export function sendMessageFrame(
  content: string,
  idempotencyKey: string,
): string {
  return JSON.stringify({
    type: 'send_message',
    content,
    idempotency_key: idempotencyKey,
    include_saved_message: true,
  });
}

export function sendSimilarRequestFrame(
  productId: string,
  idempotencyKey: string,
  productName?: string,
): string {
  return JSON.stringify({
    type: 'similar_request',
    product_id: productId,
    product_name: productName ?? '',
    idempotency_key: idempotencyKey,
    include_saved_message: true,
  });
}

export type ChatStreamAction =
  | {type: 'start'; searchContext: ChatMessage['search_context']}
  | {type: 'debug'; debug: ChatMessage['debug']}
  | {type: 'chunk'; delta: string}
  | {type: 'products'; products: ChatProduct[]; locale?: string}
  | {type: 'completed'}
  | {type: 'failed'; error: string}
  | {type: 'reset'};

export function chatStreamReducer(
  state: ChatStreamState | null,
  action: ChatStreamAction,
): ChatStreamState | null {
  switch (action.type) {
    case 'start': {
      return {
        ...initialStreamState(),
        searchContext: action.searchContext,
      };
    }
    case 'debug': {
      return state ? {...state, debug: action.debug} : state;
    }
    case 'chunk': {
      return state ? {...state, content: state.content + action.delta} : state;
    }
    case 'products': {
      return state
        ? {
            ...state,
            products: action.products,
            ...(action.locale ? {locale: action.locale} : {}),
          }
        : state;
    }
    case 'completed': {
      return state && state.status === 'streaming'
        ? {...state, status: 'completed'}
        : state;
    }
    case 'failed': {
      return state
        ? {...state, status: 'failed', error: action.error}
        : {...initialStreamState(), status: 'failed', error: action.error};
    }
    case 'reset': {
      return null;
    }
    default: {
      return state;
    }
  }
}

export function parseChatFrame(raw: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (
      parsed !== null &&
      typeof parsed === 'object' &&
      !Array.isArray(parsed)
    ) {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

export const CHAT_ERROR_CODES = [
  'chat_failed',
  'chat_limit_reached',
  'conversation_closed',
  'conversation_not_found',
  'chat_not_available',
  'embedding_failed',
  'product_not_found',
  'chat_engine_failed',
  'empty_content',
  'message_too_large',
  'missing_product_id',
  'invalid_frame',
  'unsupported_frame',
] as const;

export type ChatErrorCode = (typeof CHAT_ERROR_CODES)[number];

export function isChatErrorCode(code: string): code is ChatErrorCode {
  return (CHAT_ERROR_CODES as readonly string[]).includes(code);
}

export function errorCodeFromFrame(
  frame: Record<string, unknown>,
): string | null {
  const code = typeof frame.code === 'string' ? frame.code : '';
  return isChatErrorCode(code) ? code : null;
}
