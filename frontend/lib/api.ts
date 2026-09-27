import type { AskResponse, DocumentSummary, StreamEvent, UploadResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_BASE_URL) {
  // Fails loudly at build/runtime rather than silently calling the wrong host.
  console.warn(
    "NEXT_PUBLIC_API_URL is not set. API calls will fail. See frontend/.env.example."
  );
}

/**
 * Reads a JSON error body from a failed response, falling back to the
 * status text if the body isn't valid JSON (e.g. an unrelated 502 from a
 * platform edge, not our FastAPI app).
 */
async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText || `Request failed with status ${response.status}`;
  }
}

export async function pingHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Uploads a PDF via XMLHttpRequest (rather than fetch) so we can report
 * upload progress as bytes are sent to the server.
 */
export function uploadPdf(
  file: File,
  onUploadProgress: (percent: number) => void
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onUploadProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      let body: Record<string, unknown> = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // handled below via status check
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as unknown as UploadResponse);
      } else {
        reject(
          new Error((body.detail as string) || `Upload failed with status ${xhr.status}`)
        );
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Network error during upload.")));

    xhr.open("POST", `${API_BASE_URL}/upload`);
    xhr.send(formData);
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }
}

export async function getDocumentSummary(documentId: string): Promise<DocumentSummary> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/summary`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }
  return response.json();
}

export interface AskHistoryTurn {
  role: "user" | "assistant";
  content: string;
}

export async function askQuestion(
  documentIds: string[],
  question: string,
  history: AskHistoryTurn[]
): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, question, history }),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

/**
 * Parses one SSE event block (the text between two blank lines) into a
 * typed StreamEvent. Returns null for blocks we don't recognize (e.g. a
 * bare comment/keepalive line some proxies inject).
 */
function parseSseBlock(block: string): StreamEvent | null {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (eventName === "reset") return { type: "reset" };
  if (dataLines.length === 0) return null;

  try {
    const data = JSON.parse(dataLines.join("\n"));
    switch (eventName) {
      case "trace":
        return { type: "trace", data };
      case "token":
        return { type: "token", data };
      case "final":
        return { type: "final", data };
      case "error":
        return { type: "error", data };
      default:
        return null;
    }
  } catch {
    return null;
  }
}

/**
 * Streams /ask/stream via fetch + ReadableStream (EventSource can't send a
 * POST body, which we need for document_ids/question/history). Buffers
 * across chunk boundaries so an event split across two network reads still
 * parses correctly.
 */
export async function streamAsk(
  documentIds: string[],
  question: string,
  history: AskHistoryTurn[],
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, question, history }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(await extractErrorMessage(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawBlock = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const event = parseSseBlock(rawBlock);
      if (event) onEvent(event);

      boundary = buffer.indexOf("\n\n");
    }
  }
}
