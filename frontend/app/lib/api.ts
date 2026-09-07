const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'API error: ' + res.status);
  }
  return res.json();
}

export async function apiUpload(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(API_BASE + '/api/documents', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Upload error: ' + res.status);
  }
  return res.json();
}

export interface DocumentType {
  id: string;
  filename: string;
  uploaded_at: string;
  page_count: number | null;
  status: string;
  sha256: string;
  fact_count?: number;
  issue_count?: number;
  relationship_count?: number;
}

export interface FactType {
  id: string;
  document_id: string;
  page_number: number;
  fact_type: string;
  entity: string | null;
  metric: string | null;
  value: string | null;
  normalized_value: number | null;
  unit: string | null;
  time_period: string | null;
  scope: string | null;
  evidence_quote: string;
  confidence: number;
  attributes: Record<string, unknown> | null;
  created_at: string;
  document_filename?: string | null;
}

export interface RelationshipType {
  id: string;
  fact_a_id: string;
  fact_b_id: string;
  relationship_type: string;
  reasoning: string;
  confidence: number;
  created_at: string;
  fact_a: FactType | null;
  fact_b: FactType | null;
}

export interface IssueType {
  id: string;
  document_id: string;
  page_number: number | null;
  issue_type: string;
  raw_text_snippet: string | null;
  detail: string | null;
  created_at: string;
  document_filename?: string | null;
}
