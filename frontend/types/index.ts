export interface UploadResponse {
  document_id: string;
  num_chunks: number;
  num_pages: number;
}

export interface AskResponse {
  answer: string;
  source_pages: number[];
}

export type UploadStatus = "idle" | "uploading" | "processing" | "success" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sourcePages?: number[];
}
