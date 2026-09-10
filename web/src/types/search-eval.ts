export type EvalQuerySource = "manual" | "llm" | "seed";
export type EvalQueryStatus = "pending" | "evaluated" | "skipped";

export interface EvalQueryItem {
  id: string;
  text: string;
  locale: string;
  source: EvalQuerySource;
  status: EvalQueryStatus;
  rewritten_query?: string | null;
  filters?: Record<string, string[]> | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvalQueryListResponse {
  items: EvalQueryItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface EvalQueriesGenerateRequest {
  count: number;
  locales: string[];
}

export interface EvalQueryImportItem {
  text: string;
  locale: string;
  relevant_ids: string[];
}

export interface EvalQueriesImportRequest {
  queries: EvalQueryImportItem[];
}

export interface EvalImportResult {
  created: number;
  skipped: number;
  judgments_created: number;
}

export interface EvalQueryUpdate {
  status?: EvalQueryStatus;
  rewritten_query?: string | null;
  filters?: Record<string, string[]> | null;
}

export interface EvalJudgmentItem {
  product_id: string;
  relevant: boolean;
  rank?: number | null;
}

export interface EvalJudgmentsRequest {
  judgments: EvalJudgmentItem[];
}

export interface EvalSearchRequest {
  query: string;
  locale: string;
  limit?: number;
}

export interface EvalSearchResultItem {
  rank: number;
  score: number;
  id: string;
  name?: string | null;
  price?: number | null;
  currency: string;
  brand?: string | null;
  image_url?: string | null;
  store_id?: string | null;
  product_data?: Record<string, unknown> | null;
}

export interface EvalSearchResponse {
  query: string;
  locale: string;
  rewritten_query?: string | null;
  filters?: Record<string, string[]> | null;
  specs: Record<string, unknown>[];
  results: EvalSearchResultItem[];
}

export interface EvalMetricItem {
  locale: string;
  query_count: number;
  mrr_10: number;
  recall_10: number;
}

export interface EvalMetricsResponse {
  overall?: EvalMetricItem | null;
  per_locale: EvalMetricItem[];
}
