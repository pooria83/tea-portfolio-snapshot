export interface MessageFeedback {
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface ConversationItem {
  id: string;
  title: string | null;
  status: 'active' | 'closed';
  user_message_count: number;
  last_activity_at: string;
  locale: string;
  created_at: string;
  updated_at: string;
}

export interface ChatProduct {
  id: string;
  name: string | null;
  name_ar?: string | null;
  name_en?: string | null;
  name_fa?: string | null;
  price: number | null;
  currency: string;
  brand: string | null;
  brand_ar?: string | null;
  brand_en?: string | null;
  brand_fa?: string | null;
  image_url: string | null;
  buy_url: string | null;
  store_id: string | null;
}

export type ChatIntent = 'greeting' | 'search' | 'general' | 'error';

export interface ChatMessageDebug {
  prompt: Record<string, unknown>;
  response: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  status: 'streaming' | 'completed' | 'failed';
  token_count: number | null;
  product_snapshots: ChatProduct[];
  search_context: {
    rewritten_query: string | null;
    filters: Record<string, string[]> | null;
    intent?: ChatIntent | null;
  } | null;
  debug: ChatMessageDebug | null;
  feedback: MessageFeedback | null;
  created_at: string;
  error: string | null;
  locale?: string | null;
}

export interface ConversationCreateRequest {
  locale: string;
  create_new: boolean;
  app_version?: string;
}
