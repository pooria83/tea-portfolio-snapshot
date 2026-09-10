export interface CronProductItem {
  id: string;
  name_en: string | null;
  name_ar: string | null;
  name_fa: string | null;
  sku: string | null;
  status: "pending" | "generated";
  last_generated_at: string | null;
  model: string | null;
}

export interface CronProductDetail {
  id: string;
  name_en: string | null;
  name_ar: string | null;
  name_fa: string | null;
  sku: string | null;
  prompt: string | null;
  description_en: string | null;
  description_ar: string | null;
  model: string | null;
  generated_at: string | null;
}

export interface CronSummary {
  llm: {
    total: number;
    pending: number;
    generated: number;
  };
}

export interface EmbeddingCronProductItem {
  id: string;
  name_en: string | null;
  name_ar: string | null;
  name_fa: string | null;
  sku: string | null;
  embedding_model: string | null;
  embedding_status: "pending" | "generating" | "done" | "error" | null;
  embedding_error: string | null;
  updated_at: string | null;
}

export interface ProductEmbeddingRow {
  model_name: string;
  model_id: string | null;
  embedding_status: string;
  embedding_error: string | null;
  updated_at: string | null;
}

export interface EmbeddingCronProductDetail {
  id: string;
  name_en: string | null;
  name_ar: string | null;
  name_fa: string | null;
  sku: string | null;
  embedding_text: string | null;
  embeddings: ProductEmbeddingRow[];
}

export interface PaginationMeta {
  skip: number;
  limit: number;
  total: number;
  has_next: boolean;
  has_previous: boolean;
}
