export interface KnowledgeDocument {
  id: string;
  title: string;
  doc_type: "pdf" | "url" | "note" | "report";
  source_path: string | null;
  tags: string[];
  company: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  /** Only present when fetching single document detail */
  content_text?: string;
}

export interface KnowledgeSearchResult {
  id: string;
  content: string;
  source_type: string;
  source_category: string;
  document_id?: string;
  document_title?: string;
  doc_type?: string;
  score: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResult[];
  count: number;
}
