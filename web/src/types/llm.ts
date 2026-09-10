export interface LLMApiKeyItem {
  id: string;
  model_id: string;
  name?: string | null;
  is_active: boolean;
  masked_key: string;
  created_at: string;
}

export interface LLMModelItem {
  id: string;
  provider: string;
  model: string;
  is_active: boolean;
  api_keys: LLMApiKeyItem[];
}

export interface LLMSettingsResponse {
  default_llm_model_id: string | null;
  default_llm_model: LLMModelItem | null;
  user_comm_model_id: string | null;
  user_comm_model: LLMModelItem | null;
}

export interface LLMSettingsUpdate {
  default_llm_model_id?: string | null;
  user_comm_model_id?: string | null;
}

export interface PromptTemplateResponse {
  pre_prompt: string;
  ending_prompt: string;
  chat_assistant: string;
  parse_query: string;
  summarize: string;
  title: string;
}

export interface PromptTemplateUpdate {
  pre_prompt?: string | null;
  ending_prompt?: string | null;
  chat_assistant?: string | null;
  parse_query?: string | null;
  summarize?: string | null;
  title?: string | null;
}

export interface SystemSettingItem {
  key: string;
  value: string;
}

export interface ScraperHeaderItem {
  id: string;
  name: string;
  header: string | null;
  status: "ready" | "error";
  error_message: string | null;
  error_at: string | null;
  updated_at: string;
}

export interface ScraperHeaderUpdate {
  header: string;
}

export interface EmbedModelItem {
  id: string;
  model_name: string;
  display_name: string;
  is_active: boolean;
}

export interface SystemSettingUpdate {
  key: string;
  value: string;
}

export interface EmbedTextRequest {
  text: string;
}

export interface EmbedTextResponse {
  model: string;
  dimensions: number;
  embedding: number[];
}
