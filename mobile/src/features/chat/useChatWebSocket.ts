import {useCallback, useEffect, useReducer, useRef, useState} from 'react';
import {AppState} from 'react-native';
import Config from 'react-native-config';

import {storage} from '../../services/storage';
import {log} from '../../services/logging/logger';
import {normalizeChatMessage} from './normalize';
import {
  chatStreamReducer,
  errorCodeFromFrame,
  parseChatFrame,
  sendMessageFrame,
  sendSimilarRequestFrame,
} from './chatStream';
import type {ChatMessage, ChatProduct} from './types';

export type ChatSocketStatus =
  'idle' | 'connecting' | 'open' | 'closed' | 'reconnecting' | 'failed';

interface UseChatWebSocketOptions {
  conversationId: string | null;
  onMessageSaved?: (message: ChatMessage, conversationId: string) => void;
}

type PendingMessage =
  | {
      kind: 'message';
      conversationId: string;
      content: string;
      idempotencyKey: string;
    }
  | {
      kind: 'similar';
      conversationId: string;
      productId: string;
      productName: string;
      idempotencyKey: string;
    };

interface SocketCloseEventLike {
  code?: number | undefined;
}

interface SocketMessageEventLike {
  data?: string | ArrayBuffer | Blob;
}

const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 30_000;
const MAX_RETRY_ATTEMPTS = 5;

