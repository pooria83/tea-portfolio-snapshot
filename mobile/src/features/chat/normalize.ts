import type {ChatMessage, ConversationItem} from './types';

export function normalizeChatMessage(
  message: Partial<ChatMessage>,
): ChatMessage {
  return {
    id: typeof message.id === 'string' ? message.id : '',
    conversation_id:
      typeof message.conversation_id === 'string'
        ? message.conversation_id
        : '',
    role:
      message.role === 'user' || message.role === 'assistant'
        ? message.role
        : 'assistant',
    content: typeof message.content === 'string' ? message.content : '',
    status:
      message.status === 'streaming' ||
      message.status === 'completed' ||
      message.status === 'failed'
        ? message.status
        : 'completed',
    token_count:
      typeof message.token_count === 'number' ? message.token_count : null,
    product_snapshots: Array.isArray(message.product_snapshots)
      ? message.product_snapshots.filter(
          (product) => product != null && typeof product.id === 'string',
        )
      : [],
    search_context: message.search_context ?? null,
    debug: message.debug ?? null,
    feedback: message.feedback ?? null,
    created_at:
      typeof message.created_at === 'string' ? message.created_at : '',
    error: typeof message.error === 'string' ? message.error : null,
    locale: typeof message.locale === 'string' ? message.locale : null,
  };
}

export function normalizeConversationItem(
  conversation: Partial<ConversationItem>,
): ConversationItem {
  return {
    id: typeof conversation.id === 'string' ? conversation.id : '',
    title: typeof conversation.title === 'string' ? conversation.title : null,
    status:
      conversation.status === 'active' || conversation.status === 'closed'
        ? conversation.status
        : 'active',
    user_message_count:
      typeof conversation.user_message_count === 'number'
        ? conversation.user_message_count
        : 0,
    last_activity_at:
      typeof conversation.last_activity_at === 'string'
        ? conversation.last_activity_at
        : '',
    locale:
      typeof conversation.locale === 'string' ? conversation.locale : 'en',
    created_at:
      typeof conversation.created_at === 'string'
        ? conversation.created_at
        : '',
    updated_at:
      typeof conversation.updated_at === 'string'
        ? conversation.updated_at
        : '',
  };
}
