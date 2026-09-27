export interface UploadResponse {
  document_id: string;
  doc_name: string;
  num_chunks: number;
  num_pages: number;
}

/** A document as tracked client-side, persisted to localStorage. */
export interface LibraryDocument {
  id: string;
  name: string;
  pages: number;
  uploadedAt: string;
}

export type UploadStatus = "idle" | "uploading" | "processing" | "success" | "error";

export type Confidence = "high" | "medium" | "low";

export type AgentName = "planner" | "retriever" | "analyst" | "verifier";

export interface TraceEvent {
  agent: AgentName;
  status: "started" | "completed" | "error";
  summary: string;
  duration_ms: number;
}

export interface Citation {
  doc_id: string;
  doc_name: string;
  page: number;
  snippet: string;
}

export interface AskResponse {
  final_answer: string;
  citations: Citation[];
  confidence: Confidence;
  trace: TraceEvent[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: Confidence;
  trace?: TraceEvent[];
  isStreaming?: boolean;
  error?: string;
}

export interface DocumentSummary {
  title_guess: string;
  key_points: string[];
  suggested_questions: string[];
}

export type StreamEvent =
  | { type: "trace"; data: TraceEvent }
  | { type: "token"; data: { text: string } }
  | { type: "reset" }
  | { type: "final"; data: { final_answer: string; citations: Citation[]; confidence: Confidence } }
  | { type: "error"; data: { detail: string } };