function buildWsUrl(
  apiBase: string,
  conversationId: string,
  token: string,
): string {
  const base = apiBase.replace(/\/+$/, '');
  const scheme = base.startsWith('https') ? 'wss' : 'ws';
  const hostAndPath = base.replace(/^https?:\/\//, '');
  return `${scheme}://${hostAndPath}/ws/chat/${conversationId}?token=${encodeURIComponent(
    token,
  )}`;
}

export function useChatWebSocket({
  conversationId,
  onMessageSaved,
}: UseChatWebSocketOptions) {
  const [status, setStatus] = useState<ChatSocketStatus>(() =>
    conversationId ? 'connecting' : 'idle',
  );
  const [stream, dispatchStream] = useReducer(chatStreamReducer, null);
  const socketRef = useRef<WebSocket | null>(null);
  const socketConversationRef = useRef<string | null>(null);
  const pendingDebugRef = useRef<ChatMessage['debug']>(null);
  const onMessageSavedRef = useRef(onMessageSaved);
  const pendingMessageRef = useRef<PendingMessage | null>(null);
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => {
    onMessageSavedRef.current = onMessageSaved;
  }, [onMessageSaved]);

  const startStream = useCallback(() => {
    pendingDebugRef.current = null;
    dispatchStream({type: 'start', searchContext: null});
  }, []);

  useEffect(() => {
    if (!conversationId) {
      return;
    }

    const activeConversationId: string = conversationId;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    let disposed = false;

    const clearTimers = () => {
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      if (pingTimer !== null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const stopPing = () => {
      if (pingTimer !== null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const startPing = () => {
      stopPing();
      pingTimer = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({type: 'ping'}));
        }
      }, PING_INTERVAL_MS);
    };

    const flushPending = () => {
      const pending = pendingMessageRef.current;
      if (
        !pending ||
        pending.conversationId !== activeConversationId ||
        !socket ||
        socket.readyState !== WebSocket.OPEN
      ) {
        return;
      }
      pendingMessageRef.current = null;
      try {
        if (pending.kind === 'similar') {
          socket.send(
            sendSimilarRequestFrame(
              pending.productId,
              pending.idempotencyKey,
              pending.productName,
            ),
          );
        } else {
          socket.send(
            sendMessageFrame(pending.content, pending.idempotencyKey),
          );
        }
        startStream();
      } catch (error) {
        log.warn('chat_ws_flush_failed', {error});
      }
    };

    const handleOpen = () => {
      attempt = 0;
      setStatus('open');
      startPing();
      flushPending();
    };

    const scheduleRetry = () => {
      if (disposed) {
        return;
      }
      if (attempt >= MAX_RETRY_ATTEMPTS) {
        log.warn('chat_ws_max_retries', {conversationId: activeConversationId});
        setStatus('failed');
        return;
      }
      const delay = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS);
      attempt += 1;
      setStatus('reconnecting');
      retryTimer = setTimeout(() => {
        void connect();
      }, delay);
    };

    const handleClose = (event: SocketCloseEventLike) => {
      stopPing();
      if (disposed) {
        return;
      }
      if (event.code === 4001) {
        log.warn('chat_ws_closed', {code: event.code});
        setStatus('closed');
        return;
      }
      scheduleRetry();
    };

    const handleMessage = (event: SocketMessageEventLike) => {
      const raw = typeof event.data === 'string' ? event.data : '';
      const frame = parseChatFrame(raw);
      if (!frame) {
        log.warn('chat_ws_invalid_frame');
        return;
      }

      switch (frame.type) {
        case 'assistant_start': {
          const searchContext =
            (frame.search_context as ChatMessage['search_context']) ?? null;
          const debug = pendingDebugRef.current;
          pendingDebugRef.current = null;
          dispatchStream({type: 'start', searchContext});
          if (debug) {
            dispatchStream({type: 'debug', debug});
          }
          break;
        }
        case 'debug': {
          const debug = (frame.debug as ChatMessage['debug']) ?? null;
          pendingDebugRef.current = debug;
          dispatchStream({type: 'debug', debug});
          break;
        }
        case 'text_chunk': {
          const delta = typeof frame.delta === 'string' ? frame.delta : '';
          dispatchStream({type: 'chunk', delta});
          break;
        }
        case 'product_cards': {
          const products = Array.isArray(frame.products)
            ? (frame.products as ChatProduct[])
            : [];
          const locale =
            typeof frame.locale === 'string' ? frame.locale : undefined;
          dispatchStream({
            type: 'products',
            products,
            ...(locale ? {locale} : {}),
          });
          break;
        }
        case 'assistant_end': {
          dispatchStream({type: 'completed'});
          break;
        }
        case 'error': {
          const code = errorCodeFromFrame(frame) ?? 'chat_failed';
          dispatchStream({type: 'failed', error: code});
          break;
        }
        case 'message_saved': {
          const saved = normalizeChatMessage(
            (frame.message as Partial<ChatMessage> | undefined) ?? {},
          );
          if (saved.id) {
            const conversationIdFromFrame =
              typeof frame.conversation_id === 'string'
                ? frame.conversation_id
                : activeConversationId;
            onMessageSavedRef.current?.(saved, conversationIdFromFrame);
          }
          dispatchStream({type: 'completed'});
          break;
        }
        default: {
          break;
        }
      }
    };

    const connect = async () => {
      if (disposed) {
        return;
      }
      setStatus('connecting');
      const tokens = await storage.getTokens();
      if (disposed) {
        return;
      }
      const token = tokens?.accessToken;
      if (!token) {
        setStatus('closed');
        return;
      }
      socket = new WebSocket(
        buildWsUrl(Config.API_BASE_URL, activeConversationId, token),
      );
      socketRef.current = socket;
      socketConversationRef.current = activeConversationId;
      socket.onopen = handleOpen;
      socket.onclose = handleClose;
      socket.onerror = () => {
        log.warn('chat_ws_error', {conversationId: activeConversationId});
      };
      socket.onmessage = handleMessage;
    };
    connectRef.current = () => {
      void connect();
    };

    const handleAppState = (state: string) => {
      if (state !== 'active' || disposed) {
        return;
      }
      const current = socketRef.current;
      if (
        !current ||
        current.readyState === WebSocket.CLOSED ||
        current.readyState === WebSocket.CLOSING
      ) {
        attempt = 0;
        clearTimers();
        void connect();
      }
    };

    void connect();
    const subscription = AppState.addEventListener('change', handleAppState);

    return () => {
      disposed = true;
      clearTimers();
      subscription.remove();
      if (socket) {
        socket.onopen = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        socket.close();
      }
      socketRef.current = null;
      socketConversationRef.current = null;
      if (pendingMessageRef.current?.conversationId === activeConversationId) {
        pendingMessageRef.current = null;
      }
      setStatus('idle');
      dispatchStream({type: 'reset'});
    };
  }, [conversationId, startStream]);

  const sendMessage = useCallback(
    (content: string, idempotencyKey: string) => {
      if (!conversationId) {
        return;
      }
      const socket = socketRef.current;
      if (
        socket &&
        socket.readyState === WebSocket.OPEN &&
        socketConversationRef.current === conversationId
      ) {
        try {
          socket.send(sendMessageFrame(content, idempotencyKey));
          startStream();
        } catch (error) {
          log.warn('chat_ws_send_failed', {error});
          pendingMessageRef.current = {
            kind: 'message',
            conversationId,
            content,
            idempotencyKey,
          };
        }
        return;
      }
      pendingMessageRef.current = {
        kind: 'message',
        conversationId,
        content,
        idempotencyKey,
      };
    },
    [conversationId, startStream],
  );

  const sendSimilarRequest = useCallback(
    (productId: string, idempotencyKey: string, productName?: string) => {
      if (!conversationId) {
        return;
      }
      const similarName = productName ?? '';
      const socket = socketRef.current;
      if (
        socket &&
        socket.readyState === WebSocket.OPEN &&
        socketConversationRef.current === conversationId
      ) {
        try {
          socket.send(
            sendSimilarRequestFrame(productId, idempotencyKey, similarName),
          );
          startStream();
        } catch (error) {
          log.warn('chat_ws_similar_send_failed', {error});
          pendingMessageRef.current = {
            kind: 'similar',
            conversationId,
            productId,
            productName: similarName,
            idempotencyKey,
          };
        }
        return;
      }
      pendingMessageRef.current = {
        kind: 'similar',
        conversationId,
        productId,
        productName: similarName,
        idempotencyKey,
      };
    },
    [conversationId, startStream],
  );

  const retryConnect = useCallback(() => {
    const current = socketRef.current;
    if (
      current &&
      (current.readyState === WebSocket.OPEN ||
        current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }
    connectRef.current();
  }, []);

  const resetStream = useCallback(() => {
    pendingDebugRef.current = null;
    dispatchStream({type: 'reset'});
  }, []);

  return {
    status,
    stream,
    sendMessage,
    sendSimilarRequest,
    resetStream,
    retryConnect,
  };
}
