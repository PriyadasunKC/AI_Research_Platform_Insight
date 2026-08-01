// Types for the shapes returned by Module 1 (Flask, port 5000) and
// Module 2 (FastAPI, port 8010). Kept intentionally loose (optional
// fields, index signatures for note blocks) since both are actively
// developed Python backends — this describes the fields the UI actually
// reads, not a strict contract.

export type DimensionNote = {
  score: number | null;
  what_wrong?: string;
  how_to_improve?: string;
  short_note_si?: string;
  [key: string]: unknown;
};

export type Module1Notes = {
  D1_note?: DimensionNote;
  D2_note?: DimensionNote;
  D3_note?: DimensionNote;
  D4_note?: DimensionNote;
  [key: string]: unknown;
};

export type Module1Result = {
  essay_id: string;
  scores: { D1: number | null; D2: number | null; D3: number | null; D4: number | null };
  hints: { D1?: string; D2?: string; D3?: string; D4?: string };
  notes: Module1Notes;
  weakest: string;
  total: number;
  average_score: number;
  summary_si: string;
  word_count: number;
  model_type: string;
  features: Record<string, unknown>;
  module2_result: { ok: boolean; error?: string; raw?: Module2Result };
  module3_export: {
    json_download_url: string;
    txt_download_url: string;
    api_url: string;
  };
};

export type Module2Claim = {
  claim_sinhala: string;
  claim_type: string;
  verdict: "CORRECT" | "INCORRECT" | "UNVERIFIABLE";
  unverifiable_reason: string | null;
  matched_kg_fact: string;
  explanation: string;
  teacher_feedback: string | null;
  batch_number: number;
};

export type Module2Result = {
  request_id: string;
  caller: string;
  essay_subject: string;
  all_kings_found: string[];
  accuracy_score: number | null;
  coverage_ratio: number;
  confidence_level: "HIGH" | "LOW" | "INSUFFICIENT_KG";
  coverage_warning: boolean;
  total_claims: number;
  total_factual_claims: number;
  editorial_claims: number;
  correct_claims: number;
  incorrect_claims: number;
  unverifiable_claims: number;
  kg_gap_claims: number;
  not_factual_claims: number;
  kg_facts_used: number;
  batch_count: number;
  essay_sentence_count: number;
  claims: Module2Claim[];
  combined_teacher_feedback: string;
  processing_seconds: number;
};

// The exact shape written to module_1/module3_exports/*.json and served
// by GET /api/v1/module3/<essay_id> — this is the final combined payload
// that gets handed off to Module 3.
export type CombinedModule3Payload = {
  essay_text: string;
  scores: Record<string, number | null>;
  notes: Record<string, DimensionNote>;
  weakest_area: { dimension: string; score: number | null; hint: string } | null;
  rag_context: unknown[];
};

export type FetchState<T> = {
  status: "idle" | "loading" | "done" | "error";
  data: T | null;
  error: string | null;
};