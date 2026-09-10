import {
  normalizeChatMessage,
  normalizeConversationItem,
} from '../../../src/features/chat/normalize';
import type {ChatMessage} from '../../../src/features/chat/types';

describe('normalizeChatMessage', () => {
  it('keeps a well-formed message intact', () => {
    const message: Partial<ChatMessage> = {
      id: 'm1',
      conversation_id: 'conv-1',
      role: 'assistant',
      content: 'answer',
      status: 'completed',
      token_count: 5,
      product_snapshots: [
        {id: 'p1', price: 10, currency: 'USD'},
      ] as unknown as ChatMessage['product_snapshots'],
      search_context: null,
      debug: null,
      feedback: null,
      created_at: '2026-08-01T10:00:00Z',
      error: null,
      locale: null,
    };

    expect(normalizeChatMessage(message)).toEqual(message);
  });

  it('defaults missing and malformed fields to safe values', () => {
    const normalized = normalizeChatMessage({
      id: 'm1',
      role: 'unknown' as never,
      product_snapshots: [null, {name: 'no id'}, {id: 'p2'}],
    } as unknown as Partial<ChatMessage>);

    expect(normalized.role).toBe('assistant');
    expect(normalized.status).toBe('completed');
    expect(normalized.content).toBe('');
    expect(normalized.product_snapshots).toEqual([{id: 'p2'}]);
    expect(normalized.token_count).toBeNull();
    expect(normalized.search_context).toBeNull();
    expect(normalized.created_at).toBe('');
    expect(normalized.error).toBeNull();
  });

  it('defaults a missing product_snapshots field to an empty array', () => {
    const normalized = normalizeChatMessage({id: 'm2'});

    expect(Array.isArray(normalized.product_snapshots)).toBe(true);
    expect(normalized.product_snapshots).toHaveLength(0);
  });
});

describe('normalizeConversationItem', () => {
  it('keeps a well-formed conversation intact', () => {
    const conversation = {
      id: 'conv-1',
      title: 'Dresses',
      status: 'active' as const,
      user_message_count: 3,
      last_activity_at: '2026-08-01T10:00:00Z',
      locale: 'en',
      created_at: '2026-08-01T09:00:00Z',
      updated_at: '2026-08-01T10:00:00Z',
    };

    expect(normalizeConversationItem(conversation)).toEqual(conversation);
  });

  it('defaults missing and malformed fields to safe values', () => {
    const normalized = normalizeConversationItem({
      id: 'conv-2',
      status: 'weird' as never,
    });

    expect(normalized.status).toBe('active');
    expect(normalized.title).toBeNull();
    expect(normalized.user_message_count).toBe(0);
    expect(normalized.locale).toBe('en');
    expect(normalized.created_at).toBe('');
  });
});
